---
name: airflow-run-failure-diagnosis
description: Diagnosing an Airflow DAG run that failed, is stuck, or never started - reading the task state and the task log first, telling a bug in the task from a scheduler, worker or capacity problem, and re-running by clearing task instances only once the task is safe to repeat. Use when an Airflow task failed, sits in queued or scheduled, was killed without an error, or a DAG did not run when it should have.
---

# Diagnosing a failed or stuck Airflow run

An Airflow failure has two very different kinds of cause, and most time is lost
by treating one as the other. Either the task's own code raised an error, which
the task log shows and a code change fixes, or Airflow never got the task to the
point of running it properly: the scheduler did not create the run, no slot was
free, no worker picked the task up, or the process was killed from outside.
Reading the task's code for the second kind finds nothing, because nothing in
the code went wrong. The procedure below sorts a failure into one of the two
before anyone edits a DAG.

The text assumes Airflow 3.x and also holds for 2.x from 2.6 on. Where the two
majors differ, it says so.

This artifact stops at the boundary of Airflow. If every task succeeded and the
data is still wrong, the scheduler has nothing to report; that is
[data-incident-tracing](../DATA-INCIDENT-TRACING/SKILL.md). When the task log
names an exception and the question becomes why the code raises it, the general
method is [error-diagnosis](../ERROR-DIAGNOSIS/SKILL.md).

## Start from the state, not the code

The state of each task instance in the run already says which half of the
problem you are in, so read it before the code and before the log. The grid
view shows it per task and try; `airflow tasks states-for-dag-run <dag_id>
<run_id>` prints it from the command line.

| State | What it means | Where the cause is |
|---|---|---|
| `failed`, `up_for_retry` | The task ran and ended in an error, or was killed while running | The task log, then the worker if the log has no exception |
| `upstream_failed` | Never ran, because a task it depends on failed | The first failed task upstream, not this one |
| `skipped` | Skipped by a branch, a short-circuit, or a skipped upstream under the default trigger rule | The branch decision and the trigger rules, below |
| `scheduled` for a long time | Waiting for a slot | Pools and concurrency limits |
| `queued` for a long time | Handed to the executor, no worker has started it | Workers, the broker, or pods that cannot be scheduled |
| `deferred` for a long time | Waiting on a trigger | The triggerer |
| no state at all | Not reached yet, or its dependencies cannot be met | Upstream states and trigger rules |

Go to the earliest failure in the run, by dependency and by time. Everything
downstream of it is `upstream_failed` or skipped as a consequence, and fixing
them one at a time repeats the same diagnosis for every task.

Check the try number as well. A task that failed on try 3 of 3 with the same
error each time is a different problem from one that failed once on try 1 and
then succeeded: the first is deterministic, the second is something outside the
code that came and went.

## Read the task log of the failed try

The task log of the failed try names the real error in most failures that are
the task's own. Open the log for that try, not the latest one; a later retry may
show a different, secondary error, or none. Read from the end: a Python
traceback's last line is the exception, and the lines above it name the
operator and the call that raised it.

What decides the next step is whether the log has an exception from the task's
code, the provider or the library it calls. If it does, the cause is in the
task, and the usual suspects are its inputs (a missing file or partition, a
changed upstream schema), its connection (credentials, network, a target that
is down) and its code. A traceback from a provider hook on a connection error,
on a task that succeeded on its retry, is a transient fault outside the DAG;
retries with a delay exist for exactly that, and the fix is a retry policy, not
a code change.

If the log has no exception, ends mid-line, or does not exist, the task did not
fail by itself. The signs:

- **The process was killed.** On 2.x the log ends with "Task exited with return
  code Negsignal.SIGKILL" or return code -9. On 3.x the supervisor process
  outlives the task and logs "Process terminated by signal" with SIGKILL; from
  3.1 the line adds that it was likely out of memory. If the whole pod was
  killed, the log simply
  stops. A SIGKILL is nearly always the worker or pod hitting its memory limit,
  and the code that ran out of memory is in the last lines before it.
- **The scheduler marked the task failed.** The scheduler log carries a
  message asking whether the task was killed externally, because the executor
  reported the task finished while Airflow still had it as queued or running.
- **The heartbeat stopped.** A running task that stops reporting is failed by
  the scheduler once the heartbeat times out (five minutes by default). Airflow
  2 calls these zombie tasks. The worker died, was evicted, or lost its network,
  and the task's own log just stops.
- **The log cannot be read.** A message that the log could not be fetched from
  the worker means the worker that ran the task is gone and remote logging is
  not configured. That is a finding about the deployment, not evidence that the
  task logged nothing.
- **On 3.x, the task cannot reach the API server.** Tasks no longer connect to
  the metadata database; they report through the API server. Errors talking to
  it are a deployment problem even though they appear in the task log.

In each of these the evidence is in the worker, the pod or the platform, not in
the DAG. On Kubernetes, reading those logs is
[kubernetes-pod-log-triage](../KUBERNETES-POD-LOG-TRIAGE/SKILL.md), which also
covers task pods that were deleted after the task. On a managed service you
usually have no shell on the workers: the scheduler, worker and DAG processing
logs are in the provider's log service, and on some services each of them has
to be enabled separately before it is kept. Say which logs the deployment does
not keep instead of concluding from their absence.

A timeout looks like an error but has its own cause. `AirflowTaskTimeout` means
the task ran longer than its `execution_timeout`; the question is why it was
slower than usual (more data, a lock in the target, a slow source), and raising
the timeout only hides that. A whole run marked failed, with every task that
had not finished set to `skipped` and "has timed-out" in the scheduler log,
hit its `dagrun_timeout`. Those skipped tasks are not a branching problem.

## Tasks that wait and never run

