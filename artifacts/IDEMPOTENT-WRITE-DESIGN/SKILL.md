---
name: idempotent-write-design
description: Making a pipeline write safe to run again - the unit of work and its deterministic key, overwrite of a window or merge by key instead of a blind append, atomic delete+insert, the sources of non-determinism that make two runs differ, concurrent runs of one window, and a run-twice test with a row count and an overflow-free checksum that proves the result. Engine-agnostic SQL, applied to dbt, Airflow and Spark. Use when writing or reviewing a load, transformation or task that may be retried, repaired, re-run by hand or backfilled, or when a re-run has duplicated or lost rows.
---

# Idempotent writes

A write is idempotent when running it twice with the same input leaves the same
state as running it once. Pipelines need this because they run things twice all
the time: an orchestrator retries a failed task, someone repairs a run, a backfill
reprocesses last month, a queue redelivers a batch. A write that is not
idempotent does not fail on the second run. It succeeds and leaves duplicates, a
half-empty partition or a quietly changed total, and nobody hears about it until a
number in a report stops matching.

This skill covers how to design the write so that a second run is harmless, and
how to prove it with a test rather than an argument.

Idempotent is not the same as reproducible. Idempotency promises that re-running
a window *with the same input* changes nothing. Whether re-running last March
today gives what last March's run gave depends on whether the input is still what
it was then. That is the backfill question, and it starts where this one ends.

Neighbours:

- Which dbt incremental strategy and `unique_key` to choose, late-arriving rows
  and schema drift: [dbt-incremental-strategy](../DBT-INCREMENTAL-STRATEGY/SKILL.md).
  The watermark traps in an incremental model are in
  [dbt-layer-boundaries](../DBT-LAYER-BOUNDARIES/SKILL.md).
