---
name: backfill-planning
description: Planning and running a backfill or replay that rewrites history - loading a new model's past, reprocessing after a logic fix, re-deriving a table from raw - so that it changes only the window it was meant to, cannot be half-applied, and is reconciled and announced afterwards. Covers whether the input still exists and still means what it did, the exact window, a snapshot to roll back to, one-partition dry runs, bounded and resumable execution on isolated compute, pinned code, the downstream models that must be rebuilt, and the before/after reconciliation. Applied to dbt, Airflow, Databricks and Spark. Use when asked to backfill, reprocess, replay or reload a historical period, or to plan one after a bug fix.
---

# Backfills and replays

A backfill re-runs a pipeline over a period it has already processed, or over a
period before it existed. It is the routine operation most likely to change
numbers people have already read: last quarter's revenue in a board deck, a
figure a finance team closed, a metric in a contract. Done well it is boring and
repeatable. Done carelessly it double-counts, leaves a mart that disagrees with
its own source, reads inputs that have changed since, or starves the production
schedule of compute, and nobody can say afterwards which numbers moved and why.

This skill plans the run so that it rewrites only the window it was meant to,
can be stopped and resumed without damage, can be rolled back, and ends with a
reconciliation that says what changed.

It assumes the write it re-runs is idempotent: running a window twice leaves what
running it once leaves. Making a write idempotent, and the run-twice test that
proves it, are [idempotent-write-design](../IDEMPOTENT-WRITE-DESIGN/SKILL.md). A
backfill of a write that is not idempotent multiplies the data it was meant to
fix, so that check comes first and is not repeated here.

Neighbours:

- Finding out what went wrong before deciding to backfill:
  [data-incident-tracing](../DATA-INCIDENT-TRACING/SKILL.md). It stops at the
  report on purpose; this skill picks up from there.
- Choosing a dbt incremental strategy and the periodic full refresh that repairs
  drift: [dbt-incremental-strategy](../DBT-INCREMENTAL-STRATEGY/SKILL.md).
- Retry, repair and concurrent runs of a Databricks job:
  [databricks-job-design](../DATABRICKS-JOB-DESIGN/SKILL.md).