A task that sits in `scheduled` is waiting for a slot. Airflow applies several
limits at once, and any one of them can be the full one:

- the task's **pool** (`default_pool` unless the task names another), which
  other DAGs may be using up;
- the DAG's **`max_active_tasks`**, and the task's `max_active_tis_per_dag`
  and `max_active_tis_per_dagrun`, which matters for mapped tasks;
- the deployment-wide **`parallelism`**, which caps queued plus running task
  instances across all DAGs per scheduler.

Before blaming any of them, look at what is holding the slots. Sensors in the
default `poke` mode hold a worker slot, and with it a pool slot and a
`parallelism` slot, for their whole wait, so a handful of
long-waiting sensors can starve every other task in a small deployment;
`mode="reschedule"` or a deferrable sensor releases the slot between checks.

A task in `queued` has passed those limits and been handed to the executor, and
no worker has started it. The executor runs inside the scheduler, so read the
scheduler log first: an error sending the task to the broker, or creating its
pod on the Kubernetes executor, is logged there. If the scheduler handed the
task off cleanly, the cause is on the worker side: Celery workers down or not
consuming the queue the task was sent to, the broker unreachable, or a task pod
that is `Pending` because the cluster has no room or cannot pull the image. After `task_queued_timeout` (ten minutes by default) the
scheduler gives up on a queued task and fails or retries it, so a task that
"failed" with an empty log after exactly that long was never started.

A task in `deferred` that never resumes is waiting on the triggerer. If the
triggerer is not running, or is overloaded, deferrable operators wait
indefinitely and nothing in the task's own log explains it.

## Runs that were never created

When the run itself is missing, the cause is upstream of every task, in how the
scheduler reads the DAG:

- **The DAG does not import.** An import error removes the DAG, or its latest
  version, from scheduling. `airflow dags list-import-errors` lists them, and so
  does the banner in the UI. The fix is in the DAG file, usually work done at
  import time; see [airflow-dag-structure](../AIRFLOW-DAG-STRUCTURE/SKILL.md).
- **The DAG is paused.** New DAGs start paused unless the deployment changed
  `dags_are_paused_at_creation`.
- **The schedule has not come due.** A `start_date` in the future produces no
  runs. On 2.x, and on 3.x when cron data intervals are switched on, the run
  for an interval starts when the interval ends, so a daily DAG's run for
  Monday starts at Tuesday midnight and there is no run "for today" yet. By
  default 3.x runs a cron schedule at the cron time instead. Read which
  timetable the DAG uses before calling a run missing.
- **Catchup is off.** Without catchup, unpausing a DAG with an old
  `start_date` creates only the latest interval's run, not the ones in
  between. The default is on in 2.x and off in 3.x (`catchup_by_default`), so
  a DAG that does not set `catchup` behaves differently after an upgrade.
- **`max_active_runs` is reached.** An older run that is stuck, often on one of
  the waits above, blocks every newer one. The missing run is a symptom; the
  stuck one is the cause.

## Skipped and "no status" tasks after a branch

The default trigger rule, `all_success`, runs a task only when every upstream
task succeeded. A skipped upstream propagates: under `all_success`, the task
after a branch that was not taken is skipped too. That is correct for the
branch's own tasks and wrong for the task that joins the branches back together
or cleans up after them, which then never runs. Give a join
`none_failed_min_one_success` and a cleanup task that must run whatever
happened `all_done`.

A task left with no state while its run is finished usually has a dependency
that can never be met, for example an upstream that was removed from the DAG or
a trigger rule no outcome satisfies. Read its upstream states before its code.

## Re-running

Clear the failed task instance, with its downstream tasks, rather than
triggering a new run. Clearing re-runs the task inside the same run, with the
same logical date and data interval, so a task that writes the partition for
its interval rewrites the same partition. A new manual run has a different
logical date (on 3.x it may have none at all), so the templated values change:
it writes a different partition, writes the current one twice, or fails on a
missing template value. Clearing only the failed tasks also leaves the tasks
that already succeeded alone.

Check which code the cleared task will run. On 2.x, and on bundles without
versioning such as the default `LocalDagBundle`, it is the current code. On a
versioned bundle such as `GitDagBundle`, Airflow 3.1 and later re-run the code
the run was created with, so a fix merged since then does not reach the
cleared task and it fails again the same way. To pick up the fix, clear with
the option to run on the latest version (`run_on_latest_version` in the UI and
the REST API; from 3.3 the default comes from `rerun_with_latest_version`).

Clearing is still a write to production. Before suggesting it, check that the
task is safe to run twice for the same interval: it overwrites or merges its
target for that interval rather than appending, and any side effect outside the
warehouse (an email, a file pushed to a partner, an API call that creates
something) is acceptable to repeat. A task that appended part of its rows
before failing duplicates them when cleared, and the duplicates surface later
as a data incident. If the task is not safe to repeat, say what has to be
cleaned up first. Clearing, marking a task success or failed, and unpausing are
the user's decisions; propose them with the command, and do not run them.

## What to report

- **The run and the first failure**: DAG id, run id, the earliest failed or
  stuck task and its try number.
- **The kind**: an error in the task, with the exception and the line that
  raised it; or an Airflow or platform problem, with the evidence (the state,
  the scheduler or worker message, the missing log, the full pool).
- **The cause**, as far as the evidence goes, and what would confirm it if it
  is not certain.
- **The fix**: a code change, a retry or timeout setting, a capacity change, or
  an infrastructure issue for whoever runs the deployment.
- **The re-run**: which task instances to clear, and whether they are safe to
  repeat.

Logs carry connection strings and data rows. Quote the shape of the error, with
credentials and personal data replaced by a placeholder, even when the reader
has access to the original; see
[sensitive-data-handling](../SENSITIVE-DATA-HANDLING/SKILL.md).
