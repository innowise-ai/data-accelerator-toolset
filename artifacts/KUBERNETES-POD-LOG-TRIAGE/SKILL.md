---
name: kubernetes-pod-log-triage
description: Reading the logs of Kubernetes pods with read-only kubectl and reporting each distinct error once, with its count, first and last time, affected pods and root cause, instead of a raw dump. Covers Airflow and Spark pods, Java and Python stack traces, crashed containers and pods killed without a log line. Use when asked to check the logs of a pod, a service, an Airflow task or a Spark application running on Kubernetes, or when something deployed there fails and the cause is not yet known.
---

# Triaging Kubernetes pod logs

A pod log is the cheapest evidence there is about a failure on Kubernetes, and
the easiest to waste. Ten replicas repeating the same connection error for an
hour produce thousands of lines that say one thing. Pasted raw, they push
everything else out of the conversation and hide the second, rarer error that
was the real cause. The job here is to turn the log into a short list of
distinct errors, each counted, dated and traced to its root cause, and to say
what the list means.

This is a log-reading procedure, not a debugging method. Once the errors are
known, finding why they happen is
[error-diagnosis](../ERROR-DIAGNOSIS/SKILL.md). If no pod failed and the data
is wrong anyway, the logs will not show it; that is
[data-incident-tracing](../DATA-INCIDENT-TRACING/SKILL.md).

## Read only, and say where you are reading

Everything below uses `kubectl get`, `kubectl describe` and `kubectl logs`.
None of them change the cluster. The commands that would (`delete`,
`rollout restart`, `exec`, `scale`, `edit`) are not part of reading logs, and
some of them destroy the evidence: restarting a crash-looping pod throws away
the previous container's log, which is usually where the cause is. A fix is a
separate decision the user makes after seeing the summary.

Pass `--context` and `-n` on every command, and do not run
`kubectl config use-context`. Switching the context rewrites the kubeconfig
that every other terminal on the machine reads, so a colleague's next
`kubectl apply`, or the user's own, goes to whichever cluster you last looked
at. Explicit flags also make each command in the transcript say which cluster
it read.

You need the context, the namespace, what to read (a pod, a service, an
Airflow task, a Spark application) and a time window. Take what the user gave.
For anything missing, use the current context and the namespace from it, say
so in the first line of the answer, and ask before reading production if the
context name suggests it. If a command fails with an authentication or
"context not found" error, stop and tell the user to refresh their cluster
credentials the way their platform does it. Retrying will not help, and
guessing another context reads the wrong cluster.

## Look at the pods before the logs

```bash
kubectl --context "$CTX" -n "$NS" get pods -l "$SELECTOR" -o wide
kubectl --context "$CTX" -n "$NS" describe pod "$POD"
kubectl --context "$CTX" -n "$NS" get events --field-selector involvedObject.name="$POD" --sort-by=.lastTimestamp
```

The pod list answers questions the log cannot. `RESTARTS` above zero means a
container died in the window, and the log of the container that died is only
reachable with `--previous`. `STATUS` of `OOMKilled`, `Evicted`,
`ImagePullBackOff` or `Pending` means the process was killed or never started,
so its log is empty or ends mid-line, and the explanation is in `describe`
(`Last State: Terminated`, `Reason`, `Exit Code`) and in the events.

Exit code 137 is SIGKILL. With `Reason: OOMKilled` the container went over its
memory limit, and neither the JVM nor Python gets to log anything, so a log
that stops without an error is consistent with an out-of-memory kill rather
than evidence that nothing went wrong. Read the events early: by default the
API server keeps them for about an hour, so the scheduling failure or probe
failure that explains a restart may be gone by the time anyone looks.

To find the pods of a service, read the selector the workload actually uses
rather than guessing a label:

```bash
kubectl --context "$CTX" -n "$NS" get deploy "$NAME" -o jsonpath='{.spec.selector.matchLabels}'
```

`app.kubernetes.io/name` is common, but Helm charts and operators often use
their own labels, and a selector that matches nothing returns no logs and no
error.

## Where data platform pods live

**Airflow (official Helm chart).** The long-running components carry
`tier=airflow` and `component=` with `scheduler`, `webserver` or
`api-server`, `triggerer`, `dag-processor` or `worker` (Celery workers), plus
`release=<release name>`. A DAG that never appears, or tasks stuck in queued,
is a scheduler or DAG processor question, so start there; an import error is
logged when the DAG file is parsed, not when a task runs.

Task pods are found by their task. Pods started by the Kubernetes executor and
by `KubernetesPodOperator` are labelled with `dag_id`, `task_id`, `run_id` and
`try_number`; Airflow rewrites the values to fit Kubernetes label rules, so
list them with the labels as columns and pick from what is there instead of
building an exact selector:

```bash
kubectl --context "$CTX" -n "$NS" get pods -L dag_id,task_id,try_number --sort-by=.metadata.creationTimestamp
```

A task pod may no longer exist. The Kubernetes executor deletes worker pods
after the task, by default keeping the ones that failed.
`KubernetesPodOperator` deletes its pod when it finishes unless
`on_finish_action` says otherwise. When the pod is gone, the same output is in
the Airflow task log (the UI, or the remote log store if one is configured),
and that is where to read it. Saying "the pod was deleted" is a finding; an
empty `kubectl logs` is not "no errors".

