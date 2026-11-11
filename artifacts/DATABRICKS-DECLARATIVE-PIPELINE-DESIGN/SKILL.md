---
name: databricks-declarative-pipeline-design
description: Designing Databricks Lakeflow pipelines (Spark Declarative Pipelines, formerly Delta Live Tables) - choosing a streaming table or a materialized view for each dataset, placing expectations, building change data capture and SCD Type 2 with AUTO CDC, and ingesting files with Auto Loader, without a full refresh losing history. Use when writing or changing a Lakeflow or DLT pipeline, or when one reprocesses, drops or duplicates data unexpectedly. Not for Delta table maintenance or deciding medallion layers.
---

# Designing Lakeflow declarative pipelines

A declarative pipeline is a set of dataset definitions. The engine works out the
order from the references between them, decides how to bring each one up to
date, and keeps the state that makes the next update incremental. That is what
makes these pipelines short to write, and it is also where their defects come
from: each dataset type has its own answer to "what happens to the rows already
processed when something changes", and a pipeline that picks the wrong type runs
without error and gives wrong or missing data later.

**Names.** Databricks documents the product as *Lakeflow pipelines*. The engine
is open source as Apache Spark Declarative Pipelines, part of Spark from 4.1.
Older code and older answers call it Delta Live Tables (DLT). The Python module
is `from pyspark import pipelines as dp`; `import dlt` still works, but new code
should use `dp`. `APPLY CHANGES` became `AUTO CDC` with the same syntax. These
names have changed several times, so check a name you are unsure of in the
documentation index at `https://docs.databricks.com/llms.txt` and the page it
links, rather than answering from memory.

Neighbours:

- The semantics of a Type 2 history (validity intervals, one current row per
  key, change detection, re-run safety) are explained in
  [scd2-implementation](../SCD2-IMPLEMENTATION/SKILL.md). Here AUTO CDC builds
  that history; that skill is how to judge whether the result is right.
- Designing quarantine, a release comparison and quality scores is
  [data-quality-controls](../DATA-QUALITY-CONTROLS/SKILL.md). Expectations below
  are the mechanism a pipeline uses to apply such rules.
- Which medallion layer a dataset belongs to, and what each layer may contain,
  is [medallion-layer-boundaries](../MEDALLION-LAYER-BOUNDARIES/SKILL.md).
- Delta table maintenance (`MERGE` outside a pipeline, `OPTIMIZE`, `VACUUM`,
  clustering) is outside this skill.

## First: read the pipeline as it is

Before changing anything, establish from the project and the pipeline settings:

- **Language and API.** SQL, Python with `dp`, or Python with the older `dlt`
  module. Keep to what the pipeline already uses, and move it to `dp` as a
  change of its own rather than inside a feature.
- **Where datasets are published.** The pipeline's default catalog and schema.
  The `LIVE.` prefix and the `target` setting are legacy; a pipeline still using
  them publishes differently, so do not mix forms in one change.
- **Compute and edition.** Serverless or classic, and the product edition.
  AUTO CDC needs serverless or the Pro or Advanced edition, expectations need
  Advanced (serverless always runs Advanced, so this matters only on classic
  compute), and a materialized view refreshes incrementally only on serverless;
  elsewhere it is recomputed in full on every update.
- **How it runs.** Triggered (each update processes what is available, then
  stops) or continuous. Databricks discourages the built-in continuous mode for
  new pipelines in favour of a continuous job.
- **How it is deployed.** A bundle, Terraform or the UI. Change the definition
  where it lives, or the next deployment reverts it.
- **Which sources can be replayed.** For each source: does it still hold the
  full history (files kept in storage, a Delta table with history), or only a
  window (Kafka or Event Hubs retention, files removed by a lifecycle rule)?
  This decides what a full refresh destroys, below.

## Choose the dataset type by what must happen to old rows

| | Streaming table | Materialized view | Temporary view |
|---|---|---|---|
| Reads | Each input row once, from an append-only source | The whole query over current sources, every refresh | Inline, when a dataset that uses it is updated |
| Old rows when the query or an input changes | Stay as they were computed | Recomputed | Not stored |
| Right for | Ingestion, append-only events, the target of AUTO CDC | Joins, aggregates, anything that must reflect current inputs | Intermediate logic not worth publishing |

