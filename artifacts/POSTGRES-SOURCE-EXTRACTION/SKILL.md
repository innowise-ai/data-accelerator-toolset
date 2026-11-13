---
name: postgres-source-extraction
description: Extracting data from a PostgreSQL database that another application owns - incremental reads by an (updated_at, id) keyset that neither skip nor repeat rows, reading EXPLAIN to keep each batch's cost flat, the indexes an extraction needs and how to ask for one, and keeping long transactions, timeouts and connections from hurting the production database. Reads by default and confirms every write. Use when writing or reviewing a job that reads from PostgreSQL, when an extraction is slow, misses rows or duplicates them, or when the source's owners report bloat, blocked migrations or exhausted connections caused by it.
---

# Extracting from a PostgreSQL source

A PostgreSQL source is usually an application's production database, and the
extraction job is a guest in it. The application's owners decide its indexes,
roles and settings, and they notice the guest only when it hurts: a query that
reads the whole table every run, a transaction left open for hours, a burst of
connections during their peak. The job can also hurt itself, silently, with
incremental logic that skips rows committed late or repeats a batch after a
retry.

This skill covers both sides: reading the source correctly, and reading it
without being noticed. Its neighbour on the warehouse side is
[dbt-incremental-strategy](../DBT-INCREMENTAL-STRATEGY/SKILL.md), which decides
how the extracted rows are merged.

## Read only, unless someone confirms a write

Everything needed to diagnose an extraction is a read: `SELECT`, plain
`EXPLAIN`, and the statistics views. Run those freely against the connection
the user gives you.

Some statements look like reads and are not:

- **`EXPLAIN ANALYZE` executes the statement.** For a `SELECT` that means the
  full query runs on the source, with its full cost. For `INSERT`, `UPDATE` or
  `DELETE` it changes data. Wrapping it in `BEGIN; ... ROLLBACK;` undoes the
  rows but not the locks taken while it ran, the triggers it fired, or the
  sequence values it consumed. Run it only on a bounded query (one batch, one
  day), and never on a write against production.
- **`ANALYZE <table>`** rewrites the table's planner statistics. It is cheap
  and usually welcome, but it is a change to someone else's database and needs
  the table's owner (or, from PostgreSQL 17, the `MAINTAIN` privilege).

Anything that changes the source, including `CREATE INDEX`, `CREATE
STATISTICS`, `ANALYZE` and `ALTER ROLE ... SET`, is a proposal. Say what it
changes, what it locks and for how long, and who has to run it, then wait for
the user to confirm. Run confirmed statements one at a time.

