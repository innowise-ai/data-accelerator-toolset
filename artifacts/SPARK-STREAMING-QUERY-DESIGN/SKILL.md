---
name: spark-streaming-query-design
description: Designing Spark Structured Streaming queries that run outside declarative pipelines, on Apache Spark or Databricks - checkpoints and which query changes they survive, triggers including available-now, exactly-once writes to Delta and idempotent foreachBatch, watermarks and state, and Kafka and Delta source options. Use when writing or changing a readStream / writeStream query, or when one reprocesses, skips or duplicates data after a restart, falls behind, or its state keeps growing. Not for Lakeflow pipeline datasets or for tuning batch Spark jobs.
---

# Designing Spark streaming queries

A streaming query keeps its real state in its checkpoint: the offsets it has
read, the batches it has committed, and the state of every aggregation, join and
deduplication. On restart the code is replayed against that checkpoint. So the
questions that decide whether a stream is correct are about the checkpoint and
the sink, not the transformation: which checkpoint the query uses, which changes
it survives, and what the sink sees when a batch is replayed after a failure.
Most streaming incidents are one of four things: a checkpoint that was shared,
moved or deleted; a code change the checkpoint cannot survive; a `foreachBatch`
write that duplicates on retry; or state that grows without bound.

This skill covers queries you run yourself, as a job task, a notebook or a
`spark-submit` application. Neighbours:

- In Lakeflow pipelines the engine manages checkpoints and state; that is
  [databricks-declarative-pipeline-design](../DATABRICKS-DECLARATIVE-PIPELINE-DESIGN/SKILL.md),
  which also covers Auto Loader's schema handling.
- Running the query as a Databricks job task (retries, continuous jobs, compute)
  is [databricks-job-design](../DATABRICKS-JOB-DESIGN/SKILL.md).
- Spark work that is slow inside each batch is
  [spark-job-tuning](../SPARK-JOB-TUNING/SKILL.md).
- Which layer a stream reads from and writes to (bronze, silver or gold), and
  the write mode that keeps each layer safe to replay, is
  [medallion-layer-boundaries](../MEDALLION-LAYER-BOUNDARIES/SKILL.md).

## First: read the query as it is

Establish the sources, the sink, the output mode, the trigger, the checkpoint
location, every stateful operation (aggregation, `dropDuplicates`, stream-stream
join, `transformWithState`), how the query is run, and the Spark or Databricks
Runtime version. Several behaviours below changed between versions, and the
version decides which apply.

## The checkpoint is the query's identity

**One query, one checkpoint.** "Each query must have a different checkpoint
location. Multiple queries should never share the same location." Two queries
writing one checkpoint corrupt each other's offsets and state. Keep it in
durable storage owned by the job, at a path named for the query, never in a
temporary or per-user location.

**A new checkpoint is a new query.** "When you delete the files in a checkpoint
directory or change to a new checkpoint location, the next run of the query
begins fresh." Where it begins is then decided by the source's start options,
which are ignored on every normal restart:

- Kafka `startingOffsets` "only applies when a new query is started, and that
  resuming will always pick up from where the query left off". Its default for
  streaming is `latest`, so a query restarted on a new checkpoint silently skips
  everything that arrived while it was down. `earliest` re-reads the topic's
  whole retention, which duplicates an append-only target.
- Delta `startingVersion` and `startingTimestamp` likewise apply to new queries
  only.

Deleting a checkpoint to get past an error therefore always skips or repeats
data. Decide which, and say so, before doing it.

**Which code changes a checkpoint survives.** Structured Streaming identifies
sources by their position in the query plan, and state by the shape of the
stateful operations.

| Change | Restart from the same checkpoint |
|---|---|
| Add or remove a filter | Allowed |
| Change a projection, keeping the output schema | Allowed; a new schema only if the sink accepts it |
| Add, remove or reorder sources | Not allowed by default (newer runtimes allow it for named sources, opt-in) |
| Change grouping keys or aggregates, join type, or deduplication columns | Not allowed |
| File sink to Kafka sink | Allowed; Kafka sees only new data |
| Kafka sink to file sink | Not allowed |
| State store provider | Not allowed |

