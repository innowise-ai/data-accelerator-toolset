---
name: schema-evolution-planning
description: Changing the schema of a table, file set or event stream that other people read - adding, renaming, dropping or retyping a column, or tightening nullability - without breaking a reader. Covers finding the readers, which compatibility direction a change needs, telling additive from breaking changes, rolling a breaking change out in steps (add, dual-write, backfill, move readers, drop after a deprecation window), adding a NOT NULL column, reading by name rather than position, and how Avro with a schema registry, Delta Lake, Iceberg, raw Parquet and the main warehouses evolve. Use when asked to add, rename, drop or retype a column in a shared table or event schema, to enable schema evolution or mergeSchema, or when a schema change has broken a downstream reader.
---

# Rolling out a schema change

A schema that other people read is an interface. The producer can change it in
one statement; the readers are dashboards, dbt models in other projects, Spark
jobs, extracts, ML features and services that nobody listed, and each one finds
out about the change when it next runs. Some of them fail loudly. The worse ones
keep working: a renamed column read through a tolerant reader becomes a column of
nulls, a type change truncates, and a column with a new meaning under the old name
feeds a report for weeks before anyone notices.

This skill plans a change so that every reader keeps working at every point
between the old schema and the new one. Most of the work is not the `ALTER
TABLE`. It is finding the readers, deciding whether the change is additive or
breaking, and, for a breaking one, splitting it into steps that each leave every
reader working.

Neighbours:

- Inside one dbt project, where the model and all its consumers change in one
  commit: [dbt-model-refactoring](../DBT-MODEL-REFACTORING/SKILL.md#when-the-interface-must-change).
  This skill is for readers that a single commit cannot reach.
- dbt contracts, which fail a build when a model's columns or types drift:
  [dbt-layer-boundaries](../DBT-LAYER-BOUNDARIES/SKILL.md#contracts).
- What an incremental dbt model does when its input gains or loses a column
  (`on_schema_change`): [dbt-incremental-strategy](../DBT-INCREMENTAL-STRATEGY/SKILL.md#declare-what-happens-when-the-schema-changes).
- Which layer accepts an upstream schema change and which one stops it:
  [medallion-layer-boundaries](../MEDALLION-LAYER-BOUNDARIES/SKILL.md).
- New columns arriving in files through Auto Loader (`schemaEvolutionMode`,
  `_rescued_data`):
  [databricks-declarative-pipeline-design](../DATABRICKS-DECLARATIVE-PIPELINE-DESIGN/SKILL.md).
- Re-deriving history after the change, when the backfill is more than one
  `UPDATE`: [backfill-planning](../BACKFILL-PLANNING/SKILL.md).
- A semantic view that drifted from the tables beneath it:
  [snowflake-semantic-view-drift](../SNOWFLAKE-SEMANTIC-VIEW-DRIFT/SKILL.md).

## What this skill changes

Planning is read-only: reading code, table metadata, lineage and query history.
The steps themselves alter shared tables, and some of them cannot be undone
without a restore or a rewrite (a dropped column, a protocol upgrade on a Delta
table, a tightened constraint that a writer then fails on). Write the plan first, with
each step's statement, and run each step only after the user has approved it.
Run the steps against a copy or a development schema first when one exists. The
role that runs them needs to alter the table; it does not need to own the
readers.

## First: find the readers

The change is safe only for the readers you know about, so list them before
classifying anything. Look in every place a reader can hide:

- **Lineage in code.** `dbt ls --select <model>+` for models in the same project,
  a search of the other repositories for the table name, the orchestrator's
  tasks that read it.
- **Query history**, which finds readers that are not in any repository: in
  Snowflake, `SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY` (Enterprise Edition) lists
  the columns each query read; in BigQuery,
  `INFORMATION_SCHEMA.JOBS` has `referenced_tables`; in PostgreSQL,
  `pg_stat_statements` when it is installed, and `pg_depend` for views. Take a
  window long enough to include monthly and quarterly jobs.
- **Views and semantic layers** defined over the table, in the warehouse and in
  BI tools. A view that names a column fails when the column is renamed; one
  written as `SELECT *` may keep the old column list or pick up the new one,
  depending on the engine.
- **Extracts and caches**: BI extracts, reverse-ETL syncs, feature stores and
  exports to other teams, which copied the schema at some point and will
  compare against it on the next refresh.
- **Engines that read the files directly.** Trino, Athena, a Spark job on an
  older runtime, or a pandas script reading the Parquet files under a Delta or
  Iceberg table bypass the table format, and some features below (Delta column
  mapping in particular) make the table unreadable to them.
- **Event consumers**: every consumer group of a topic, including the ones that
  archive it to a lake.

Write the list down with an owner for each. It is the list of people to tell,
and in the stepwise rollout below it is the list you tick off before the old
column can go.

## Which direction of compatibility the change needs

Two questions, and they have different answers:

- **Can a reader that has been updated read data written before the change?**
  This is *backward* compatibility in the schema registry's terms: new readers,
  old data. For a table format it is the format's job: Delta and Iceberg read old
  files under the new schema, filling an added column with nulls. For an event
  stream it matters whenever a consumer replays old messages.
- **Can a reader that has not been updated read data written after the change?**
  This is *forward* compatibility: old readers, new data. For a shared table it
  is the question that matters most, because every query, dashboard and job that
  exists today is an old reader, and the change reaches all of them the moment it
  is applied.

A table has one current schema that every reader sees at once, so a change to it
has to be compatible in both directions while readers are moving, and the
stepwise rollout below is how a breaking change gets there. An event stream can
hold messages of several schema versions at once, so there the direction decides
the order of deployment: under backward compatibility the consumers are upgraded
first, under forward compatibility the producers.

## Classify the change

| Change | Existing readers | Why |
|---|---|---|
| Add a nullable column, or one with a default | Keep working, with the exceptions below | A reader that names its columns does not see it |
| Widen a type (`int` to `bigint`, `decimal(10,2)` to `decimal(18,2)`) | Usually keep working | Every old value still fits; a reader with a fixed target type, such as a contract, a typed DataFrame schema or a fixed-width export, can still fail |
| Relax `NOT NULL` to nullable | Keep working until a null arrives | Code that assumed no nulls then breaks on data, not on the schema |
| Rename a column | Break | Every reader names the old column |
| Drop a column | Break | Same, and the data is gone for anyone who still needed it |
| Narrow a type (`bigint` to `int`, shorter `varchar`, fewer decimal places) | Break or lose data | Old values may not fit; engines either fail or truncate, and truncation is silent |
| Change a type's family (`string` to `int`, `timestamp` to `date`) | Break | Treat as drop plus add |
| Tighten nullable to `NOT NULL` | Break writers, not readers | Every writer that can still produce a null now fails |
| Reorder columns | Break positional readers | See [Read by name, not by position](#read-by-name-not-by-position) |
| Same name, same type, new meaning (cents to units, UTC to local time, gross to net) | Break silently | Nothing in any schema check detects it |

"Additive is safe" holds only for readers that name their columns. An added
column breaks a reader that writes `SELECT *` into a table with a fixed column
list, an `INSERT INTO ... SELECT *` that binds by position, a dbt model with an
enforced contract that selects `*`, and an export whose consumer rejects
unexpected fields. The reader inventory says which of these exist.

The last row deserves its own rule. A change of meaning is the most dangerous
change because every check passes. Never change what a column means under the
same name: add a column with a new name (`amount_net`, `created_at_utc`) and
treat the old one as a column to deprecate.

## Roll out a breaking change in steps

A rename, a drop, a narrowing or a change of type is done as a sequence in which
every step leaves every reader working. The usual name is expand and contract:
the schema first grows to hold both forms, readers move, then it shrinks.

1. **Add the new column** beside the old one, nullable. Nothing reads it yet, so
   nothing can break.
2. **Dual-write**: change every writer to fill both columns, from the same
   expression in the same statement, so the two cannot disagree. This comes
   before the backfill, not after it: rows written between a backfill and the
   start of dual-writing would have only the old column.
3. **Backfill** the new column from the old one for the rows written before
   dual-writing started. For a large or partitioned table this is a backfill in
   its own right, done in units and reconciled; see
   [backfill-planning](../BACKFILL-PLANNING/SKILL.md). Then check that the two
   columns agree on every row, with a query that counts mismatches, nulls
   included.
4. **Move the readers** to the new column, one by one, from the inventory. Tell
   each owner what changed, what the new column holds, and the date the old one
   goes away.
5. **Wait out the deprecation window**, and check query history for reads of the
   old column during it. The window has to cover the slowest reader's cycle:
   month-end and quarter-end jobs read a table a handful of times a year, and a
   window shorter than that removes the column from under them. Mark the old
   column deprecated where readers will see it: its description (in dbt, the
   column's `description` or `meta`) and the data catalog. dbt's
   `deprecation_date` belongs to a whole model or model version, not to a column;
   see [dbt](#dbt).
6. **Stop writing the old column** once query history shows no reads of it:
   change every writer to fill only the new one, and check in query history that
   no statement writes the old column any more.
7. **Drop the old column.** Dropping it while a writer still fills it makes every
   one of that writer's statements fail, and the DDL and the writers' deploys
   cannot happen at the same instant, so the drop comes after the last writer has
   stopped.

Each step is reversible until the last, which is why the last waits for
evidence rather than a date alone.

**A view can shorten this.** When every reader goes through a view rather than
the table, the view can keep the old name while the table changes
(`new_name AS old_name`). Readers move to the new name, in the same view or a
new one, on their own schedule, and the old name is removed from the view after
the window. The table change and the view change must reach readers together,
and engines differ there. A PostgreSQL view refers to the table's columns by
number, so it keeps working through `RENAME COLUMN` and keeps showing the old
name without being redefined. Snowflake and BigQuery resolve a view's column
names when it is queried, so between the rename and the `CREATE OR REPLACE VIEW`
every reader of the view fails, and Snowflake commits each DDL statement on its
own. There, add the new column under the view instead of renaming (steps 1 to 3),
point the view's old name at it, and drop the old column at the end. Either way
this works only when nobody reads the table directly, and the inventory is what
says so.

**Some engines rename in metadata only**, so the rename itself is cheap and
instant: Iceberg, Delta with column mapping, Snowflake, BigQuery, PostgreSQL.
That does not make it safe. It changes the cost of the rename, not the number of
readers that name the old column.

## Add a NOT NULL column

Rows that exist before the column is added have no value for it, so a new column
cannot be `NOT NULL` from the first statement unless the engine fills a default
into every existing row. Do it in three steps:

1. Add the column nullable, or with a default when one value is right for every
   existing row. A default that is only a placeholder (`0` for an unknown
   discount, `'UNKNOWN'` for a missing region) is not right: it turns "we do not
   know" into a value that looks real, and readers sum it.
2. Backfill the real values, and change every writer to fill the column.
3. Tighten to `NOT NULL` once no nulls remain and no writer can produce one. On
   most engines this statement scans the table to check, and fails if a null is
   still there, which makes it the last check of the backfill.

The same order applies to making any existing column `NOT NULL`: the writers
first, then the data, then the constraint.

## Read by name, not by position

A reader that binds columns by their position breaks when a column is added in
the middle, reordered, or added to one side of a copy but not the other, and it
usually does not fail: it puts values into the wrong columns whenever the types
are compatible. The common forms:

- `INSERT INTO target SELECT * FROM source`, and `INSERT INTO target SELECT a, b, c`
  without a column list on the target. SQL binds both by position. Name the
  target columns (`INSERT INTO target (a, b, c) SELECT a, b, c`), or use
  `INSERT INTO target BY NAME SELECT ...` where the engine has it (Spark SQL,
  DuckDB).
- In Spark, `DataFrameWriter.insertInto` ignores the DataFrame's column names
  and binds by position; `saveAsTable` in append mode resolves by name.
- CSV and other headerless files, and code that reads a row as a tuple
  (`row[3]`).
- External engines reading the files of a Hive-style table, when they match file
  columns by index. Trino's Hive connector, for one, reads ORC files by position
  by default (`hive.orc.use-column-names` is `false`) and Parquet files by name.

Iceberg and Delta with column mapping track columns by an id, so reordering
their columns is safe for readers that go through the format. The `INSERT ...
SELECT *` above is still positional against them.

## Schema evolution on write: choose where it happens

Several engines can add a column automatically when the data being written has
one the table lacks: `mergeSchema` in Delta, schema evolution in Auto Loader,
`on_schema_change: append_new_columns` in dbt. Switched on everywhere, this
turns every upstream change, including a typo, into a new column. A producer
that writes `custmer_id` instead of `customer_id` adds a column of that name to
the table, leaves `customer_id` null for its rows, and the write succeeds.

Accept automatic evolution where the job is to keep whatever arrived, which is
bronze or raw. Turn it off where the schema is an interface, which is silver,
gold and anything with readers outside the team, so that an unexpected column
stops the run there instead of reaching a dashboard
([medallion-layer-boundaries](../MEDALLION-LAYER-BOUNDARIES/SKILL.md) puts that
decision in silver). Where it is on, watch for it: compare each run's schema with
the last one, or alert on new columns, so that the column added at 3 a.m. is a
message rather than a discovery.

## Formats

### Avro with a schema registry

The registry checks each new schema version against the previous one before a
producer can use it, under a compatibility type set per subject. With the
Confluent Schema Registry the default is `BACKWARD`.

| Type | Allowed changes | Upgrade first |
|---|---|---|
| `BACKWARD` (default) | Delete fields; add optional fields (with a default) | Consumers |
| `FORWARD` | Add fields; delete optional fields | Producers |
| `FULL` | Add or delete optional fields | Either |
| `NONE` | Anything | Not checked |

The non-transitive types compare a new schema with the last version only; the
`*_TRANSITIVE` types compare it with every earlier version. A consumer that
replays a topic from the beginning reads every version still retained, so a topic
that is replayed, or archived and re-read, needs a transitive type.

Add a field with a default; a field without one is rejected under `BACKWARD`,
because a new consumer reading an old message would have no value for it. A
rename is a delete plus an add under every type: the registry passes it only if
both halves are allowed, and consumers that read the old name then see the
default. Avro aliases on the reader's schema can map an old name to a new one,
but not every Avro implementation honours them, so do not count on them to make a
rename safe. Roll it out like any other rename, with both fields present for a
window.

### Delta Lake

- **Adding columns** is an `ALTER TABLE ... ADD COLUMNS`, or `mergeSchema` on a
  write (`.option("mergeSchema", "true")`), which adds the columns the DataFrame
  has and the table lacks. Columns the DataFrame lacks stay in the table and are
  written as null. For `MERGE`, Databricks Runtime 15.4 LTS and later switch
  schema evolution on for one statement with `MERGE WITH SCHEMA EVOLUTION INTO`.
  Elsewhere it takes the session setting
  `spark.databricks.delta.schema.autoMerge.enabled`, which applies to every
  write in the session, not only the merge; set it around the one statement
  that needs it, in a session that runs nothing else meanwhile.
- **Renaming and dropping** need column mapping, enabled with
  `ALTER TABLE t SET TBLPROPERTIES ('delta.columnMapping.mode' = 'name')`. It
  upgrades the table's protocol (reader version 2, writer version 5): the table
  can then be read only by Delta Lake 1.2 or later, or by an engine that
  supports column mapping. Check the inventory for engines and older runtimes
  that read it before enabling it; this is the one step in this skill that can
  break readers who never use the column. Undoing it is not a property change:
  `ALTER TABLE t DROP FEATURE columnMapping` removes it and downgrades the
  protocol from Delta Lake 3.3 and Databricks Runtime 15.4 LTS, by rewriting
  the data files. On older versions the upgrade is permanent. With column
  mapping on, a rename or drop changes metadata only; a dropped column's data
  stays in the Parquet files until they are rewritten.
- **Streaming readers** of a table that had a column renamed or dropped are
  blocked; from Delta 3.0 they continue only with a schema tracking location
  (`schemaTrackingLocation`, inside the query's checkpoint location), so include
  every streaming query on the table in the inventory.
- **Changing a type** without type widening means rewriting the table with
  `overwriteSchema`, which every reader sees as a drop and an add. Type widening
  (`delta.enableTypeWidening`, fully supported from Delta 4.0) widens types in
  place: integers to wider integers, `float` to `double`, a larger decimal,
  `date` to `timestamp_ntz`. Widening an integer to a decimal or a double has to
  be done with an explicit `ALTER TABLE`; schema evolution on write does not
  apply it.

### Iceberg

Iceberg tracks every column by an id that is never reused, and resolves file
columns by that id, not by name or position. Adding, dropping, renaming and
reordering columns, and widening a type (`int` to `long`, `float` to `double`, a
larger decimal precision) change only metadata; no data file is rewritten. A
column dropped and then added again under the same name gets a new id, so the
old values do not come back.

What Iceberg does not do is make the change safe for readers that name the
column: a rename is still a rename for every query that uses the old name.
Making a column required, or adding a required column, is rejected by default,
for the reason in [Add a NOT NULL column](#add-a-not-null-column): the Java API
throws unless `allowIncompatibleChanges()` is called, and Spark SQL cannot `SET
NOT NULL`. Format version 3 lets a new column carry an `initial-default`, the
value every row written before it was added reads as.

### Parquet files without a table format

Parquet files carry their own schema, and nothing keeps the files in a directory
consistent with each other. A directory written over time holds files with
different columns, and what a reader sees depends on how it merges them. Spark,
for one, does not merge Parquet schemas by default (`mergeSchema` is off for
Parquet reads, because merging is expensive), so a column present only in newer
files can be missing from the result. A type that changed between files fails
the read, or not, depending on the engine.

There is no rename and no drop: the files are immutable, and a "rename" is new
files with a new name beside old files with the old one. Either put the data
under a table format (Delta, Iceberg, Hudi), which records one schema for all
files, or reconcile on read: a reader that declares the schema it expects,
casts each file to it, and fails on a column it cannot place.

### Warehouse tables

The warehouse holds one schema and applies an `ALTER` to all readers at once, so
the stepwise rollout is the whole technique; the engine only decides what each
step costs and which changes it refuses.

- **PostgreSQL**: adding a column with a non-volatile default does not rewrite
  the table (since 11). `SET NOT NULL` scans the whole table under an exclusive
  lock; on a large table, add a `CHECK (col IS NOT NULL) NOT VALID` constraint,
  run `VALIDATE CONSTRAINT` (which takes a lock that does not block writes), and
  `SET NOT NULL` then skips the scan because the valid constraint already proves
  there are no nulls. That skip exists from PostgreSQL 12; on 11 and earlier
  `SET NOT NULL` scans anyway.
- **Snowflake**: an existing column's type can change only within limits, such
  as a longer `VARCHAR` or a larger `NUMBER` precision with the same scale;
  anything else is a new column. `SET NOT NULL` fails while the column holds a
  null. A view that includes a dropped column becomes invalid and fails when
  next queried, and a view that names a renamed column breaks the same way.
- **BigQuery**: a column's type can only be widened along the permitted
  conversions, and a `REQUIRED` column can be relaxed to `NULLABLE` but not
  tightened, or added to an existing table. `RENAME COLUMN` and `DROP COLUMN`
  are metadata changes.

## dbt

The steps above apply to a dbt model as they do to a table; dbt adds two tools,
described in its neighbours rather than here:

- **Contracts** turn an unplanned change of a column's name or type into a
  failed build instead of a reshaped table:
  [dbt-layer-boundaries](../DBT-LAYER-BOUNDARIES/SKILL.md#contracts). An
  incremental model with an enforced contract accepts only
  `on_schema_change: append_new_columns` or `fail`, because `sync_all_columns`
  would drop columns. When a run compares against a saved state
  (`state:modified`), dbt 1.7 and later report a breaking change to a contract
  (a removed column, a changed type, a removed or changed constraint) as an
  error on a versioned model and as a warning on an unversioned one.
- **Model versions** (dbt 1.5 and later) are the stepwise rollout for a model as
  a whole: a new version (`versions:` in the model's YAML, with
  `latest_version`) is built beside the old one, consumers move with
  `ref('model', v=2)` or by following the latest version, which an unpinned
  `ref` resolves to, and the old version carries a `deprecation_date` (dbt 1.6
  and later) until it is removed. Use them for a breaking change to a model that
  other projects or teams read, where the change is large enough that adding and
  later dropping columns in one model would be harder to follow than two
  versions.

## What to report

The plan, before any change:

- the change in one sentence, and its classification from the table, with the
  reason;
- the reader inventory, with owners, and how each one was found;
- for an additive change, which readers could still be affected and why not;
- for a breaking change, the steps with their statements, the check that ends
  each step (backfill complete, columns agree, no reads of the old column, no
  writes to it), and
  the deprecation window with its end date;
- format-specific consequences: a protocol upgrade, a streaming restart, a
  rewrite, a lock;
- the message to the readers' owners.

After each step: what ran, the check and its result, and what the next step
waits for.