**Recommend a dedicated role for the job.** It should be able to read the
tables it extracts and nothing more: `SELECT` on those tables, or membership in
`pg_read_all_data` (PostgreSQL 14+) when the job really reads everything. Add
`pg_read_all_stats` if the job or the agent needs to see other sessions in
`pg_stat_activity` and `pg_stat_statements`. Setting
`default_transaction_read_only = on` on the role catches accidental writes,
but any session can switch it off, so the grants remain the real boundary. The
timeouts in [Do not hurt the source](#do-not-hurt-the-source) belong on this
role too.

**Prefer a replica when there is one.** Reading from a hot standby keeps the
extraction's I/O off the primary. Two costs come with it. The replica lags, so
the newest rows may not be there yet; take the upper bound of a window from the
replica, not from the clock of the machine running the job. And a long query on
a standby can be cancelled with `canceling statement due to conflict with
recovery`, when the primary vacuums rows the query still needs. Turning on
`hot_standby_feedback` stops the cancellations by making the primary keep those
rows, which moves the bloat back to the primary. Short batched queries, below,
avoid both.

## Incremental extraction by `(updated_at, id)`

An incremental job reads only what changed since its last run, so it needs a
column that moves forward with every change, and a position in that column to
resume from. `updated_at` is the usual choice. Used naively, as
`WHERE updated_at > :last_run`, it loses rows in four ways, and each has a
specific fix.

### Ties: always carry a unique tie-breaker

A bulk update gives thousands of rows the same `updated_at`. If a batch ends in
the middle of them, `updated_at > :last` skips the rest and `updated_at >=
:last` reads the first part again. Resume from the pair `(updated_at, id)`
instead, where `id` is unique:

```sql
SELECT id, updated_at, customer_id, status, amount
FROM orders
WHERE (updated_at, id) > (:last_updated_at, :last_id)
  AND updated_at < :upper_bound
ORDER BY updated_at, id
LIMIT 10000;
-- index: (updated_at, id)
```

PostgreSQL compares row values left to right and can use a B-tree index on
`(updated_at, id)` for the whole condition, so every batch starts where the
previous one ended, reads only its own rows, and needs no sort. That is the
difference from `LIMIT ... OFFSET n`, which reads and throws away `n` rows on
every batch: its cost grows with how far the job has got, and rows written
during the run move between pages, so some are read twice and some never.

Store the pair from the last row of each batch, and loop until a batch returns
fewer rows than the limit.

### Late commits: stop short of now

`now()` in PostgreSQL is the time the transaction *started*, and a trigger or
default that sets `updated_at = now()` stamps rows with that time. A
transaction that starts at 10:00:00 and commits at 10:00:40 makes its rows
visible 40 seconds after their timestamp. A run at 10:00:20 that reads up to
the current time moves the watermark past 10:00:00 before those rows exist,
and no later run will look behind it.

So never read up to the current moment. Each run reads only rows below an
upper bound: the current time minus a lag longer than the longest write
transaction on the source. The bound only caps the window. What the job stores
is still the `(updated_at, id)` pair from the last row it read, never the bound
and never the clock time of the run, so the next run resumes exactly after
that row. The longest transaction is visible in `pg_stat_activity` (see the
query below), and the application's owners usually know it. Where that cannot
be bounded, re-read an overlap window on every run and let the downstream
merge, keyed on `id`, absorb the repeats. An overlap is only safe when the merge is idempotent.

### Writes that do not touch `updated_at`

The column moves only if every write path moves it. Check how it is
maintained before relying on it:

```sql
SELECT tgname, pg_get_triggerdef(oid)
FROM pg_trigger
WHERE tgrelid = 'public.orders'::regclass AND NOT tgisinternal;
```

A trigger that sets it on every `UPDATE` is reliable. If the application sets
it instead, any bulk fix, admin script or second service that writes the table
without it produces changes the extraction never sees. Say so, and either ask
for a trigger or plan a periodic full comparison of keys and a checksum.

### Deletes

A deleted row has no `updated_at` to find. A watermark extraction sees deletes
only if the application soft-deletes (sets a `deleted_at` and keeps the row).
If it hard-deletes and the warehouse must reflect that, the options are a
periodic comparison of the full key set, or change data capture through logical
decoding (Debezium or a similar connector), which also gives every intermediate
version of a row. That is a different tool, and it needs a replication slot
the source's owners must agree to, because an unread slot keeps WAL on the
primary until the disk fills.

### Smaller traps

- Keep the watermark as `timestamptz` end to end. A `timestamp without time
  zone` column is interpreted in the session's `TimeZone`, so a job and an
  application in different zones, or a daylight-saving change, shift the
  window by hours.
- PostgreSQL stores microseconds. A watermark that passes through something
  with millisecond precision (a JavaScript client, some JSON serialisers)
  comes back truncated, and the next run re-reads or skips the rows in that
  millisecond.
- List columns rather than `SELECT *`. A column added to the source then stays
  out of the extract until someone adds it on purpose, instead of changing the
  shape of the load without warning.

## Read the plan before the job runs at scale

Plain `EXPLAIN` shows the plan the planner chose and its estimates, and runs
nothing. Start there. For the keyset query above, the plan you want is a
`Limit` over an `Index Scan` on `(updated_at, id)` whose `Index Cond` contains
the row comparison, with no `Sort` node. A `Sort` over a `Seq Scan` means every
batch reads and sorts the whole table to return ten thousand rows, and the job
gets slower as the table grows, not as the change volume grows.

Then run `EXPLAIN (ANALYZE, BUFFERS)` on one bounded batch, which executes it
(see above), and read it node by node:

- **Estimated rows against actual rows.** A gap of ten times or more means the
  planner is choosing from wrong numbers: statistics that are stale (`ANALYZE`
  the table), correlated columns it treats as independent (`CREATE
  STATISTICS`), or a plan made for a different parameter value.
- **`Seq Scan` on a large table with a selective filter**, or a high `Rows
  Removed by Filter`: no index matches the predicate. A sequential scan is
  correct when the query reads most of the table, as a first full load does.
- **`Nested Loop` with a large `loops` count and a `Seq Scan` inside it**: the
  join column of the inner table has no index, so it is scanned once per outer
  row. `Hash Join` and `Merge Join` are normal for large inputs.
- **`Sort Method: external merge  Disk`**: the sort spilled because it did not
  fit in `work_mem`. An index that delivers the order removes the sort.
- **`Buffers: shared hit` and `read`**: `hit` came from PostgreSQL's cache,
  `read` from the OS cache or disk. A batch with many reads is pulling cold
  pages that the application's own queries then have to read back in.
- **`actual time` multiplied by `loops`.** Times on an inner node are per loop.
  The slowest node is often not the top one.

Plans depend on data volume, so a plan read on a development copy with a
thousand rows says little about production. And a query sent with bind
parameters as a prepared statement is planned for its actual values for the
first five executions, after which PostgreSQL may switch to one generic plan
for all values. If the job is fast in tests and slow after a while in
production, compare the plan for literal values with `EXPLAIN EXECUTE` on the
prepared statement.

Predicates the index cannot use look harmless in SQL:

- **A function on the indexed column.** `WHERE date(updated_at) = :day` cannot
  use an index on `updated_at`; `WHERE updated_at >= :day AND updated_at <
  :day + interval '1 day'` can.
- **A type mismatch.** A `bigint` column compared with a `numeric` parameter
  is cast on every row, and the index is skipped. Bind parameters with the
  column's type.
- **`NOT IN (subquery)`** returns no rows at all when the subquery yields a
  `NULL`, which is a wrong result before it is a slow one. Use `NOT EXISTS`.

`pg_stat_statements`, when the source has it installed, records every
statement's total time, calls and buffer reads. It shows what the extraction
costs the source across runs, which one `EXPLAIN` cannot.

## The indexes an extraction needs

An index is the owner's decision, because every index slows every write to the
table and takes space. Propose one only when the plan shows the job needs it,
and say what it costs.

**Column order decides what an index serves.** Equality columns go first, then
the range or sort column, then the tie-breaker. `(tenant_id, updated_at, id)`
serves an extraction per tenant, and serves `tenant_id = ?` alone, but is of
little use for `updated_at` without a tenant. Before PostgreSQL 18 the planner
can only read the whole index for that condition; from 18, a B-tree skip scan
can use it, and pays off only when `tenant_id` has few distinct values. An index can also deliver
`ORDER BY` only when the columns and directions match it, or are all exactly
reversed.

Before proposing a new index, look for one that already fits:

```sql
SELECT indexrelid::regclass AS index, pg_get_indexdef(indexrelid), idx_scan
FROM pg_stat_user_indexes JOIN pg_index USING (indexrelid)
WHERE relid = 'public.orders'::regclass;
```

`idx_scan` also shows the owner which indexes nobody uses, but it counts only
since the statistics were last reset (`stats_reset` in `pg_stat_database`).
An index with `idx_scan = 0` is unused only if that period includes month-end
and other rare workloads.

Kinds worth knowing for extraction:

- **Partial**, such as `ON orders (updated_at, id) WHERE status <> 'archived'`,
  is small and cheap to maintain, but the planner uses it only when the query's
  `WHERE` clause implies the index's condition.
- **Covering**, with `INCLUDE (col, ...)`, lets the scan answer from the index
  alone. That works only for pages the visibility map marks all-visible, which
  needs a recent vacuum. On a table that is updated constantly, `Heap Fetches`
  in the plan shows the scan going back to the table anyway.
- **BRIN** is tiny and suits a column whose values follow the physical order
  of the rows, such as `created_at` on an insert-only event table. It does not
  suit `updated_at` on a table whose rows are updated, because an updated row
  is not moved to the end of the table.
- A single-column index on a boolean or a small enum is rarely chosen by the
  planner. Make it partial or part of a composite.

### Creating one without blocking the application

A plain `CREATE INDEX` blocks every write to the table until it finishes, which
on a large table is an outage. `CREATE INDEX CONCURRENTLY` lets writes
continue. It takes longer, scans the table twice, waits for transactions that
were already running (including a long extraction), and cannot run inside a
transaction block, so migration tools need it in a migration of its own with
the transaction turned off. If it fails, it leaves an `INVALID` index that
still slows writes; find it with `pg_index.indisvalid = false`, drop it, and
retry.

Set `lock_timeout` (a few seconds) in the session that runs any DDL. A
statement waiting for a lock holds its place in the queue, and every query that
arrives after it waits behind it, so an `ALTER TABLE` stuck behind one long
transaction stops the whole application. With a timeout it fails fast, and can
be retried at a quieter moment.

## Do not hurt the source

### Long transactions

PostgreSQL keeps old row versions for as long as any open transaction might
still need them. One transaction open for hours stops vacuum from removing
dead rows anywhere in the database, so the application's busiest tables bloat
and its queries slow down, and the cause is a session that looks idle.

The common way an extraction does this is by accident. psycopg (versions 2
and 3) and SQLAlchemy open a transaction on the first statement and keep it
open until a commit or rollback, so a job that reads a batch and then spends
an hour writing it to the warehouse sits `idle in transaction` for that hour.
Commit or roll back after each read, or use autocommit for read-only work.

The same reasoning sets the shape of a large read. One `SELECT` over a big
table, a server-side cursor walked for hours, or `COPY (SELECT ...) TO STDOUT`
for a full load each keep one snapshot open for the whole read. Keyset batches
are separate short statements, so no snapshot outlives a batch. The price is
that batches do not see one consistent moment; for a watermark extraction that
is fine, because a row changed mid-run is picked up by the next run. When
several tables must be read as of one moment, `REPEATABLE READ` gives that,
and holds the snapshot for as long as the read takes. Choose it knowingly.

A long read also blocks the application's deployments: most forms of `ALTER
TABLE` need a lock that conflicts with every read, so the migration waits for
the extraction, and the application's queries queue behind the migration.

### Timeouts on the job's role

Ask for these on the job's role, so they apply however the job connects:

```sql
ALTER ROLE etl_reader SET statement_timeout = '15min';
ALTER ROLE etl_reader SET idle_in_transaction_session_timeout = '5min';
ALTER ROLE etl_reader SET lock_timeout = '10s';
```

`statement_timeout` caps any single query, so a plan that went wrong ends as
an error instead of a scan that runs all night. `idle_in_transaction_session_timeout`
closes a session left in an open transaction, which is the vacuum problem
above. `lock_timeout` makes the job fail instead of queueing behind DDL. Pick
values from the job's real batch times, with margin. Settings on the role
survive connection poolers in transaction mode, where a `SET` issued by the
session may land on a different server connection.

Set `application_name` in the job's connection string, so the owners can
tell its sessions apart from their own.

### Watching it

```sql
SELECT pid, usename, application_name, state,
       now() - xact_start AS xact_age, wait_event_type, wait_event,
       pg_blocking_pids(pid) AS blocked_by, left(query, 80) AS query
FROM pg_stat_activity
WHERE backend_type = 'client backend' AND xact_start IS NOT NULL
ORDER BY xact_start;
```

The oldest transactions come first. `idle in transaction` with a large
`xact_age` is the vacuum problem; a non-empty `blocked_by` shows who is waiting
for whom. Run it during an extraction, not only after a complaint.

### Connections

Every connection is a server process with its own memory, and the source's
`max_connections` is shared with the application. Count everything the
extraction opens at once: pool size times the number of workers, plus every
parallel task. A Spark JDBC read with `numPartitions = 32` opens 32 connections
and runs 32 range scans on the source at the same time, which is fast for the
job and a load spike for everyone else. Keep the total well below
`max_connections` minus the connections reserved for superusers and the
application's own peak.

The same Spark read needs `fetchsize` set. Without it, the PostgreSQL JDBC
driver reads each partition's whole result into executor memory before
returning a row. psycopg's default cursor does the same on the client; keyset
batches with `LIMIT` bound it either way.

If the source sits behind PgBouncer in transaction pooling, session state does
not survive between transactions: session-level `SET`, `WITH HOLD` cursors,
advisory locks, and prepared statements on PgBouncer versions before 1.21 or
without `max_prepared_statements`. Role settings and per-transaction `SET
LOCAL` work.

## Reviewing an existing extraction

| In the job | Why it goes wrong |
|---|---|
| `LIMIT ... OFFSET` paging | Cost grows with depth; concurrent writes shift rows between pages |
| `updated_at > :last` with no `id` | Rows sharing a timestamp at a batch edge are skipped |
| Upper bound at the current time | Transactions that commit late are skipped forever |
| Watermark set to the run's clock time | Same as above, and wrong on a lagging replica |
| A function on the watermark column | The index is not used and every batch scans the table |
| `COUNT(*)` before every batch | A full scan per batch, for a number the loop does not need |
| One transaction or cursor for the whole run | Vacuum stalls on the source for the run's duration |
| Client left `idle in transaction` between batches | The same, while the job does unrelated work |
| `SELECT *` | Source schema changes alter the load without review |
| More parallel readers than the source's spare connections | Connection exhaustion for the application |

## Verify before calling it done

- `EXPLAIN` of the batch query shows the index scan and no sort, and the time
  per batch stays flat from the first batch to the last.
- For one closed window, the number of rows extracted equals `count(*)` for
  that window on the source (on the replica, bounded by the same predicate).
- Running the same window twice yields the same rows, and the downstream merge
  leaves the target unchanged the second time.
- During a run, `pg_stat_activity` shows the job's sessions as short
  statements, never `idle in transaction` for longer than one batch's write.

Report what you measured and on which data. A plan read on a small copy, or a
single fast run on a warm cache, is not evidence that the job is safe on
production; say so when that is all you have.