A change the checkpoint cannot survive is a migration, not a deployment: a new
checkpoint, an explicit start position, and a decision about the gap or overlap
that creates, made before the change ships.

## Triggers

| Trigger | Behaviour | Use for |
|---|---|---|
| Default | A micro-batch as soon as the previous one ends | Low latency on always-on compute |
| `processingTime` | A micro-batch at a fixed interval | Steady latency at lower cost |
| `availableNow` | Processes everything available at start, in batches that respect the rate limits, then stops | Incremental batch on a schedule |

`availableNow` gives the same exactly-once bookkeeping as a long-running stream,
with compute only while it runs. Use it for most "every 15 minutes" or nightly
incremental loads. The older `once` trigger is deprecated; replace it with
`availableNow`, which also honours `maxFilesPerTrigger` and
`maxOffsetsPerTrigger` instead of reading everything in one batch.

Two platform limits:

- **Serverless.** Serverless notebooks and jobs support only `availableNow` (and
  the deprecated `once`). A query with a processing-time trigger needs classic
  compute.
- **Continuous trigger.** This is experimental in Apache Spark and not supported
  on Databricks, which offers real-time mode for low latency instead. Real-time
  mode has its own limits: Kafka, Event Hubs or Kinesis sources, Kafka or
  `foreach` sinks, update output mode, no Delta source or sink, and no serverless.
  Check them before choosing it.

## Exactly-once depends on the sink

End-to-end exactly-once needs a replayable source and an idempotent sink. A
batch that failed is replayed from the checkpoint, so whatever the sink did
before the failure happens again.

- **Delta sink.** "The Delta Lake transaction log guarantees exactly-once
  processing." A plain `writeStream` to a Delta table is safe on replay.
- **Kafka sink** is at-least-once. Consumers must tolerate duplicates.
- **`foreachBatch`** "provides only at-least-once write guarantees". Whatever the
  function writes is written again when the batch replays. Make each write
  idempotent: either merge on a key, or pass the Delta writer options
  `txnAppId` (a fixed string per query) and `txnVersion` (the batch id), which
  make Delta ignore a write it has already committed:

```python
APP_ID = "orders_to_silver"  # fixed for this query and this checkpoint

def write_batch(batch_df, batch_id):
    (batch_df.write.format("delta")
        .option("txnAppId", APP_ID)
        .option("txnVersion", batch_id)
        .mode("append")
        .saveAsTable("silver.orders"))

(spark.readStream.table("bronze.orders")
    .writeStream
    .foreachBatch(write_batch)
    .option("checkpointLocation", "/Volumes/main/checkpoints/orders_to_silver")
    .trigger(availableNow=True)
    .start())
```

Every write inside the function needs its own idempotency. With a new
checkpoint, batch ids restart at 0, so change `txnAppId` too. Otherwise Delta
treats every new batch as one it has already written and silently skips it.

**Let the query fail.** Do not catch and retry exceptions inside the query.
Databricks recommends letting it "fail fast" and relying on the orchestration
layer to restart it, which restarts from the checkpoint with the guarantees
above. A retry inside `foreachBatch` repeats writes outside them.

## Sources

**Kafka.**

- `failOnDataLoss` defaults to `true`; keep it on in production. When messages
  expire before the query reads them, it fails instead of skipping them.
  Switching it off turns that data loss into silence.
- `maxOffsetsPerTrigger` bounds a batch. Set it, so that the first run, or a run
  catching up after downtime, does not try to read the whole backlog at once.
- `minPartitions` is a hint for read parallelism.

**Delta.**

