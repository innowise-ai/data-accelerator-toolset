---
name: medallion-layer-boundaries
description: Medallion (bronze, silver, gold) lakehouse layers on any platform - what each layer is for and must not contain, idempotent writes between layers, where quality checks sit, the failure modes, and when three layers are too many. Covers Microsoft Fabric, Databricks, plain Spark, and how the layers map onto dbt. Use when designing or reviewing a lakehouse's layers, deciding which layer a transformation, check or table belongs in, or refactoring a flat pipeline into layers.
---

# Medallion layer boundaries

The medallion layout splits a lakehouse into three layers: bronze holds data as it
arrived, silver holds a trustworthy version of it, gold holds what consumers read.
The names matter less than what each layer promises to its readers. A table in
silver promises that its rows are deduplicated, typed and checked; a table in
bronze promises that nothing was changed. When a table breaks its layer's promise,
the layout still looks right and stops paying for itself.

What it pays for is one property: **a logic fix is re-derived from bronze, not
re-pulled from the source.** Sources forget. An API returns only the last 90 days,
a vendor overwrites yesterday's file, an operational database updates rows in
place. If bronze kept what arrived, a bug in silver or gold costs a recompute. If
it did not, the bug costs whatever the source still remembers, and sometimes the
data is gone.

Everything below follows from protecting that property.

## Bronze: capture, not transformation

Bronze stores records as received, append-only, with metadata about the load.
It is the only copy of the source that the platform controls.

**No business logic, no filtering, no deduplication.** Any rule applied on the way
into bronze is applied forever, because bronze is what everything is re-derived
from. Filter out test orders at ingestion and a later decision that test orders
should be counted separately needs a re-pull. A rule belongs in a layer that can
be recomputed, and bronze is the one layer that cannot.

**Keep types loose.** Databricks recommends storing most bronze fields as string,
`VARIANT` or binary. A strict schema at ingestion turns an unexpected value into
a failed load or, worse, a silently nulled column, and the original value is then
unrecoverable. Casting is silver's job, where a failure can be quarantined and
retried.

**Record load metadata on every row:** the source system, the ingestion timestamp,
and the file or batch it came from (and the offset, for a stream). Without it,
"where did this bad row come from?" has no answer, a single bad delivery cannot be
removed or replayed on its own, and silver has no way to choose between two
versions of a record that arrived at different times.

```python
from pyspark.sql import functions as F

raw = (
    spark.read.format("json").load(landing_path)
    .select(
        "*",
        F.col("_metadata.file_path").alias("_source_file"),
        F.current_timestamp().alias("_ingested_at"),
        F.lit("crm").alias("_source_system"),
        F.lit(batch_id).alias("_batch_id"),
    )
)
raw.write.format("delta").mode("append").saveAsTable("bronze.crm_customers")
```

`_metadata` is the hidden file-metadata column of Spark's file sources (Spark 3.3
and later); `input_file_name()` is the older equivalent.

**Append-only still has to be idempotent.** Re-running the same load must not
land the same file twice. Either track which files were loaded (Databricks Auto
Loader and `COPY INTO` do this; a hand-written job needs its own record of loaded
files), or write each batch to its own partition keyed by `_batch_id` and
overwrite that partition on a re-run.

**Bronze is only replayable while it is retained.** Delta `VACUUM` and retention
settings delete old files; a bronze table vacuumed to seven days can replay seven
days. Decide bronze retention from how far back a fix may need to reach, not from
the default.

## Silver: the trustworthy base

Silver holds at least one validated, non-aggregated row per real-world record:
deduplicated, typed, conformed, and checked. It is what every gold table builds
on, so cleanup written here is written once.

**Deduplicate on the business key with a deterministic tie-break.** Sources
redeliver, and bronze kept every delivery on purpose. Pick the latest version per
key by the source's own change timestamp, then by `_ingested_at`, so a re-run
picks the same row. A tie-break on anything non-deterministic (row order, a
`first()` without an ordering) gives a different silver table on every replay,
which defeats the point of replaying.

**Cast, rename and conform here.** Conforming includes making entities from
different sources line up: one customer id across CRM and billing, one currency,
one date convention. That is still about what the data *is*. What the business
does with it (revenue recognition, segment rules, KPI definitions) is gold.

