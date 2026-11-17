# Verifying a write by running it twice

Queries for the run-twice tests in [SKILL.md](../SKILL.md#prove-it-by-running-it-twice).
Table and column names are illustrative: `fct_orders` is the target, the window
is one `order_date`, and `order_id, customer_id, amount, status` are the business
columns.

## What the checksum has to do

A checksum for this test compares the contents of a window before and after a
re-run. It has three jobs, and each common version fails one of them:

- **It must not depend on row order.** Two runs scan in different orders.
  `md5(string_agg(...))` without an `ORDER BY` inside the aggregate hashes rows in
  scan order, so two identical windows can disagree.
- **It must count a duplicated row.** Duplication is the failure the test exists
  to catch. `BIT_XOR` over row hashes is order-independent and cannot overflow,
  but a row that appears twice XORs to zero: a window where every row was written
  twice has the same XOR as an empty one. The row count catches the simple case;
  it does not catch one row lost and another duplicated.
- **It must not fail on a large table.** A `SUM` of 64-bit hashes overflows after
  a handful of rows, since each hash is up to about 9.2 × 10^18. BigQuery raises
  an error on `INT64` overflow, and so does Spark with ANSI mode on, the default
  in current versions.

Summing the hashes in a wider type does all three: addition is order-independent,
a duplicated row adds its hash again, and a 38-digit decimal holds the sum of
billions of 64-bit values. Hash only the business columns, in a fixed order, and
leave out columns that change by design on every run (`loaded_at`, `run_id`).
Round floating-point columns first, since their last digits can differ between
two correct runs.

Two equal checksums mean the windows are equal with very high probability, not
with certainty. That is enough for a test. When the checksums differ, the
row-level comparison below shows which rows.

## Per engine

### BigQuery

```sql
SELECT
  COUNT(*) AS row_count,
  SUM(CAST(FARM_FINGERPRINT(TO_JSON_STRING(
      STRUCT(order_id, customer_id, amount, status))) AS BIGNUMERIC)) AS checksum
FROM fct_orders
WHERE order_date = DATE '2026-01-15';
```

`SUM` of `BIGNUMERIC` returns `BIGNUMERIC`, so it does not overflow. `SUM` of the
bare `INT64` fingerprints, as often written, raises an overflow error on real
tables. `TO_JSON_STRING` of a `STRUCT` keeps `NULL` distinct from an empty string.

### Snowflake

```sql
SELECT
  COUNT(*) AS row_count,
  HASH_AGG(order_id, customer_id, amount, status) AS checksum
FROM fct_orders
WHERE order_date = '2026-01-15';
```

`HASH_AGG` is built for this: row order does not change it, duplicate rows do,
and it includes `NULL` values. The order of the columns passed to it does change
it, so list them the same way in both runs.

### Spark and Databricks

```sql
SELECT
  count(*) AS row_count,
  sum(CAST(xxhash64(order_id, customer_id, amount, status) AS DECIMAL(38, 0))) AS checksum
FROM fct_orders
WHERE order_date = DATE'2026-01-15';
```

`xxhash64` returns a 64-bit `BIGINT`; summing it as `BIGINT` overflows, which
throws under ANSI mode and wraps silently without it. The cast to
`DECIMAL(38, 0)` avoids both. `hash()` returns a 32-bit `INT`, whose `sum` is a
`BIGINT` that does not overflow below a few billion rows, but 32 bits make two
different windows agreeing by chance far more likely; prefer `xxhash64`.

In PySpark:

```python
from pyspark.sql import functions as F

cols = ["order_id", "customer_id", "amount", "status"]
(spark.table("fct_orders")
     .where(F.col("order_date") == "2026-01-15")
     .agg(F.count("*").alias("row_count"),
          F.sum(F.xxhash64(*cols).cast("decimal(38,0)")).alias("checksum"))
     .show())
```

### PostgreSQL

```sql
SELECT
  count(*) AS row_count,
  sum(('x' || substr(md5(row(order_id, customer_id, amount, status)::text), 1, 16))
        ::bit(64)::bigint) AS checksum
FROM fct_orders
WHERE order_date = DATE '2026-01-15';
```

Each row's text form is hashed with `md5`, the first 16 hex digits become a
`bigint`, and `sum(bigint)` in PostgreSQL returns `numeric`, so it cannot
overflow. `row(...)::text` writes a `NULL` as an empty field and quotes empty
strings, so the two stay distinct.

The `string_agg` form also works if the aggregate is ordered:
`md5(string_agg(row(...)::text, ',' ORDER BY row(...)::text))`. It builds the
whole window as one string, which is limited to 1 GB, so keep it for small
windows.

## Finding the rows that differ

When count or checksum differ, compare the window with row multiplicity. Take a
copy of the window before the re-run (or read it back with time travel:
`FOR SYSTEM_TIME AS OF` in BigQuery, `AT(OFFSET => ...)` in Snowflake,
`VERSION AS OF` on Delta), then group both sides by a row hash, so that `NULL`
columns compare as equal and duplicates show as a count of 2:

```sql
WITH before AS (
  SELECT md5(row(order_id, customer_id, amount, status)::text) AS row_hash,
         count(*) AS n
  FROM fct_orders_before_rerun
  GROUP BY 1
),
after AS (
  SELECT md5(row(order_id, customer_id, amount, status)::text) AS row_hash,
         count(*) AS n
  FROM fct_orders
  WHERE order_date = DATE '2026-01-15'
  GROUP BY 1
)
SELECT coalesce(b.row_hash, a.row_hash) AS row_hash,
       coalesce(b.n, 0) AS n_before,
       coalesce(a.n, 0) AS n_after
FROM before b
FULL OUTER JOIN after a ON a.row_hash = b.row_hash
WHERE coalesce(b.n, 0) <> coalesce(a.n, 0);
```

This is the PostgreSQL form; swap the hash expression for the engine's own from
the queries above. Join the hashes back to the tables to see the rows. A plain
`EXCEPT` is not a substitute: it compares sets, so a row present once before and
twice after does not show up.

Then check the key separately. It finds duplicates whose audit columns differ,
which the business-column checksum is designed to ignore:

```sql
SELECT order_id, count(*)
FROM fct_orders
WHERE order_date = DATE '2026-01-15'
GROUP BY order_id
HAVING count(*) > 1;
```

## Reading the result

| Count | Checksum | Key duplicates | Meaning |
|---|---|---|---|
| Same | Same | None | The re-run changed nothing in this window |
| Higher | Different | Found | The write appends; replace the append with overwrite or merge |
| Same | Different | None | Values changed: non-determinism, a moving input, or an unrounded float |
| Lower | Different | None | The re-run lost rows: a delete wider than the insert, or a failed non-atomic overwrite |
| Same | Same | Found | The re-run changed nothing, but the window was already duplicated before it; find the earlier run or path that wrote twice |

For test 3 (re-run W after W+1), run the comparison on both windows. A change in
W+1 means the write for W reaches outside its own window.