- Which write mode each bronze, silver and gold layer uses:
  [medallion-layer-boundaries](../MEDALLION-LAYER-BOUNDARIES/SKILL.md#idempotent-transitions).
- A history table that closes and opens versions: [scd2-implementation](../SCD2-IMPLEMENTATION/SKILL.md).
- Retries and repairs of a Databricks job: [databricks-job-design](../DATABRICKS-JOB-DESIGN/SKILL.md).
- Tracing duplicates that already reached a report: [data-incident-tracing](../DATA-INCIDENT-TRACING/SKILL.md).

## First: name the unit of work and what the run writes

Read the code and the orchestration before changing anything, and establish:

- **The unit of work.** What one run is responsible for: a date or hour window,
  a batch id, a set of files, a list of keys. Idempotency is defined per unit, so
  if you cannot say what the unit is, the write cannot be made safe yet.
- **Where the unit comes from.** It should arrive as a parameter (the
  orchestrator's data interval, a job parameter, a batch id). If the code works it
  out from the clock (`now()`, `current_date - 1`, `datetime.today()`) or from the
  target (`max(updated_at)` of the table it writes), a retry tomorrow processes a
  different unit than the run it retries.
- **The key of each output row.** The columns that identify a row, unique in
  practice and not only in the documentation. A key the code generates at run
  time (`uuid()`, a sequence, an identity column, `current_timestamp`) is new on
  every run, so the second run cannot recognise the first run's rows.
- **How each target is written.** Append, overwrite of a partition or window,
  merge on a key, or full rebuild. Note every target, including log tables,
  files and API calls, not only the main table.
- **Whether two runs of the same unit can overlap**: retries with no concurrency
  limit, a manual run started while the scheduled one is still going.

## Choose how the write replaces its unit

| Write | Use when | What makes it safe to re-run |
|---|---|---|
| Overwrite the unit | The unit maps onto a partition or a filterable window | The window is recomputed from the input, whatever it held before |
| Merge by key | Rows of a unit are updated in place, or units overlap | A replayed row updates its own key instead of adding a second one |
| Full rebuild | The table is small enough to rebuild every run | There is no previous state to depend on |
| Append with a record of what landed | Events that are never updated and too large to overwrite | A unit already recorded as loaded is skipped |

A plain append is the one write that is never safe on its own. It is correct on
the first run, and the first retry doubles the rows.

Overwrite and merge differ in one way that is easy to miss. Overwrite makes the
window match the input exactly, so a row that disappeared from the source, or a
row that an earlier buggy run wrote, is gone after the re-run. Merge only touches
keys that are in the input, so those rows stay. When a re-run is meant to repair
a window, overwrite repairs it and merge does not.

### Delete and insert must be one atomic step

Overwrite by window is often written as a delete followed by an insert. Between
the two statements the window is empty. If the run fails there, the window stays
empty until someone notices, and every reader in the meantime sees the data as
missing. A retry would fix it, if there is one; a failure that exhausts retries
leaves the hole in production.

So the pair has to commit together:

```sql
BEGIN;
DELETE FROM fct_orders
WHERE order_date >= :window_start AND order_date < :window_end;

INSERT INTO fct_orders (order_id, order_date, customer_id, amount, status)
SELECT order_id, order_date, customer_id, amount, status
FROM stg_orders
WHERE order_date >= :window_start AND order_date < :window_end;
COMMIT;
```

The window is half-open (`>= start AND < end`), and both statements use the same
predicate. `BETWEEN` includes both ends, so a row on the boundary belongs to two
windows and is written by both. A delete that covers less than the insert leaves
duplicates; one that covers more deletes rows no run will write back.

Whether this is really atomic depends on the engine, and the differences are
where the bugs live:

- **PostgreSQL**: `DELETE`, `INSERT`, `TRUNCATE` and DDL all roll back together
  inside one transaction.
- **Snowflake**: `DELETE`, `INSERT`, `MERGE` and `TRUNCATE` are DML and stay in
  the transaction. A DDL statement (`CREATE OR REPLACE`, `ALTER`) commits the
  open transaction implicitly, so a `CREATE OR REPLACE` of a staging table between
  the delete and the insert commits the delete on its own.
- **MySQL**: `TRUNCATE` and DDL commit implicitly, so truncate-then-load is
  never one transaction there.
- **BigQuery**: wrap the statements in `BEGIN TRANSACTION; ... COMMIT TRANSACTION;`,
  or replace the window in one `MERGE` with `ON FALSE` and a `WHEN NOT MATCHED BY
  SOURCE AND <window predicate> THEN DELETE` branch, which is what dbt's
  `insert_overwrite` does there.
- **Spark on plain Parquet or ORC files**: an overwrite deletes the old files and
  then writes new ones, with no commit protocol around the two. A failed job can
  leave a partition empty or half written. Delta Lake (`replaceWhere`) and Iceberg
  (`overwritePartitions`, `INSERT OVERWRITE`) commit the replacement as one
  snapshot, which is the main reason to use a table format for anything that is
  re-run.

Check how wide the overwrite really is. With Spark's default
`spark.sql.sources.partitionOverwriteMode=static`, `mode("overwrite")` replaces
the whole table, not the partitions in the batch; the details are in
[medallion-layer-boundaries](../MEDALLION-LAYER-BOUNDARIES/SKILL.md#idempotent-transitions).

### Merge needs a key that is unique in the input

```sql
MERGE INTO fct_orders t
USING (
    SELECT order_id, customer_id, amount, status, updated_at
    FROM (
        SELECT s.*,
               ROW_NUMBER() OVER (
                   PARTITION BY order_id
                   ORDER BY updated_at DESC, source_file DESC, source_line DESC
               ) AS rn
        FROM stg_orders s
        WHERE s.updated_at >= :window_start AND s.updated_at < :window_end
    ) ranked
    WHERE rn = 1
) s
ON t.order_id = s.order_id
WHEN MATCHED THEN UPDATE SET
    customer_id = s.customer_id, amount = s.amount,
    status = s.status, updated_at = s.updated_at
WHEN NOT MATCHED THEN INSERT (order_id, customer_id, amount, status, updated_at)
    VALUES (s.order_id, s.customer_id, s.amount, s.status, s.updated_at);
```

The deduplication is not decoration. When two input rows carry a key that is
already in the target, BigQuery, PostgreSQL and Delta Lake stop the `MERGE` with
an error, and Snowflake does too under its default `ERROR_ON_NONDETERMINISTIC_MERGE`. When
the key is new, there is no target row to conflict over: both input rows go
through `WHEN NOT MATCHED` and both are inserted, with no error. So the first run
of a batch with duplicates writes them, and only a later run that touches those
keys fails. Equally quiet is a `ROW_NUMBER()` ordered only by `updated_at`: it
picks an arbitrary row whenever two versions share a timestamp, so two runs over
the same input can keep different rows. The tiebreaker has to reach a column
combination that is unique, such as the source file and line or the source's own
sequence number.

A merge also does not stop at the target. If the target declares a primary key,
check whether the engine enforces it. PostgreSQL does. Snowflake and BigQuery
accept the declaration and do not enforce it, so a duplicate written by some
other path stays there, and only a test catches it.

### Append, but record what landed

For an event stream too large to overwrite, keep a record of each unit loaded (a
file name, a batch id, a Kafka offset range) and skip a unit already recorded. Write
the record in the same transaction as the data. Recorded first, a failure after
it marks a unit loaded that never landed; recorded after a separate commit, a
failure between the two loads the unit again on retry.

The same applies to side effects that cannot be overwritten: a file sent to a
partner, a notification, a call to a paid API. Record the unit, check the record
before acting, and accept that between acting and recording a crash still
repeats the action once. Where the receiver accepts an idempotency key, send one
derived from the unit, so it can discard the repeat.

## Remove what makes two runs differ

A run that writes by key or by window can still produce a different result each
time if its own output is not a function of its input. Look for these:

- **Generated keys.** `uuid()`, `gen_random_uuid()`, sequences and identity
  columns give each run new keys, so a merge on them matches nothing and inserts
  everything again. Derive the key from the business columns instead, by using
  them directly or by hashing them. A hash key needs a separator and a marker for
  `NULL`, or `('ab', 'c')` and `('a', 'bc')` collide and a `NULL` nulls the whole
  hash; [scd2-implementation](../SCD2-IMPLEMENTATION/SKILL.md) shows the safe form.
- **The clock inside the logic.** `current_timestamp` written into a column only
  for audit (`loaded_at`) is fine, as long as no key, filter or join reads it. In
  a filter (`WHERE event_ts > now() - interval '1 day'`) it makes the window
  depend on when the run started, so a retry an hour later reads a different
  hour. Take times from the data and windows from parameters.
- **Ordering that is not total.** `ROW_NUMBER()` without a unique tiebreaker,
  `LIMIT` without `ORDER BY`, `FIRST_VALUE` over ties, `ARRAY_AGG` or
  `STRING_AGG` without an `ORDER BY` inside. Each returns whatever order the
  engine happened to read in, and parallel engines read in a different order
  each run.
- **Floating-point aggregates.** `SUM` over `FLOAT` or `DOUBLE` depends on the
  order of addition, which changes with parallelism, so the last digits can
  differ between two correct runs. Use `DECIMAL`/`NUMERIC` for money and counts.
  Where a float is unavoidable, round it before comparing or hashing.
- **Bucket assignment that changes.** Hash partitioning or bucketing into `N`
  buckets moves every row when `N` changes, and random assignment
  (`rand()`, `repartition(n)` with no columns) moves them on every run. If a
  later step overwrites "bucket 3", it overwrites different rows each time.
- **Input that is still moving.** A query on a live source table sees rows that
  committed between the first run and the retry. That is a different input, not a
  broken write, but it makes a run-twice test fail for the wrong reason. Freeze
  the input for the test (a snapshot, a time-travel query, a fixed staging copy).

## A watermark read from the target is not a parameter

```sql
-- The only incremental filter: the trap
WHERE created_at > (SELECT max(created_at) FROM fct_orders)
```

This makes the run's input depend on the state of the table it is about to
write. There is no window to re-run: after a partial write the maximum has
already moved, so the retry skips what the failed run did not finish. A row that
commits late with an older `created_at` lands below the maximum and is never
loaded. A backfill of an earlier period is impossible without editing the query.
Keep a watermark if the source needs one, but take it from a parameter or a state
table written together with the data, and read a lookback overlap that the
merge or overwrite absorbs. [dbt-layer-boundaries](../DBT-LAYER-BOUNDARIES/SKILL.md)
covers the `>` versus `>=` and empty-table traps of the same filter in dbt.

## Two runs of the same unit at once

Everything above assumes the runs of a unit happen one after another. Two runs of
the same window at the same time can each delete, then each insert, and leave the
rows twice, even though each run on its own is idempotent. A merge has the same
race: both runs see the key as missing and both insert it.

Serialise runs of the same unit rather than trying to make concurrent writes
safe. In Airflow, `max_active_runs=1` on the DAG (or a pool of size one for the
task) keeps a manual run from overlapping the scheduled one. On Databricks,
`max_concurrent_runs` does the same for a job. In PostgreSQL,
`SELECT pg_advisory_xact_lock(hashtext('fct_orders'))` at the start of the
transaction makes a second run wait for the first. Where the engine enforces a
unique constraint on the key, keep it as a backstop that turns a race into an
error.

## Applying it

### dbt

- `materialized='incremental'` with no strategy and no `unique_key` appends on
  most adapters. Declare the strategy, and for `merge` the `unique_key`, and
  check that the key is unique in each batch.
- `insert_overwrite` (BigQuery, Spark, Databricks) and `delete+insert` replace
  the unit and are the overwrite pattern above. Read the compiled statements in
  `target/run/` to see whether the adapter wraps them in a transaction on your
  warehouse, rather than assuming it.
- `microbatch` (dbt 1.9 and later) makes the unit explicit: each batch of the
  model's `event_time` is replaced as one atomic unit with the adapter's
  replacement mechanism, can be retried on its own with `dbt retry`, and is
  backfilled with `--event-time-start` and `--event-time-end`.
- `{{ run_started_at }}` and `current_timestamp` in a key or filter are the clock
  problem above.

### Airflow

- Read the window from the run, `{{ data_interval_start }}` and
  `{{ data_interval_end }}` in a template or the same keys in the task context,
  and pass both into the SQL as bound parameters. A retry, a clear and a backfill
  of that run then process the same window.
- In Airflow 3 a run triggered by an asset event, or manually without a logical
  date, can have no logical date and no data interval. A task that falls back to
  the clock in that case is no longer idempotent; fail instead, or require the
  window as a DAG param.
- Retries are only safe on a task whose write is. Turning `retries` on for a task
  that appends is how a transient failure becomes duplicated data.

### Spark

- Overwrite the batch's partitions, not the table: dynamic partition overwrite,
  or `replaceWhere` with the exact window on Delta.
- `MERGE INTO` on Delta or Iceberg for keyed updates, with the source
  deduplicated first, for the same reason as in SQL.
- For Structured Streaming, the checkpoint plus an idempotent sink is what gives
  exactly-once results; see [spark-streaming-query-design](../SPARK-STREAMING-QUERY-DESIGN/SKILL.md).

## Prove it by running it twice

The argument that a write is idempotent is easy to get wrong, so test it on a
non-production target with a frozen input. Three runs cover the cases that occur:

1. **Re-run after success.** Run the window, record its row count and checksum,
   run the same window again, compare. Nothing may change.
2. **Re-run after a failure mid-write.** Make the write fail between its
   statements (a failing row, a cancelled query, a fault injected in a test),
   check that the window still holds what it held before the run, then re-run
   and check it now matches the result of test 1. This is the case retries
   actually face, and the one an atomicity bug shows up in.
3. **Re-run an older window after a newer one.** Run window W, then W+1, then W
   again. W must match and W+1 must not change. This catches a delete or merge
   that reaches past its own window.

Compare a row count and an order-independent checksum over the business columns,
and also check that the key is still unique. Leave out columns that differ by
design between runs (`loaded_at`, `run_id`, `_ingested_at`), or a correct write
fails the test; and test that they are the only ones. The checksum has to survive
large tables and count a duplicated row, which the obvious versions do not: a
`SUM` of 64-bit hashes overflows, an `XOR` of hashes cancels a row that appears
twice, and `md5(string_agg(...))` without an `ORDER BY` inside changes with scan
order. Per-engine queries that avoid all three, and a query that finds the rows
that differ when the checksums do not match, are in
[references/verification.md](references/verification.md).

Run this as a repeatable test, not a one-off: in CI against a fixture, or as a
scheduled check that re-runs a recent window into a scratch schema.

## What to report

When reviewing or changing a write, state:

- the unit of work and where it comes from (parameter, clock, or target);
- the key and whether it is unique in the input;
- the write pattern, whether it is atomic on this engine, and how wide it reaches;
- the sources of non-determinism found and what replaced each;
- whether runs of one unit can overlap and what serialises them;
- the result of the three run-twice tests, with the counts and checksums, or
  that they were not run and why.