**Schema evolution is decided here.** Bronze took whatever arrived; silver decides
whether a new column is accepted, a dropped column is an incident, or a type change
is cast. This is where an upstream change should stop a run instead of reaching a
dashboard.

```sql
MERGE INTO silver.customers AS t
USING (
    SELECT * FROM (
        SELECT *,
               row_number() OVER (
                   PARTITION BY customer_id
                   ORDER BY source_updated_at DESC, _ingested_at DESC
               ) AS rn
        FROM bronze_customers_typed   -- cast and checked from this batch
    ) WHERE rn = 1
) AS s
ON t.customer_id = s.customer_id
WHEN MATCHED AND s.source_updated_at >= t.source_updated_at THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
```

The deduplication inside `USING` is not optional. Delta's `MERGE` fails when more
than one source row matches the same target row, and other engines either fail
the same way or apply the duplicates in an undefined order. The guard on
`source_updated_at` keeps a replayed older batch from overwriting a newer row.

## Gold: serving consumers

Gold holds what people and systems read: dimensional models, aggregates, metrics,
ML features. Its shape follows its consumers, not its sources, so one silver table
may feed several gold tables and one gold table may join many silver ones.

**Gold reads silver, never bronze.** A gold table that reads bronze skips the
deduplication and typing that silver exists to do, and repeats them, slightly
differently, in its own SQL. Two gold tables then disagree about how many
customers there are, and neither is wrong by its own logic.

Business rules live here, in one place each. A metric defined in two gold tables
will drift; build the second on the first, or define the rule in a shared gold
model both read.

## Idempotent transitions

Every write between layers must give the same result when it runs twice, because
retries, replays and backfills all run it twice. Which write mode achieves that
depends on what the target table is keyed by.

| Layer | Write mode | Why it is safe to re-run |
|---|---|---|
| Bronze | Append, with loaded-file tracking or overwrite of the batch's partition | The same file or batch never lands twice |
| Silver | `MERGE` by business key, or overwrite of the affected partitions | A replayed row updates its own key instead of adding a second one |
| Gold | Overwrite of the affected partitions, or full rebuild when small | The partition is recomputed from silver, whatever it held before |

A plain `append` to silver or gold is the common mistake: it works on the first
run, and the first retry doubles the rows. Partition overwrite needs care too.
Spark's default `spark.sql.sources.partitionOverwriteMode=static` with `mode("overwrite")`
replaces the whole table, not the partitions the batch touched; set it to `dynamic`,
or on Delta use `replaceWhere` with the exact range being rebuilt.

## Where the quality checks sit

| Layer | Checks | What a failure does |
|---|---|---|
| Bronze | Schema capture only: the load succeeded, the file parsed, row counts are recorded | Alerts; the raw data is kept regardless |
| Silver | Blocking checks: keys not null and unique, types cast, values in range, referential integrity | Failing records are quarantined or the run stops, before anything downstream reads them |
| Gold | Business-rule checks: totals reconcile with silver, metrics within plausible bounds, no unexpected drop in volume | The publish is held for a person to look at |

Bronze checks stay light because bronze must accept what arrived; rejecting a row
at ingestion loses it. Silver is where checks block, because silver is the last
point where one bad record can be stopped before many gold tables multiply it. For
quarantine, release comparison and quality scores, see
[data-quality-controls](../DATA-QUALITY-CONTROLS/SKILL.md).

## Failure modes

**Business logic in bronze.** A filter, a join or a derived column at ingestion
couples capture to logic. When the rule changes, there is no unchanged copy to
re-derive from, and the fix becomes a re-ingestion the source may not support.

**Skipping silver.** Raw data goes straight into marts. Each gold table then
deduplicates and casts on its own, the cleanups diverge, and a source change has to
be fixed in every gold table instead of one silver table.

**Gold reading bronze directly.** Usually a shortcut taken for one urgent report.
It bypasses silver's checks, so dirty rows reach consumers, and it creates a
second definition of the entity that nobody maintains.

**No load metadata in bronze.** Lineage stops at the bronze table. A bad file
cannot be found, removed or replayed on its own, and silver's tie-break has no
ingestion order to fall back on.

**Silver that is not idempotent.** Appending to silver, or deduplicating with a
non-deterministic tie-break, makes every backfill a risk. Teams then stop
backfilling, and the replay property the layout was built for is lost.

## When three layers is ceremony

The layers buy replayability and a single place for cleanup. They cost storage,
compute and a set of jobs per source. Scale the rigour to what the data is used for.