- The source accepts appends only. "Structured Streaming only accepts append
  inputs and throws an exception if any modifications occur." `skipChangeCommits`
  ignores commits that update or delete rows. The query then keeps running, but
  those changes never reach the target, so use it only when that is intended.
- `maxFilesPerTrigger` (default 1000) and `maxBytesPerTrigger` (a soft limit)
  bound a batch; with both set, whichever is reached first applies.
- If the source table's schema changes after the stream starts, the query fails;
  restart it.
- A stream that falls further behind than the source's retention (`VACUUM`, 7
  days by default, and the log, 30 days) fails with `DELTA_FILE_NOT_FOUND_DETAILED`
  and has to start again from a new checkpoint. Do not set
  `spark.sql.files.ignoreMissingFiles` to `true` to get past it.

**Files with Auto Loader.** Outside a pipeline, set `cloudFiles.schemaLocation`
yourself; the schema decisions in
[databricks-declarative-pipeline-design](../DATABRICKS-DECLARATIVE-PIPELINE-DESIGN/SKILL.md)
apply unchanged.

## State and watermarks

Stateful operations keep state in the checkpoint's state store, and without a
bound that state grows for as long as the query runs. A watermark
(`withWatermark("event_time", "2 hours")`) is that bound. State older than the
watermark can be dropped. Data later than the threshold "will start getting
dropped", but that is not guaranteed: it may still be aggregated. Treat the delay
as the lateness you accept, not as an exact cut-off.

- **Aggregations** in append mode use the watermark to finalise and drop old
  windows. Complete mode never drops state.
- **Deduplication** without a watermark keeps every key forever. Use
  `dropDuplicatesWithinWatermark`, or include the event-time column with a
  watermark.
- **Stream-stream joins.** Watermarks and event-time conditions are optional for
  inner joins but required for outer and semi joins. Without them even an inner
  join keeps every row on both sides.
- **The delay is a trade.** A longer delay accepts later data, but holds more
  state and, in append mode, delays output by the same amount.

For large state, use the RocksDB state store. It is the default from Databricks
Runtime 17.3 LTS, and opt-in before that, together with changelog checkpointing.
The provider cannot change between restarts, so choose it before the first run.

## Output modes

Append writes only new final rows, update writes rows changed since the last
trigger, and complete rewrites the whole result (aggregations only). A Delta sink
takes append or complete. To apply updates to a Delta table, use `foreachBatch`
with a `MERGE`, made idempotent as above. A file sink supports append only.

## Monitoring

Name every query with `.queryName(...)`, so that its metrics and its tab in the
Spark UI can be told apart. In the progress metrics, or through a
`StreamingQueryListener`, watch:

- `inputRowsPerSecond` against `processedRowsPerSecond`. Input persistently
  above processing means the query is falling behind.
- `batchDuration` against the trigger interval.
- For a Delta source, the backlog: `numBytesOutstanding` and
  `numFilesOutstanding`.
- In `stateOperators`, `numRowsTotal` and `memoryUsedBytes`. Growth that never
  levels off means a missing or too generous watermark.

## What this skill changes

This skill writes streaming code. The following change what data the target
receives, so each one is done only with the user's confirmation, stating what it
will reprocess or skip:

- starting a query on a new or deleted checkpoint;
- changing `startingOffsets`, `startingVersion` or `startingTimestamp`;
- setting `failOnDataLoss` to `false` or adding `skipChangeCommits`;
- changing `txnAppId`.

Production starts and restarts go the same way.

## Verify before handing over

1. Run the query in development with `availableNow` on a fresh checkpoint. Run
   it again with no new input and confirm the target did not change.
2. Make the batch fail after its write, for example by raising an error at the
   end of `foreachBatch`, then restart. The target must have no duplicates.
3. For a code change, place it in the table above. If the checkpoint cannot
   survive it, write the migration plan instead of deploying.
4. For a stateful query, run several batches and confirm the state metrics level
   off.
5. Report the runtime version tested on, and anything only reasoned about rather
   than run.
