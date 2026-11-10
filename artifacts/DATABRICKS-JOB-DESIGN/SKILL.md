---
name: databricks-job-design
description: Designing Databricks Lakeflow Jobs - the task graph and run-if conditions, tasks that are safe to retry and repair, job and task parameters and task values, retries and timeouts, concurrency and queueing, triggers (schedule, file arrival, table update, continuous), and the compute each task runs on, including the dbt task. Use when creating or changing a Databricks job, or when one runs twice, skips runs, duplicates data after a repair, or costs more than it should. Not for Lakeflow pipeline definitions or Airflow DAGs.
---

# Designing Lakeflow Jobs

A job is a graph of tasks plus the rules that decide when it runs, what each task
receives, and what happens when something fails. Almost every one of those rules
runs a task again: a retry, a repair, a manual run, a queued run that starts after
the previous one, a trigger that fires twice. The documentation is plain about
the consequence: "Lakeflow Jobs doesn't make tasks idempotent, so if a task wrote
part of its output before it failed, re-running it can duplicate that data." The
design question behind every section below is therefore the same: what happens
when this task runs twice, or two runs overlap?

**Names.** The product is Lakeflow Jobs, shown under "Jobs & Pipelines" in the
workspace; older material says Databricks Workflows. Bundles are now
Declarative Automation Bundles. When a name or option is in doubt, look it up in
the documentation index at `https://docs.databricks.com/llms.txt` and the page it
links, rather than answering from memory.

Neighbours:

- What a pipeline task runs, its datasets and refresh behaviour, is
  [databricks-declarative-pipeline-design](../DATABRICKS-DECLARATIVE-PIPELINE-DESIGN/SKILL.md).
- A streaming query run as a job task is designed with
  [spark-streaming-query-design](../SPARK-STREAMING-QUERY-DESIGN/SKILL.md).
- A task that is slow because of its Spark work is
  [spark-job-tuning](../SPARK-JOB-TUNING/SKILL.md).
- When Airflow orchestrates and triggers Databricks jobs, the DAG side is
  [airflow-dag-structure](../AIRFLOW-DAG-STRUCTURE/SKILL.md).

## First: read the job as it is

Before changing anything, establish:

- **Where the job is defined.** A bundle, Terraform, or the UI. Change it where
  it lives. An edit made in the UI to a job that a bundle deploys is overwritten
  by the next deployment, silently.
- **Who it runs as.** The run-as identity decides what every task can read and
  write. A production job running as a person stops working when that person
  leaves; run it as a service principal.
- **What each task writes, and how.** Append, overwrite of a partition or window,
  or merge on a key. This decides whether the task can be retried at all, and it
  matters more than any setting below.
- **Triggers, concurrency and queueing**, and the compute of each task.

## Make every task safe to run again

A task is safe to re-run when running it twice with the same parameters leaves
the same result as running it once. The common ways to get there:

- **Overwrite what the task owns.** Replace the partition or date window the run
  is responsible for, rather than appending to it.
- **Merge on a key** where rows can arrive more than once.
- **Record completed work** (a batch id or the window processed) and skip it
  when it is already there, for side effects that cannot be overwritten, such as
  sending a file or calling an API.

Give each run its window explicitly. A task that computes "yesterday" from the
clock processes a different day when it is repaired tomorrow. Pass the logical
date as a job parameter, so that a retry, a repair and a backfill all process
the window the run was for. If you default it from a dynamic value such as
`{{job.start_time.iso_date}}`, check what that resolves to on a repair before
relying on it.

**Repair** re-runs "only the subset of unsuccessful tasks and any dependent
tasks", each "from the beginning", and it uses "the current job and task
settings". Two consequences follow. A task that wrote half its output before
failing writes it again, so repair is only as safe as the task. And a repair run
after a deployment mixes code versions inside one run: the tasks that succeeded
ran the old code, the repaired ones run the new. Parameters entered when
repairing override the run's values. Repair applies to jobs with two or more
tasks; a single-task job is simply run again.

## The task graph and run-if conditions

Tasks and their dependencies form a directed acyclic graph. Each task's run-if
condition decides what it does when its upstream tasks finish:

| Condition | Runs when | Otherwise |
|---|---|---|
| All succeeded (default) | Every dependency succeeded | Marked `Upstream failed` |
| At least one succeeded | Any dependency succeeded | `Upstream failed` |
| None failed | No dependency failed | `Upstream failed` |
| All done | Every dependency finished, in any state | Always runs |
| At least one failed | Any dependency failed | Marked `Excluded` |
| All failed | Every dependency failed | `Excluded` |

Use "All done" for cleanup that must run whatever happened, and the "failed"
conditions for a failure branch, such as writing a status record. Two details
catch people out. An `Excluded` dependency counts as successful when downstream
tasks evaluate their condition. And a task whose dependencies are all excluded is
excluded too. A failure branch that is skipped on a good day therefore does not
block what comes after it, but a task placed after the failure branch alone never
runs on a good day.

Control-flow tasks keep decisions inside the graph, where they are visible and
repairable:

- **If/else condition** compares job parameters, task values or dynamic values
  (`==`, `!=`, `>`, `>=`, `<`, `<=`) and runs one branch.
- **For each** runs a nested task once per input, from a fixed list or one
  produced by an upstream task. Iterations may run concurrently, so each one must
  be independent and safe to re-run, like any task.
- **Run Job** triggers another job. Prefer it to starting jobs from notebook code
  through the API: the dependency shows in the graph, the run is tracked, and
  repair works. Run Job tasks count towards the workspace's concurrency limits.

## Parameters and task values

