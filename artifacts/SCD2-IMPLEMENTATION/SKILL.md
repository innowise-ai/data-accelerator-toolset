---
name: scd2-implementation
description: Implement Slowly Changing Dimension Type 2 using the project's database dialect and schema, with validity intervals, null-safe change detection, and idempotency checks. Use when building or fixing a dimension that must keep the history of changed attributes.
---

# SCD2 implementation

Type 2 keeps history: instead of overwriting a changed attribute, close the current
row and open a new one. Every row is a version with a validity interval.

Apply the workflow to the project's database and schema. The SQL blocks below are
PostgreSQL reference examples, not a portable script. Names such as
`dds.dim_customers`, `raw.customers` and `customer_id` are illustrative.

## First: identify the database and map the schema

Before writing SQL, inspect project configuration, migrations, existing queries and,
when available, read-only database metadata. Establish:

- The database engine and version, SQL client or dbt adapter, and transaction support
  of the target tables. Do not infer the engine from table names or this example.
- The source relation and history target, including their database/schema qualifiers;
  the business key (possibly composite); tracked attributes; effective timestamp;
  validity columns; current-row convention; and any audit or surrogate-key columns.
- The input shape: current-state snapshot or change events, uniqueness per key in a
  batch, ordering and timestamp precision/time zone. Distinguish the extraction
  watermark from the business effective time if the project uses separate columns.
- The handling of late events, deletes and concurrent loads of the same keys. Reuse
  established project rules; identify missing rules that affect history correctness.

Summarize the engine/version and the source-to-target column mapping before
implementation. Ask only for facts that cannot be established from the project;
do not silently default to PostgreSQL or invent missing columns. If `customers_db`
is the user's table, determine whether it is the source or history target and keep
that name. Do not rename it or create `dds.dim_customers` just to match the example.

## Adapt, implement, and verify

1. Choose an implementation supported by that engine/version and the input contract.
   The reference merge assumes a stable batch with one row per business key,
   chronological new versions (or an identical retry of the latest batch), and
   serialized loads of overlapping keys.
   Validate these assumptions before writes; otherwise deduplicate identical events,
   process distinct changes in order, or implement interval splitting as required.
   A transaction alone does not guarantee that concurrent loads cannot duplicate keys.