**Spark on Kubernetes.** Pods of one application share
`spark-app-selector=<application id>`, and `spark-role` is `driver` or
`executor`. Under the Spark operator, `sparkoperator.k8s.io/app-name=<name>`
selects them by the application's name. Read the driver first: it reports
every task failure with the exception that caused it, so one driver log
usually explains what the executor logs repeat. Executors are deleted when the
application ends, by default, while the driver pod stays in `Completed` or
`Error` until something removes it, so after the fact the driver may be all
there is.

A lost executor is the case where the log misleads most. The driver says the
executor was lost or exited, often with exit code 137; the executor's own log,
if it still exists, just stops. That is the memory limit, not a network
problem, and sizing it is [spark-job-tuning](../SPARK-JOB-TUNING/SKILL.md).

## Fetch a bounded amount

```bash
# one pod, the window you were given
kubectl --context "$CTX" -n "$NS" logs "$POD" --since=30m --timestamps
# every replica, each line prefixed with its pod and container
kubectl --context "$CTX" -n "$NS" logs -l "$SELECTOR" --all-containers --prefix \
  --since=30m --timestamps --tail=-1
# the container that died: the cause of a restart is here
kubectl --context "$CTX" -n "$NS" logs "$POD" -c "$CONTAINER" --previous --timestamps --tail=500
```

Every fetch is bounded by `--since` (or `--since-time` with an RFC 3339 time,
for an incident at a known moment) or `--tail`. With `-l`, `kubectl` returns
only the last 10 lines of each pod unless `--tail` is set, which looks like a
quiet log and is not; set `--tail=-1` together with `--since`. `--timestamps`
adds the time the container runtime recorded each line, which is what first
and last occurrence are counted from when the application's own format has no
time.

Never use `-f`. A followed log does not end, so the command never returns and
the session hangs on it.

`kubectl logs` reads only what the node still holds. The kubelet rotates
container logs by size and serves only the newest file, so on a busy pod the
window may reach back minutes, not hours. When the log starts later than the
window asked for, say so, and point to the cluster's central log store for
older lines. `--previous` reaches one container back, no further.

## Reduce to distinct errors

The commands below assume a POSIX shell (Git Bash or WSL on Windows). In
PowerShell, `Select-String -Pattern` and `Group-Object` do the same job.

Start with the lines that matter, keeping a few lines of context so a stack
trace stays attached to its message:

```bash
... | grep -E -A3 ' (ERROR|FATAL|CRITICAL) |Traceback \(most recent call last\)|Exception|Caused by:|OOM|Killed|Timeout' | head -400
```

A stack trace is many lines and one error. What identifies it is the root
cause, which sits in a different place per language:

- **Java and Scala** (Spark, the JVM half of PySpark): the last `Caused by:`
  line. The first line is usually a wrapper such as `SparkException: Job
  aborted`, the same for every failure.
- **Python** (Airflow tasks, PySpark drivers and UDFs, dbt): the last line of
  the traceback, `SomeError: message`. With chained exceptions ("During
  handling of the above exception" or "The above exception was the direct
  cause"), the first traceback is the origin and the last is what surfaced.
- **PySpark** mixes both. `Py4JJavaError` on the driver wraps a Java
  exception, so look for its `Caused by:`. An error inside a Python UDF comes
  back as `PythonException` carrying a Python traceback from the executor.

Then count by shape, not by text. Two lines that differ only in an id, a
number or a host are the same error, and counting them apart turns one
problem into fifty:

```bash
... | grep -E 'Caused by:|^[A-Za-z_][A-Za-z0-9_.]*(Error|Exception): ' \
    | sed -E 's/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/<uuid>/g; s/[0-9]+/<n>/g' \
    | sort | uniq -c | sort -rn | head -20
```

For a known shape, `grep -F` the message, take the first and last timestamp,
and note which pods it came from (the `--prefix` column). For one request
across services, `grep -F` its trace or correlation id.

Structured logs are filtered on fields instead, for example
`jq -r 'select(.level=="ERROR") | [.timestamp, .logger, .message] | @tsv'`.
Field names depend on the logging setup, so read one line first rather than
assuming them.

Probe and health-check lines (`/health`, `/ready`, `/metrics`) are noise for
this purpose; drop them. If the filter finds nothing, look at the last 20
lines before reporting "no errors": a pod that logged nothing in the window
and a pod that is stuck look the same through a filter.

## What to report

One entry per distinct error, most frequent or earliest first:

- **Error**: a one-line message and its root cause (`Caused by:` or the last
  traceback line).
- **Count**, and **first and last** time seen in the window.
- **Pods**: which ones, and whether it came from a `--previous` container.
- **Sample id**: one trace, request, task or application id, so the error can
  be followed into other services or into Airflow and the Spark UI.

Then one line of assessment that a reader can act on, such as "config error on
all replicas since 10:12, the first line after the deploy", "the driver lost
four executors to the memory limit; no application error", or "no errors in
the last 60 minutes; the log covers only the last 25 because of rotation".

When the pods are crash-looping, OOM-killed or never scheduled, more log
reading will not find the cause. Name the next thing to look at (the events,
the probe settings, the memory limit and request, the image) and stop.

## Logs carry secrets

Logs routinely contain connection strings, tokens in URLs, Spark
configuration dumps and rows of data printed while debugging. Report the shape
of an error, not the values in it: replace credentials, tokens and personal
data with a placeholder before they go into the summary, even when the user
has access to the original. A summary gets pasted into tickets and chats that
the log never would have reached. For what counts as personal data, see
[sensitive-data-handling](../SENSITIVE-DATA-HANDLING/SKILL.md).