- **Job parameters** are key-value pairs at job level. They are "pushed down to
  tasks that use key-value parameters" and can be overridden on Run now or
  through the API. **Task parameters** belong to one task. Job parameters
  coexist with them and do not replace them.
- **Dynamic value references** fill parameters at run time:
  `{{job.parameters.<name>}}`, `{{job.start_time.iso_date}}`, or
  `{{tasks.<task>.values.<key>}}` for a value an upstream task set. When tasks use
  dynamic values, job parameters are limited to 10,000 characters.
- **Task values** pass small results between tasks: a row count, a flag, a list
  of partitions. An upstream task sets them with
  `dbutils.jobs.taskValues.set(key=..., value=...)`. They are for control
  decisions, not for moving data; write data to a table and pass its name.

Keep secrets out of parameters, which are visible in the run's details. Read
them from a secret scope inside the task.

## Failure handling: retries, timeouts, alerts

- **Retries are off by default** for most configurations; serverless jobs
  optimise retries automatically. Add a retry policy per task, and only to tasks
  that are safe to re-run. A retry is a re-run, with everything above.
- **Set a timeout on every task.** A task with no timeout that hangs holds its
  compute, and with one concurrent run allowed, it also holds back every later
  run. The timeout applies to each retry separately.
- **Fail fast inside the task.** Catching and retrying exceptions in code hides
  failures from the job and repeats work the retry policy would repeat anyway.
  Databricks recommends letting a streaming query fail and leaving retries to
  the orchestrator; the same reasoning holds for batch tasks.
- **Notify a group or channel**, not a person, on failure. Add a duration
  warning where it is available, so that a run that is slow but not failed is
  noticed.

## Concurrency and queueing

New jobs allow one concurrent run by default. When a run is due while the job is
already at its limit, the outcome depends on queueing:

- **Queueing off.** The run is skipped. A schedule that fires while the previous
  run is still going skips a day without failing anything.
- **Queueing on.** The run waits, for up to 48 hours. Queueing is on by default
  for jobs created in the UI since April 2024. Set it explicitly in bundles and
  Terraform rather than relying on a default.

Raise the concurrent-run limit only when runs are parameterized to disjoint
windows, as in a backfill. Two runs over the same window write the same target
at the same time, and neither is safe.

## Triggers

- **Schedule.** Set the time zone explicitly. A schedule in UTC and a business
  day in local time drift apart twice a year.
- **File arrival** watches a Unity Catalog volume or external location, or a
  subpath, and checks for new files on a best-effort basis about once a minute.
  Only new files trigger a run: overwriting a file with the same name does not.
  The trigger says that something arrived, not which files, so the task should
  process everything new since its last run (Auto Loader or a checkpoint), not
  "the file that triggered it". Use the wait-after-last-change setting when files
  arrive in bursts, so that one run sees the whole burst, and a minimum time
  between triggers to cap the run rate. Without file events on the location, the
  number of jobs and files that can be watched is limited.
- **Table update** starts a run when a Unity Catalog table changes. Use it to
  chain jobs on data rather than on time.
- **Continuous** keeps one run active at all times and starts a new one when it
  ends or fails, with exponential backoff and no retry limit. A continuous job
  has no task dependencies and no retry policies. On serverless, only bounded
  streaming triggers such as available-now are supported, so a continuous
  serverless job processes what is available, ends, and starts again.

## Compute

| Task | Recommended compute |
|---|---|
| Notebook, Python script, Python wheel | Serverless jobs compute |
| dbt | A serverless SQL warehouse |
| JAR, Spark Submit | Classic job compute |

- **Serverless** is the default for tasks that support it. Check that the code
  does not depend on what serverless does not offer, such as init scripts or
  cluster-scoped settings, before moving a task to it.
- **Job compute** is created for the run and terminated after it. Tasks in one
  run can share it, which saves start-up time. It cannot be shared between runs
  or jobs.
- **All-purpose clusters** are for interactive work, and Databricks does not
  recommend them for production jobs. They cost more and are shared with whoever
  else uses them, whose libraries and load affect the job.

## The dbt task

The dbt task runs dbt Core from workspace files or a Git repository. The SQL it
generates runs on a serverless or pro SQL warehouse, and the run-as identity
needs `CAN USE` on it. Pin the `dbt-databricks` version on the task (1.6.0 or
later is recommended), so that an adapter release does not change a production
run.

The default commands are `dbt deps`, `dbt seed` and `dbt run`. Replace them with
what the project needs, usually `dbt deps` and `dbt build` with a selector.
`dbt run` skips tests, and `dbt seed` on every run reloads seed tables.

For production, point the Git source at a tag or commit rather than a branch.
A branch makes a repair, which uses the current settings, run code that was
merged after the original run.

## What this skill changes

This skill edits job definitions, in the place where they are managed. Running
them is separate:

- **Runs and repairs in a development target** check a change. Run them if the
  project lets the agent; otherwise hand over the steps.
- **Production runs, repairs and cancellations**, and changes to triggers,
  schedules, concurrency, queueing, compute or the run-as identity, only with
  the user's confirmation each time. Say what each one starts, stops or re-runs.

## Verify before handing over

1. Validate the definition the way the project deploys it, for example by
   validating the bundle.
2. Run the job in development with explicit parameters. Then run it again with
   the same parameters and confirm the targets did not change.
3. Make one task fail after it has written (or stop it mid-run), repair the run,
   and confirm nothing was duplicated.
4. Read the deployed job's settings back: time zone, concurrency, queueing,
   timeouts, retries and run-as. Defaults differ between the UI, bundles and the
   API.
5. Report what was run where, and what was only validated.