- Full refresh of a Lakeflow (DLT) pipeline, which can discard history the source
  no longer holds:
  [databricks-declarative-pipeline-design](../DATABRICKS-DECLARATIVE-PIPELINE-DESIGN/SKILL.md#full-refresh-discards-what-the-source-no-longer-holds).
- Restarting a streaming query from an earlier offset:
  [spark-streaming-query-design](../SPARK-STREAMING-QUERY-DESIGN/SKILL.md#the-checkpoint-is-the-querys-identity).
- How far back bronze can be replayed:
  [medallion-layer-boundaries](../MEDALLION-LAYER-BOUNDARIES/SKILL.md).
- Reviewing the output of the run once it is done:
  [pipeline-output-review](../PIPELINE-OUTPUT-REVIEW/SKILL.md).

## What this skill changes

Planning is read-only: reading code, orchestration, lineage and the current
state of the tables. The run itself rewrites production history, so do not
start it without the user's go-ahead on the written plan, even when the request
says "backfill prod": the request names the goal, and the plan is what the user
has not seen yet. The plan therefore carries predicted numbers, and its first
approved step is the one-unit dry run into a scratch schema or a clone, never a
production table. Report the measured numbers from that unit and wait for the
go-ahead again before the full run when they differ from the prediction.

## First: say what the backfill is for

The reason decides almost everything else, so write it down in one sentence
before planning:

- **A new model's history.** Nothing has been reported from the target yet. The
  risk is load on production and an input that no longer goes back far enough,
  not changed numbers.
- **A logic fix.** The output for the window is wrong and will change. Every
  number that changes was reported before, so the reconciliation and the
  announcement matter most.
- **Missing or late input.** A source delivered late, or a run was skipped. The
  window should grow, and nothing already present should change. Any other
  change is a defect in the backfill.
- **A replay from raw**, after a schema change or a move to a new platform. The
  output should match what was there, except where a known difference was
  intended.

Each of these predicts what the reconciliation will find. Write the prediction
down too: "only `net_amount` changes, only for orders with a refund, between
2026-03-01 and 2026-05-31". A backfill whose result matches its prediction is
done. One that changes something else is not, however green the run was.

## Can the input still be read, and does it still mean the same?

A backfill reads the input as it is now, not as it was when the window first
ran. Check, for each source of the job:

- **Retention.** Does the source still hold the whole window? Kafka topics,
  staging tables with a TTL, landing buckets with a lifecycle rule, CDC logs and
  API endpoints that serve the last N days all forget. A full rebuild of a table
  whose source has forgotten half its history writes a table with half its
  history, and reports success.
- **Rows that were changed or deleted at the source since.** An operational
  table holds today's state. Re-deriving last March from it gives last March as
  it looks now, which may be what a logic fix wants and is rarely what a "replay"
  promises.
- **Dimensions joined as they are today.** A fact re-processed with today's
  customer region, product category or exchange rate is attributed differently
  from the original run. If the history must keep the attribution it had, the
  join has to be as-of the fact's date against a history table
  ([scd2-implementation](../SCD2-IMPLEMENTATION/SKILL.md)), not against the
  current dimension.
- **Snapshots cannot be backfilled.** A dbt snapshot, or any job that records the
  state of a source at run time, captured what it saw on each run. Re-running it
  now records only today's state. Lost snapshot history is gone unless a copy of
  the table exists.
- **The clock in the code.** A job that derives its window from `now()` or from
  the target's `max()` processes today, not the window you asked for. That is an
  idempotency defect and has to be fixed first; see
  [idempotent-write-design](../IDEMPOTENT-WRITE-DESIGN/SKILL.md#first-name-the-unit-of-work-and-what-the-run-writes).

If the input is gone or has changed meaning for part of the window, say so in the
plan and narrow the window, rather than letting the backfill overwrite good
history with worse.

## Scope: the window, the unit and the targets

- **The window**, as a half-open range of the column the job partitions by:
  `>= 2026-03-01 AND < 2026-06-01`. Say whether it is an event date or a load
  date; the two give different rows for the same dates.
- **The unit** the run is chunked into: a day, an hour, a partition, a batch.
  It should be the unit the job already processes on a normal run, so that each
  chunk is an ordinary, already tested run with a different parameter.
- **The targets**: the table the job writes, and every model downstream of it
  that reads the window. Backfilling a base table and leaving the marts built
  from it untouched leaves the marts disagreeing with their own source. In dbt,
  `dbt ls --select <model>+ --resource-type model` lists them; column-level
  impact is in [dbt-column-lineage](../DBT-COLUMN-LINEAGE/SKILL.md).

Downstream incremental models need their own backfill of the same window. A
normal incremental run reads only new rows from its parent, so it does not pick
up history that the backfill rewrote in the parent; the mart keeps the old
numbers until it is rebuilt for that window or fully refreshed. Downstream tables
that are rebuilt in full on every run (views, `table` materializations) only need
to run once, after the base backfill has finished.

Downstream also includes what is outside the pipeline: extracts and reverse-ETL
syncs that pushed the old numbers somewhere else, dashboards with cached
extracts, and ML features computed from the window. List them; the announcement
names them.

## Snapshot before you write

Take a copy of every target's window plus one unit on each side of it, or of the
whole table when it is small, before the first write. It is the rollback, and it
is the "before" side of the reconciliation, whose first question compares the
units just outside the window, so a copy of the window alone cannot answer it.
Time travel, clones and table versions cover the whole table; a copy you make
yourself has to include those neighbours, and when the table is too large for
even that, record the row count and checksum of every unit in the table before
the first write as the baseline. Without it, the only way to answer "what did this number used to
be?" is a report someone exported.

- **Snowflake**: a zero-copy `CREATE TABLE ... CLONE`, or `AT (TIMESTAMP => ...)`
  while within the table's Time Travel retention, which is one day by default.
- **BigQuery**: `CREATE SNAPSHOT TABLE`, or `FOR SYSTEM_TIME AS OF` within the
  dataset's time travel window, seven days by default.
- **Delta Lake and Iceberg**: note the table version before the run. `RESTORE`
  (Delta) or a rollback to the snapshot (Iceberg) returns to it, as long as
  `VACUUM` or snapshot expiry has not removed the files.
- **PostgreSQL and others without time travel**: `CREATE TABLE ... AS SELECT` of
  the window and one unit either side into a backup schema.

Record where the snapshot is and when it can be dropped.

## Dry-run one unit, and predict the result

Before scaling out, run one unit into a scratch schema or a clone, from the same
code and the same input the backfill will use, and reconcile it against the
current target for that unit and against the source. Pick a unit where the change
is expected, and one where nothing should change, if the window has both.

The dry run answers questions that are expensive to discover halfway through: how
long one unit takes and how much compute it uses (which sets the parallelism and
the total duration), whether the output differs from the current target exactly
as predicted, and whether the input really is there for the oldest unit of the
window. Run the oldest unit, not the newest: it is the one most likely to have
lost its input.

## Run it unit by unit, bounded and resumable

Run the window as a sequence of units with a fixed limit on how many run at once,
not as one job over the whole range. A single job over six months cannot be
watched, cannot be paused without losing its work, and fails at hour five with
nothing committed, or worse, with an unknown part committed. Units of a day can
be watched, paused at any boundary, retried on their own and resumed from the
first one not done.

- **Bound the parallelism** by what the target and the source can take, not by
  how fast you want it done. Units that write different partitions of one table
  can run in parallel when the write is a partition overwrite or a merge on a
  key; units that overlap must not.
- **Keep a record of the units done**, with each unit's row count and checksum,
  in the orchestrator's run history or a small control table. Resuming means
  starting from the first unit not in it, and the counts feed the reconciliation.
- **Order the units** oldest to newest when later units read the state earlier
  ones wrote (running totals, SCD2 history, a watermark), and in any order
  otherwise.
- **Hold the scheduled runs that write the same units.** A scheduled run and a
  backfill unit writing the same window at once write it twice; see
  [idempotent-write-design](../IDEMPOTENT-WRITE-DESIGN/SKILL.md#two-runs-of-the-same-unit-at-once).
  Either pause the schedule for the duration, or keep the backfill's window
  strictly before the window the schedule writes.

## Isolate the compute

A backfill of a year is a year of production runs in a day. On shared compute it
queues behind, or in front of, the production schedule, and the first symptom is
a late dashboard. Give it its own: a separate Snowflake warehouse, a separate
BigQuery reservation or a slot cap on its project, a job cluster rather than the
shared all-purpose one on Databricks, an Airflow pool with a fixed number of
slots for the backfill's tasks. Set a statement timeout so a runaway unit fails
rather than runs for a day. Then the backfill's speed is limited by what it was
given, and production keeps what it had.

Watch the source too. A backfill that re-extracts from an operational database
reads a year of rows from a system someone else owns; run it with the same
read-only, rate-limited approach the regular extraction uses
([postgres-source-extraction](../POSTGRES-SOURCE-EXTRACTION/SKILL.md) for
PostgreSQL).

## Pin the code for the whole run

Every unit of one backfill must run the same code. If a fix is merged on day
three of a five-day backfill, the first three days of history follow one logic
and the last two another, and the result is a series with a step in it that no
source explains. Run from a tag or a commit, not a branch: a dbt project checked
out at a fixed commit, a Databricks job whose Git source is a tag, an Airflow
deployment that is not redeployed during the run. If the code has to change
mid-run, stop, and restart the backfill from its first unit with the new code.

Record the commit in the plan and in the announcement. It is the answer to "which
logic produced this history?".

## Applying it

### dbt

- **`--full-refresh` is not a window.** It drops and rebuilds the whole model from
  everything the source holds now, ignoring `is_incremental()`. It is the right
  tool only when the whole table should be rebuilt and the source still holds all
  of it. A model whose source has lost history should carry
  `full_refresh: false` in its config, which makes dbt ignore `--full-refresh`
  for that model instead of truncating history it cannot rebuild.
- **A window on an incremental model** needs the model to accept one. For
  `microbatch` (dbt 1.9 and later), `dbt run --select <model> --event-time-start
  2026-03-01 --event-time-end 2026-06-01` reprocesses exactly those batches, and
  `dbt retry` re-runs only the batches that failed. `concurrent_batches` decides
  whether batches run in parallel. How a batch is written depends on the adapter:
  on dbt-postgres it is a merge and needs a `unique_key`, so a row deleted at the
  source stays in the target after the batch is reprocessed. Read the compiled
  statement in `target/run/` before relying on a batch being replaced. For the other
  strategies, read the window from `var()` with a normal-run default and pass it
  with `--vars`, so the `is_incremental()` filter and the overwrite cover the
  same range:

  ```sql
  {% if is_incremental() %}
  where order_date >= '{{ var("backfill_start", "") or (run_started_at - modules.datetime.timedelta(days=3)).date() }}'
    and order_date <  '{{ var("backfill_end", "") or run_started_at.date() }}'
  {% endif %}
  ```

  With `insert_overwrite`, or `delete+insert` whose `unique_key` is the window
  column (the day), the window is replaced. dbt's `delete+insert` deletes only
  target rows whose key appears in the new batch, so keyed on a row id it
  behaves like `merge`: rows removed from the source for that window stay in the
  target. Even keyed on the day, a day with no rows left in the source is not
  deleted. `incremental_predicates` only narrow that delete and do not help.
- **Downstream**: `dbt run --select <model>+` after a windowed run of the base
  model rebuilds the `table` and `view` models below it, but an incremental mart
  whose filter reads only rows newer than its own maximum picks up nothing, and
  keeps the old numbers. Each downstream incremental model needs a window of its
  own: the same `--vars` or `--event-time-*` flags if it accepts them, otherwise a
  `--full-refresh` of that model when its parent still holds everything. Use
  `dbt build` rather than `dbt run`, so the tests run on the rewritten window too.

### Airflow

- Every task must take its window from the run (`data_interval_start`,
  `data_interval_end`), not from the clock; a backfill run of 2026-03-01 then
  processes 2026-03-01.
- **Airflow 3**: `airflow backfill create --dag-id <dag> --from-date 2026-03-01
  --to-date 2026-05-31` creates the runs, which the scheduler then executes like
  any other. `--to-date` is inclusive, unlike dbt's `--event-time-end`, so the
  same three months end on 05-31 here and on 06-01 there. The same is available
  from the UI. `--dry-run` lists the dates without creating anything.
  `--max-active-runs` bounds how many backfill runs run at once, independently of the DAG's own `max_active_runs`, so it does not
  stop a scheduled run from overlapping a backfill run.
- **Dates that already have a run are skipped by default.** `--reprocess-behavior`
  is `none` unless set, which creates runs only for missing dates: a logic-fix
  backfill over dates that already ran does nothing. `failed` re-runs dates whose
  run failed, `completed` re-runs dates whose run completed or failed. A DAG with
  `depends_on_past` tasks refuses `none`.
- **A re-run may use the old code.** A date that is reprocessed has its existing
  run cleared, not a new one created, and with a versioned DAG bundle (such as a
  Git bundle) a cleared run keeps the bundle version it first ran with. Without
  `--run-on-latest-version` (experimental in 3.1), a logic-fix backfill on a Git
  bundle re-runs the code it was meant to replace. Clearing runs by hand behaves
  the same way unless "run on latest version" is chosen. Local and S3 bundles are
  not versioned and always run the latest code.
- **Airflow 2**: `airflow dags backfill --start-date ... --end-date ...` runs the
  backfill inside the CLI process, so closing the terminal stops it; run it where
  it can outlive the session. To re-run dates that already succeeded, clear them
  (`airflow tasks clear --start-date ... --end-date ...`, or `--reset-dagruns` on
  the backfill).
- `catchup=True` is a backfill too, of every interval since `start_date`, started
  the moment the DAG is unpaused. Use an explicit backfill instead; see
  [airflow-dag-structure](../AIRFLOW-DAG-STRUCTURE/SKILL.md).
- A dedicated pool for the backfill's tasks is the Airflow form of isolated
  compute.

### Databricks and Spark

- Parameterize the job by the window and launch one run per unit, with
  `max_concurrent_runs` as the bound; parallel runs are safe only when they write
  disjoint windows ([databricks-job-design](../DATABRICKS-JOB-DESIGN/SKILL.md#concurrency-and-queueing)).
- Write each unit with `replaceWhere` on Delta, or with dynamic partition
  overwrite, so a unit replaces its own partitions and nothing else.
- Point the job's Git source at a tag or commit for the duration of the backfill.
- For a Lakeflow (DLT) pipeline, prefer refreshing the affected datasets over a
  full refresh of the pipeline, and check what each streaming source can still
  replay first.

## Reconcile what changed

When the last unit is done, compare the snapshot with the result, window by
window and target by target. Three questions, in this order:

1. **Did anything outside the window change?** Row counts and checksums of the
   units just before and after the window must be identical to the snapshot or
   the recorded baseline.
   A difference here is a write that reached past its window, and is a defect
   whatever else is true.
2. **Did the window change as predicted?** Compare row counts and checksums per
   unit, then, where they differ, the rows by key: which keys were added,
   removed, and changed, and in which columns. The change should fall inside the
   prediction you wrote at the start. A change outside it is either a second
   effect of the fix that nobody anticipated, or a fault in the backfill. Find out
   which before announcing anything.
3. **Do the downstream models agree with the base table again?** The total of a
   mart over the window should match the total of the table it is built from, and
   the totals people read should have moved by the amount the base table moved.

The checksum and row-diff queries for the main engines, built so they do not
overflow and count duplicated rows, are in
[idempotent-write-design/references/verification.md](../IDEMPOTENT-WRITE-DESIGN/references/verification.md).
Run them per unit (`GROUP BY order_date`) rather than over the whole window, so a
difference points at a day. For a row-by-row comparison of two large tables with
a format-aware classification of the differences, see
[migration-data-reconciliation](../MIGRATION-DATA-RECONCILIATION/SKILL.md).
Then review the output as for any run
([pipeline-output-review](../PIPELINE-OUTPUT-REVIEW/SKILL.md)).

## Tell the people who read the numbers

History that changed silently is found later, by someone comparing a new report
with an old one, and by then nobody trusts either. For a backfill that changes
reported numbers, write a short notice, before the run when the change is known
in advance and after the reconciliation with the real figures:

- what was wrong, or what was added, in one sentence;
- the window and the tables, models and dashboards affected;
- for the metrics people read, the old and the new value over the window, or the
  size of the change;
- when the change takes effect, and the commit that produced the new history;
- where the snapshot of the old values is, and until when.

Send it to the owners of the dashboards and downstream systems listed in the
scope, not only to the data team.

## What to report

The plan, before the run:

- the reason and the predicted change;
- whether the input still covers the window and still means the same, and what
  was done where it does not;
- the window, the unit, the targets and the downstream models to rebuild;
- the snapshot, which unit the dry run will use and what it should show, the
  parallelism and compute, the pinned commit, and how the schedule is held;
- the command or the runs that will execute it, for the user to approve.

After the dry run: the measured duration, counts and checksums for that unit,
compared with the prediction, before the full run starts.

After the run:

- the units done, with counts and checksums, and any that failed or were retried;
- the reconciliation result for each of the three questions, with the figures;
- the notice, if one was needed, and to whom it went;
- when the snapshot can be dropped.