The question that decides it is whether a row already written must change when
something it was computed from changes. A streaming table never goes back. If
it joins events to a customer dimension, each event gets the customer
attributes as they were when the event was processed; a later correction to the
customer reaches only events processed after it. The documentation calls this
join "fast-but-wrong" when the current answer is what users expect. A
materialized view answers with the current state of every input on each
refresh, so put joins to changing dimensions and aggregates there.

The same property applies to your own changes. Fixing a bug in a streaming
table's query fixes new rows only; rows already written keep the bug until the
table is fully refreshed, which has its own cost (below). Decide which of the
two you need before editing the query, and say so in the change.

A streaming table assumes its source only appends. Structured Streaming fails
when a Delta source has an `UPDATE`, `DELETE`, `MERGE` or overwrite. The
`skipChangeCommits` read option stops the failure by ignoring those commits, so
the changes never arrive downstream. Use it only when that is what you want, for
example after a GDPR delete in a raw table. When the source carries changes that
must be applied, that is change data capture (below). The target of an AUTO CDC
flow is itself updated in place, so read it downstream through a materialized
view, not a streaming read.

```python
from pyspark import pipelines as dp
from pyspark.sql import functions as F

@dp.table(comment="Orders as delivered by the source, one row per record")
def orders_raw():
    return (spark.readStream.format("cloudFiles")
            .option("cloudFiles.format", "json")
            .option("cloudFiles.inferColumnTypes", "true")
            .load("/Volumes/main/landing/orders/"))

@dp.materialized_view(comment="Order totals per customer, current on each refresh")
def customer_order_totals():
    return (spark.read.table("orders_clean")
            .groupBy("customer_id")
            .agg(F.sum("amount").alias("total_amount")))
```

```sql
CREATE OR REFRESH STREAMING TABLE orders_raw
AS SELECT * FROM STREAM read_files('/Volumes/main/landing/orders/', format => 'json');

CREATE OR REFRESH MATERIALIZED VIEW customer_order_totals
AS SELECT customer_id, sum(amount) AS total_amount
   FROM orders_clean
   GROUP BY customer_id;
```

On serverless, a materialized view's `REFRESH POLICY` (`AUTO` by default, or
`INCREMENTAL`, `INCREMENTAL STRICT`, `FULL`) decides whether a refresh may fall
back to full recomputation. The event log records which kind each refresh was.
Check it for a large view before assuming it is cheap.

## Dataset code runs more than once

A pipeline evaluates its source code several times while planning an update,
before any data moves. A dataset function is a description of a query, not a
step that runs once. Anything with an effect therefore happens an unpredictable
number of times, or during planning with no data behind it. The documentation
names `collect()`, `count()`, `toPandas()`, `save()`, `saveAsTable()`,
`start()` and `toTable()` as methods never to use in dataset code. The same goes
for calling an API, writing a file or logging row counts from inside a
definition. To write outside the pipeline, use a sink; to compute a value a
definition depends on, do it in configuration or a parameter, not in a query.

## Full refresh discards what the source no longer holds

A full refresh of a streaming table discards all its data and its checkpoint,
then reads the source from the beginning. It recovers exactly what the source
still holds. If a Kafka topic keeps seven days, a full refresh of a table
holding two years of events leaves seven days. Files removed by a lifecycle
rule are gone the same way. Nothing warns about this; the update succeeds.

Two consequences:

- **Never start a full refresh without confirming it**, naming each streaming
  table it covers and what its source can replay. Prefer refreshing one
  dataset over the whole pipeline. This applies to a "reset" button in the UI
  as much as to an API call.
- **Protect tables whose source cannot be replayed** with the table property
  `pipelines.reset.allowed` set to `false`, which controls whether a full
  refresh is allowed for that table. It turns an accident into a refused
  operation. Add it when the table is created, not after the first incident.

```sql
CREATE OR REFRESH STREAMING TABLE clicks_raw
TBLPROPERTIES ('pipelines.reset.allowed' = 'false')
AS SELECT * FROM STREAM(kafka_clicks);
```

```python
@dp.table(table_properties={"pipelines.reset.allowed": "false"})
def clicks_raw():
    ...
```

A streaming source that falls further behind than the Delta source's retention
fails with a missing-file error and can only be recovered by a full refresh. A
streaming table that is paused or failing for days is therefore a data-loss
risk, not only a freshness one.

## Expectations: decide who pays for a bad record

An expectation is a named SQL boolean condition on a dataset. What happens to a
row that fails it is the decision that matters:

| Action | SQL | Python | A failing row | Metrics |
|---|---|---|---|---|
| warn (default) | `EXPECT (cond)` | `@dp.expect` | Written to the target | Recorded |
| drop | `EXPECT (cond) ON VIOLATION DROP ROW` | `@dp.expect_or_drop` | Not written | Count recorded |
| fail | `EXPECT (cond) ON VIOLATION FAIL UPDATE` | `@dp.expect_or_fail` | The update fails and its transaction rolls back | Not recorded |

`expect_all`, `expect_all_or_drop` and `expect_all_or_fail` take a dictionary
of rules, which lets the rules live in configuration rather than in decorators.

Choose by consequence, not by severity of wording:

- **warn** when downstream can tolerate the record and you want to measure how
  often it happens. It is also the only way to start a new rule on live data
  without changing what is published.
- **drop** when the record is useless downstream and losing it is acceptable.
  A dropped row is not stored anywhere; only its count is. If anyone will need
  to see which records failed and why, dropping is the wrong action.
- **fail** when a single failing record means the whole batch is wrong: a null
  key in a CDC feed, a file that does not match the agreed structure. A fail
  stops the pipeline for everyone, so do not use it for record-level content
  problems a source owner fixes one at a time.

When failing records must be kept and reported, the documented pattern is a
quarantine flag: the rules stay warn-level expectations, one dataset adds
`is_quarantined` as the negation of all rules combined, and two views split it
into valid and quarantined rows. How to give each quarantined record a reason
and resolve it on a passing re-run is in
[data-quality-controls](../DATA-QUALITY-CONTROLS/SKILL.md).

```sql
CREATE OR REFRESH STREAMING TABLE orders_clean (
  CONSTRAINT order_id_present EXPECT (order_id IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT amount_positive  EXPECT (amount > 0) ON VIOLATION DROP ROW,
  CONSTRAINT fits_schema      EXPECT (_rescued_data IS NULL)
)
AS SELECT * FROM STREAM(orders_raw);
```

Conditions are plain SQL: no Python functions, external calls or subqueries.
Expectations are not supported on `AUTO CDC FROM SNAPSHOT`; check those rows on
a view before the flow.

Metrics for warn and drop are in the pipeline event log, in `flow_progress`
events:

```sql
SELECT timestamp,
       details:flow_progress:data_quality:expectations
FROM event_log('<pipeline-id>')
WHERE event_type = 'flow_progress';
```

A rule nobody reads is not a control. If the project has no alert on these
metrics, say so when adding a warn-level rule.

## Change data capture with AUTO CDC

A change feed (inserts, updates and deletes from a source database, keyed and
ordered) cannot be applied correctly by appending it, and a hand-written `MERGE`
in a pipeline has to solve out-of-order events, deletes and history itself.
AUTO CDC does that from a declaration. Its target is a streaming table that you
create first, with no query of its own.

```sql
CREATE OR REFRESH STREAMING TABLE customers_history;

CREATE FLOW customers_history_cdc AS AUTO CDC INTO customers_history
FROM STREAM(customers_changes)
KEYS (customer_id)
APPLY AS DELETE WHEN op = 'DELETE'
SEQUENCE BY STRUCT(changed_at, change_seq)
COLUMNS * EXCEPT (op, change_seq)
STORED AS SCD TYPE 2
TRACK HISTORY ON * EXCEPT (last_login_at);
```

```python
dp.create_streaming_table("customers_history")

dp.create_auto_cdc_flow(
    target="customers_history",
    source="customers_changes",
    keys=["customer_id"],
    sequence_by=F.struct("changed_at", "change_seq"),
    apply_as_deletes=F.expr("op = 'DELETE'"),
    except_column_list=["op", "change_seq"],
    stored_as_scd_type=2,
    track_history_except_column_list=["last_login_at"],
)
```

What each part is protecting against:

- **`SEQUENCE BY`** is the order of changes per key, and the only one AUTO CDC
  trusts. Arrival order is not used, so a late event cannot overwrite a newer
  one. The column must be sortable and never `NULL`: `NULL` sequencing values
  are not supported, so reject them with a fail expectation on a view in front
  of the flow rather than letting them reach it. When two changes to one key can
  share a timestamp, add a tie-breaker in a `STRUCT`, as above; without one,
  which change wins is undefined.
- **Type 1 or Type 2.** Type 1 keeps the latest state. Type 2 keeps every
  version and adds `__START_AT` and `__END_AT`; the current version has
  `__END_AT` null. Choose Type 2 only when someone needs past states.