2. Translate all SQL to the target dialect: identifiers, null-safe comparisons,
   update/join syntax, temporal types, defaults, indexes, transaction boundaries,
   parameter binding and validation queries. Preserve the invariants below. Check
   version-specific support in official engine/driver documentation; renaming tables
   alone is not a dialect conversion. See [Dialect adaptation](#dialect-adaptation).
3. Run the adapted implementation in an isolated fixture on the target engine/version.
   Cover new, unchanged and changed keys, changes into/out of `NULL`, and window
   boundaries. Load the identical batch twice and compare row values and their
   multiplicities, total count and open-version counts per key; run all invariants.
   Test late/multiple events or their rejection according to the chosen contract.
4. Deliver the mapped SQL and validation results with the engine/version and remaining
   assumptions. If execution is unavailable, label the implementation unverified on
   that engine; a PostgreSQL test does not establish MySQL or Snowflake compatibility.

## Table shape

```sql
CREATE TABLE dds.dim_customers (
    customer_id   integer      NOT NULL,
    full_name     text,
    email         text,
    city          text,
    actual_from   timestamptz  NOT NULL,
    actual_to     timestamptz,                         -- NULL = current version
    loaded_at     timestamptz  NOT NULL DEFAULT now()  -- when the merge wrote this row
);

CREATE INDEX idx_dim_customers_current
    ON dds.dim_customers (customer_id) WHERE actual_to IS NULL;
```

The partial index matters: nearly every query and every step of the merge below
filters on `actual_to IS NULL`, and that predicate hits a small fraction of a table
that grows without bound.

The source, `raw.customers`, has the same attribute columns plus `updated_at`: the
time the source system recorded the change. It is the only timestamp the merge
reasons with. It selects the load window, and it becomes the new version's
`actual_from`, so validity follows when the change happened, not when the pipeline
got round to loading it. `loaded_at` is audit only; nothing below reads it. If the
source has no change time and you fall back to a load timestamp, the validity
intervals end up describing your load schedule rather than the customer.

## Open interval: `NULL` or a sentinel

Two conventions, and mixing them is a real source of bugs.

| | `actual_to IS NULL` | `actual_to = '9999-12-31'` |
|---|---|---|
| Current-row filter | `WHERE actual_to IS NULL` | `WHERE actual_to = '9999-12-31'` |
| Range query | needs `COALESCE` or `OR IS NULL` | plain `BETWEEN` works |
| Wrong-result risk | `NULL` comparisons silently drop rows | sentinel leaks into date arithmetic |

Pick one per warehouse and enforce it. The failure when both exist is that a
`BETWEEN` range query silently omits every current row - no error, just quietly
missing data.

## Half-open intervals

Use `[actual_from, actual_to)` - inclusive start, exclusive end. The new version's
`actual_from` equals the closed version's `actual_to`.

Closing with `actual_to = new_ts` and opening with `actual_from = new_ts` means a
point-in-time lookup uses `WHERE ts >= actual_from AND (actual_to IS NULL OR ts < actual_to)`
and matches exactly one row. Closing with `new_ts - interval '1 second'` instead
creates a one-second gap where the customer does not exist, and hides a genuine
double-write behind what looks like rounding.

## Change detection

Use a null-safe difference test for the selected dialect, rather than a plain
`<>` or `!=`. In PostgreSQL this is `IS DISTINCT FROM`:

```sql
WHERE d.full_name IS DISTINCT FROM n.full_name
   OR d.email     IS DISTINCT FROM n.email
   OR d.city      IS DISTINCT FROM n.city
```

`NULL <> 'x'` evaluates to `NULL`, not `TRUE`, so a plain comparison misses every
change into or out of `NULL`. A customer whose email goes from `NULL` to a real
address produces no new version at all - silent history loss, and the kind that is
only discovered months later.

For wide tables, hashing is the readable alternative. It must handle `NULL` and
separator collisions:

```sql
-- Wrong: NULL nulls the whole hash; 'ab'||'c' collides with 'a'||'bc'
md5(full_name || email || city)

-- Correct
md5(concat_ws('|', coalesce(full_name, '<NULL>'),
                   coalesce(email,     '<NULL>'),
                   coalesce(city,      '<NULL>')))
```

## The merge

PostgreSQL reference: three steps, one transaction, under the input assumptions
established above. Map the identifiers and adapt the syntax before using it elsewhere.

```sql
BEGIN;

-- 1. Close versions whose attributes changed
UPDATE dds.dim_customers dst
SET actual_to = i.updated_at
FROM (SELECT customer_id, full_name, email, city, updated_at
      FROM raw.customers
      WHERE updated_at >= :start_ts AND updated_at < :end_ts) i
WHERE dst.customer_id = i.customer_id
  AND dst.actual_to IS NULL
  AND (dst.full_name IS DISTINCT FROM i.full_name
       OR dst.email  IS DISTINCT FROM i.email
       OR dst.city   IS DISTINCT FROM i.city);

-- 2. Open new versions for the keys step 1 just closed
INSERT INTO dds.dim_customers (customer_id, full_name, email, city,
                               actual_from, actual_to)
SELECT i.customer_id, i.full_name, i.email, i.city, i.updated_at, NULL
FROM raw.customers i
WHERE i.updated_at >= :start_ts AND i.updated_at < :end_ts
  AND EXISTS     (SELECT 1 FROM dds.dim_customers d
                  WHERE d.customer_id = i.customer_id
                    AND d.actual_to = i.updated_at)
  AND NOT EXISTS (SELECT 1 FROM dds.dim_customers d
                  WHERE d.customer_id = i.customer_id
                    AND d.actual_to IS NULL);

-- 3. Insert first versions for keys never seen before
INSERT INTO dds.dim_customers (customer_id, full_name, email, city,
                               actual_from, actual_to)
SELECT i.customer_id, i.full_name, i.email, i.city, i.updated_at, NULL
FROM raw.customers i
WHERE i.updated_at >= :start_ts AND i.updated_at < :end_ts
  AND NOT EXISTS (SELECT 1 FROM dds.dim_customers d
                  WHERE d.customer_id = i.customer_id);

COMMIT;
```

**One transaction, not three.** Between step 1 and step 2 the changed keys have no
open version. A reader querying `actual_to IS NULL` at that moment sees the customer
as deleted, and a crash there leaves the dimension permanently missing rows.

**Bind parameters, do not interpolate.** Building the window with an f-string
(`f"WHERE updated_at BETWEEN '{start_date}'..."`) is how a timezone-formatted
timestamp silently shifts the window, and it is an injection vector when any part of
the predicate comes from a config table.

**Half-open window `>= start AND < end`.** `BETWEEN` includes both endpoints, so a
row landing exactly on the boundary is processed by two consecutive runs and gets a
duplicate version.

## Idempotency

Re-running the window that was just loaded - after a failed downstream step, or
because the orchestrator retried - must change nothing. Each step has a guard that
makes it a no-op the second time:

- **Step 1** closes an open version only when its attributes differ from the
  incoming row. On a re-run the open version *is* the incoming row, so nothing is
  closed.
- **Step 2** needs both of its conditions. `EXISTS` says "this key has a version that
  ends at this incoming timestamp", and that stays true after the first run, because
  the version closed then still ends at `updated_at`. On its own it re-opens the key
  on every re-run and leaves two open versions. `NOT EXISTS` on an open version is
  what stops the re-run: on the first run step 1 has just closed the key, so there
  is no open version and the insert goes ahead; on a re-run the version the first
  run opened is still there, so nothing is inserted.
- **Step 3** inserts only keys with no rows at all, and after the first run the key
  has one.

In this reference, `NOT EXISTS` avoids collecting keys closed in this run into a
temporary table. Under the stated input and serialization assumptions it prevents
opening another version when one is already open. It is not a uniqueness constraint
and does not make arbitrary changes to step 1 or concurrent loads safe.

Test it rather than trusting the argument. Load a window, snapshot the table, run the
merge again with the same `:start_ts` and `:end_ts`, and compare:

```sql
-- After the first run
CREATE TEMP TABLE after_first_run AS SELECT * FROM dds.dim_customers;

-- ... run the merge again on the same window ...

-- Row count unchanged: must return 0
SELECT (SELECT count(*) FROM dds.dim_customers)
     - (SELECT count(*) FROM after_first_run) AS rows_added;

-- No row changed: must return no rows
SELECT * FROM dds.dim_customers EXCEPT SELECT * FROM after_first_run;

-- At most one open version per key: must return no rows
SELECT customer_id FROM dds.dim_customers
WHERE actual_to IS NULL GROUP BY customer_id HAVING count(*) > 1;
```

The count check is not redundant with `EXCEPT`. `EXCEPT` compares sets, so it sees a
duplicated open version only because its `loaded_at` differs. Drop the audit column,
or compare only the business columns, and the duplicate is identical to the original
and `EXCEPT` passes the exact bug the test exists to catch.

Re-running an *older* window after a newer one has loaded is a different case: step 1
would close the current version at an earlier timestamp and leave an inverted
interval. That is late-arriving data, covered below.

Three related traps:

- **Multiple changes per key in one window.** The merge as written closes one
  version and opens one, so intermediate states are lost. If the source can change
  a key twice within a window, either shrink the window or rank the incoming rows
  and process them in order.
- **Late-arriving data.** A row whose `updated_at` precedes the current version's
  `actual_from` needs an interval split, not an append. Decide explicitly whether to
  support this; if not, assert the input and fail loudly.
- **Full-reload initialisation.** The initial load uses
  `LEAD(updated_at) OVER (PARTITION BY customer_id ORDER BY updated_at)` to derive
  `actual_to` from the next row's timestamp. That is a different code path from the
  incremental merge, and it needs its own test.

## Invariants worth asserting

Cheap to check, and each catches a real class of corruption:

```sql
-- At most one open version per key
SELECT customer_id FROM dds.dim_customers
WHERE actual_to IS NULL GROUP BY customer_id HAVING count(*) > 1;

-- No two versions of a key starting at the same time
SELECT customer_id, actual_from FROM dds.dim_customers
GROUP BY customer_id, actual_from HAVING count(*) > 1;

-- No overlapping intervals: a later version starts before the earlier one ends
SELECT a.customer_id FROM dds.dim_customers a
JOIN dds.dim_customers b
  ON a.customer_id = b.customer_id AND a.actual_from < b.actual_from
WHERE a.actual_to IS NULL OR b.actual_from < a.actual_to;

-- No inverted intervals
SELECT * FROM dds.dim_customers WHERE actual_to <= actual_from;
```

Run them as pipeline assertions, not one-off queries. The first one in particular
catches the double-write that step 1 and 2 in separate transactions produces. The
overlap check pairs versions by ordering on `actual_from`, so it needs no physical
row id; exact duplicates, which that ordering cannot see, are what the second check
is for.

## Dialect adaptation

These are starting points for adapting the reference, not a list of tested engines.
For any other SQL engine, use its version-specific documentation and the same
mapping and verification workflow.

### Snowflake

- **Index strategy.** For a standard Snowflake table, omit the PostgreSQL partial
  index. Choose clustering only when query profiles justify it; do not translate
  indexes mechanically into clustering keys.
- **`DEFAULT now()`** becomes `DEFAULT current_timestamp()`.
- Adapt timestamp types and client parameters, then verify the complete transaction
  and invariant queries on the target account.

### MySQL

- Rewrite `UPDATE ... FROM` using the supported joined-update form; see
  [UPDATE](https://dev.mysql.com/doc/refman/8.4/en/update.html).
- Use `NOT (a <=> b)` for null-safe difference; see
  [comparison operators](https://dev.mysql.com/doc/refman/8.4/en/comparison-operators.html).
- Replace PostgreSQL temporal types and partial indexes with a design supported by
  the actual version. Choose `DATETIME`/`TIMESTAMP` precision and a time-zone policy
  explicitly; see [temporal types](https://dev.mysql.com/doc/refman/8.4/en/date-and-time-types.html).
- Verify transactional storage, target-table read/write restrictions and support for
  the test queries (including `EXCEPT`) in the deployed version. Use an equivalent
  comparison preserving duplicate counts if a set operator is unavailable.

### Client parameters

- **Parameter syntax belongs to the client, not the SQL.** The examples use
  SQLAlchemy-style named binds (`:start_ts`, `:end_ts`). In psql, replace them with
  `:'start_ts'` and `:'end_ts'`: psql substitutes variables into the SQL text, and
  this form quotes and escapes their values as SQL literals. Bare `:start_ts`
  inserts text verbatim; it is not a bound parameter. The Snowflake Python
  connector uses `%(start_ts)s` or, when configured for `qmark`, `?`. In application
  code, pass values through the client's parameter API rather than interpolating
  them into SQL strings.

## Prefer the built-in

If the project already runs dbt with a suitable adapter, consider a snapshot for
tracking successive source states. Adapt the configuration to the installed dbt
version and map the source and key; this is a reference example:

```sql
{% snapshot customers_snapshot %}
{{ config(target_schema='snapshots', unique_key='customer_id',
          strategy='timestamp', updated_at='updated_at') }}
select customer_id, full_name, email, city, updated_at
from {{ source('raw_source', 'customers') }}
{% endsnapshot %}
```

dbt maintains `dbt_valid_from` / `dbt_valid_to` (`NULL` = current) and a
`dbt_scd_id` surrogate key. `strategy='timestamp'` needs a trustworthy `updated_at`;
where there is none, `strategy='check'` with `check_cols` compares the columns
directly and is the equivalent of the `IS DISTINCT FROM` block above.

Use custom SQL when the project's requirements exceed the snapshot's behavior,
such as replaying every event in a batch or splitting historical intervals for late
events. A snapshot cannot recover intermediate states absent from its input. Verify
the chosen implementation against the same input contract and invariants.