- **A small source read by one report**, with a source that keeps its history,
  needs no separate bronze copy: the source is the replay point. One cleaned table
  and the report may be enough.
- **A source that forgets** (overwritten files, a short API window, rows updated
  in place) needs bronze even when the pipeline is small, because nothing else can
  replay it.
- **Silver and gold can be views** over the layer below while volumes are small.
  The boundary that matters is logical: which rules live where. Materialise a layer
  when reading it as a view becomes too slow or too costly.
- **More than three layers** is a sign that layers are being used as steps. Steps
  belong inside a layer; a new layer is justified only by a new promise to readers.

## Platform notes

### Microsoft Fabric

Fabric's guidance is one lakehouse per layer, each in its own workspace, which
gives access control and governance per layer. Two deployment patterns are
documented: all three layers as lakehouses, or bronze and silver as lakehouses with
gold as a warehouse.

- **Lakehouse or warehouse for gold.** Choose by who builds it and how. A lakehouse
  is written with Spark (notebooks, Spark job definitions), pipelines or dataflows,
  and readers query it through its SQL analytics endpoint, which is read-only T-SQL.
  A warehouse is written in T-SQL (`COPY INTO`, `INSERT`, `CREATE TABLE AS SELECT`,
  stored procedures) and supports multi-table transactions. A Spark team keeps gold
  in a lakehouse; a T-SQL team, or a gold layer that must update several tables
  atomically, uses a warehouse.
- **OneLake shortcuts in bronze.** When the source already sits in OneLake, ADLS
  Gen2, Amazon S3 or Google Cloud Storage, Fabric recommends a shortcut in bronze
  instead of a copy. A shortcut is a reference, not a copy: if the source owner
  overwrites or deletes the files, bronze changes with them and can no longer
  replay. Use a shortcut when the source keeps its history or replay is not needed;
  copy when it does not.
- **Materialized lake views** define silver and gold as Spark SQL (or PySpark)
  views that Fabric materialises as Delta tables, refreshes in dependency order,
  and checks with constraints such as `CONSTRAINT valid_amount CHECK (amount > 0)
  ON MISMATCH DROP` (or `FAIL`). Incremental refresh needs Delta change data feed
  on the source tables; without it a refresh is full or skipped. For logic that is
  not SQL, use notebooks.
- Silver and gold are Delta tables by default, written with V-Order, which speeds
  reads by the SQL endpoint and Power BI.

### Databricks

Bronze, silver and gold usually map to Unity Catalog schemas or catalogs, so
grants follow the layers: most users read gold, few read silver, almost nobody reads
bronze. Auto Loader handles bronze file ingestion with loaded-file tracking and
schema evolution, and adds `_metadata` for the file path. Lakeflow Declarative
Pipelines (formerly Delta Live Tables) express silver and gold as streaming tables
and materialized views, with expectations (`expect`, `expect_or_drop`,
`expect_or_fail`) as the silver gate. Databricks explicitly advises against writing
to silver directly from ingestion: schema changes and corrupt records in the source
then fail silver loads instead of being absorbed by bronze. For tuning the Spark
jobs between layers, see [spark-job-tuning](../SPARK-JOB-TUNING/SKILL.md).

### Plain Spark

Nothing enforces the layers; a naming convention does (`bronze.`, `silver.`,
`gold.` databases or path prefixes), plus review. Use a table format with `MERGE`
and atomic overwrites (Delta Lake, Apache Iceberg or Apache Hudi). Plain Parquet
directories have neither, so a failed overwrite leaves a half-written layer that
readers see.

### dbt

dbt's layers overlap with medallion, but the boundaries do not line up exactly.

| Medallion | dbt | Where they differ |
|---|---|---|
| Bronze | Sources + staging | Staging already renames and casts, which medallion puts in silver. The raw tables themselves are written by the loader; dbt only declares them as sources. |
| Silver | Intermediate | Deduplication and conforming across sources. Typing happened a layer earlier, in staging. |
| Gold | Marts | Close match. |

The mapping is approximate, so pick one vocabulary per project and say which. For
what belongs in each dbt layer, see
[dbt-layer-boundaries](../DBT-LAYER-BOUNDARIES/SKILL.md). For keeping a dimension's
history in silver or gold, see [scd2-implementation](../SCD2-IMPLEMENTATION/SKILL.md).
