---
name: scd2-implementation
description: Implement Slowly Changing Dimension Type 2 in SQL - validity intervals, change detection, and the idempotency traps. Use when building or fixing a dimension that must keep the history of changed attributes.
---

# SCD2 implementation

Type 2 keeps history: instead of overwriting a changed attribute, close the current
row and open a new one. Every row is a version with a validity interval.

The SQL below is PostgreSQL. The merge, the change detection and the checks also run
on Snowflake as written; the few constructs that do not are covered in
[Running it on Snowflake](#running-it-on-snowflake).

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

Compare with `IS DISTINCT FROM`, never `<>` or `!=`:

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

Three steps, one transaction.

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

The `NOT EXISTS` is preferred over collecting the keys closed in this run into a temp
table because it states the invariant itself - at most one open version per key. It
needs no session state, runs the same in any warehouse, and keeps holding if step 1
is changed later.

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

## Running it on Snowflake

Everything above except the table definition runs unchanged. Snowflake accepts
`timestamptz` as a synonym for `TIMESTAMP_TZ`, supports `IS DISTINCT FROM`,
`UPDATE ... FROM`, `md5` and `concat_ws`, and runs the three statements as one
transaction between `BEGIN` and `COMMIT`. The differences:

- **No partial index.** Snowflake has no indexes. Drop the `CREATE INDEX`. On a large
  dimension `CLUSTER BY (customer_id)` is the nearest equivalent, worth adding only
  once query profiles show poor pruning.
- **`DEFAULT now()`** becomes `DEFAULT current_timestamp()`.
- **Parameter syntax belongs to the client, not the SQL.** The examples use
  SQLAlchemy-style named binds (`:start_ts`, `:end_ts`). In psql, replace them with
  `:'start_ts'` and `:'end_ts'`: psql substitutes variables into the SQL text, and
  this form quotes and escapes their values as SQL literals. Bare `:start_ts`
  inserts text verbatim; it is not a bound parameter. The Snowflake Python
  connector uses `%(start_ts)s` or, when configured for `qmark`, `?`. In application
  code, pass values through the client's parameter API rather than interpolating
  them into SQL strings.

## Prefer the built-in

If the warehouse already runs dbt, `snapshot` implements all of this:

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

Hand-write the merge when there is no dbt, when the source has no reliable change
timestamp and the table is too wide for `check_cols`, or when late-arriving data
needs interval splitting. Otherwise use the snapshot - the traps above are already
handled in it.