- **`TRACK HISTORY ON`** (Python `track_history_column_list` or
  `track_history_except_column_list`) limits which columns open a new version.
  Leave a column that changes constantly and means nothing historically, such as
  a last-login time, out of it. Otherwise every change to it creates a version
  and the history fills with noise.
- **Deletes.** `APPLY AS DELETE WHEN` turns matching events into deletes, which
  close the current version in Type 2. Deleted keys are remembered for
  `pipelines.cdc.tombstoneGCThresholdInSeconds` (two days by default), so an
  older event arriving late does not bring the row back. If events can arrive
  later than that, raise it. `APPLY AS TRUNCATE` is supported for Type 1 only.
- **Partial updates.** When the feed sends only changed columns and nulls for
  the rest, `IGNORE NULL UPDATES` (Python `ignore_null_updates=True`) keeps the
  existing values instead of overwriting them with nulls. Do not set it when a
  null in the feed really means the value was cleared.

When the source provides periodic full snapshots instead of change events, use
`AUTO CDC ... FROM SNAPSHOT` (Python `create_auto_cdc_from_snapshot_flow`). It
works out the changes between snapshots.

After the first run on real data, check the result against the invariants in
[scd2-implementation](../SCD2-IMPLEMENTATION/SKILL.md): at most one version per
key with `__END_AT` null, no overlapping intervals per key. AUTO CDC maintains
them when its inputs meet the contract above. A sequencing column that is not
truly ordered breaks them without any error.

## Ingesting files with Auto Loader

Auto Loader is the `cloudFiles` streaming source; in pipeline SQL it is
`STREAM read_files(...)`. It records which files it has processed in the
stream's checkpoint, so each file is processed exactly once. A pipeline manages
the schema location and checkpoint itself. A full refresh clears that state,
and every file still in the directory is read again. That is correct when the
directory keeps everything and loses data when it does not.

Schema is where Auto Loader surprises people:

- **Types.** For JSON, CSV and XML every column is inferred as a string unless
  `cloudFiles.inferColumnTypes` is `true`. Pin the types you depend on with
  `cloudFiles.schemaHints`, such as `"amount decimal(18,2), order_ts timestamp"`,
  so that inference on an odd first file cannot decide them.
- **New columns.** `cloudFiles.schemaEvolutionMode` decides what a new column
  does:

  | Mode | A new column |
  |---|---|
  | `addNewColumns` (default without a schema) | Is added to the schema; the stream fails once and continues with it after a restart |
  | `rescue` | Never changes the schema; the data goes to `_rescued_data` and the stream does not fail |
  | `failOnNewColumns` | Stops the stream until the schema or the file is changed |
  | `none` (default when you provide a schema) | Is ignored |

  The `addNewColumns` failure is by design. A production pipeline retries and
  continues, so do not treat it as an incident or "fix" it by switching modes.
  The dangerous default is `none`: once a schema is given, a new column in the
  source is dropped silently. Choose the mode deliberately and write the reason
  next to it.
- **`_rescued_data`** holds values that did not fit the schema (wrong type,
  missing column, different case), with the source file path. A warn
  expectation `_rescued_data IS NULL` turns it into a metric; without one,
  malformed data is ingested and nobody looks.

File discovery lists the directory by default. Databricks recommends file
notification mode with file events for most workloads, because listing a large
directory on every update becomes the slowest part of the pipeline.

## What this skill changes

This skill writes pipeline source code. Running it is separate:

- **Validate and development updates** on a development pipeline or target are
  how a change is checked. Run them if the project lets the agent; otherwise
  hand over the steps.
- **Full refresh, production updates, and changes to pipeline settings**
  (compute, edition, schedule, mode, catalog or schema) only with the user's
  confirmation each time, stating what each one affects.
- **Table properties that protect data**, such as `pipelines.reset.allowed`, are
  never removed to make an operation go through.

## Verify before handing over

1. Run a validate update. It checks every definition and the dependency graph
   without processing data, and catches most reference and syntax errors.
2. Run a development update on representative input. In the event log, check
   expectation metrics and, for materialized views, whether refreshes were
   incremental.
3. Run the same update again with no new input. Streaming tables must not gain
   rows; an AUTO CDC target must not change.
4. For AUTO CDC, run the invariant queries above, and feed one key an
   out-of-order pair of changes to confirm the later `SEQUENCE BY` value wins.
5. Report what was verified, on which compute, and what was not: a change that
   was only validated has not processed a row.
