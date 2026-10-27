---
name: spark-job-tuning
description: Tuning a slow or memory-failing Spark job from its Spark UI evidence - finding the stage that dominates, naming the cause (skew, a missed broadcast, a fanning-out join, partition size, driver-side work, Python UDFs), fixing that cause and re-measuring. Use when a PySpark, Scala Spark or Spark SQL job is slow, spills, runs out of memory, or a stage waits on a few straggler tasks.
---

# Tuning a Spark job

A Spark job that is slow has one stage, and usually one cause, that accounts for
most of its time. The Spark UI records which. Read it before changing any setting:
a config change made on a guess either does nothing or moves the cost somewhere
harder to see, and a job tuned that way stays fragile because nobody knows which
change mattered.

The order is fixed: collect the evidence, name the dominant cause, fix that cause,
then measure again on the same input.

## Collect the evidence

Open the Spark UI for the run: the driver's UI while the application is alive, the
History Server afterwards (it needs `spark.eventLog.enabled=true` and an event log
directory the server reads), or, on Databricks, the Spark UI link on the cluster or
job run page. If none of these exists, enable event logging and run the job once
more; diagnosing without them is guessing.

**Start with the Jobs timeline, not with a stage.** Look for gaps where no stage is
running. Time in a gap is spent outside the executors: on the driver in plain
Python, in `collect()` or `toPandas()`, listing millions of files, or waiting for
executors to be granted. No Spark setting shortens it, so a job that is mostly gaps
is a driver or cluster problem, and tuning stages would be wasted work.

**Then find the stage that dominates wall-clock time.** On the Stages tab, sort by
duration. Open that stage and read three things:

- **Summary metrics for completed tasks.** The min, 25th percentile, median, 75th
  percentile and max of task duration, shuffle read size, spill and GC time. This
  table is where skew shows up, and nothing else shows it as directly.
- **Shuffle read and write totals.** How much data the stage moved across the
  network. A large shuffle on a join is the usual cost to remove.
- **Spill (memory and disk).** Spill means a task's working set did not fit in its
  execution memory. Whether that is a sizing problem or a query problem depends on
  what came before it, which the next tab answers.

**Then the SQL / DataFrame tab for the query that stage belongs to.** It shows the
physical plan with runtime metrics on each node: rows in and out of every join,
files and bytes read by every scan, and the join strategy actually used. With
adaptive query execution (AQE) on, this is the final plan; `df.explain("formatted")`
before a run shows only the initial one, marked `isFinalPlan=false`, and AQE may
replace its joins at runtime.

The Executors tab completes the picture: GC time as a share of task time, and
whether one executor is consistently slower than the rest.

## Name the dominant cause

Match the evidence to a cause before touching code. The fixes differ, and several
of them make a different cause worse.

| Evidence | Cause |
|---|---|
| Long gaps between stages on the Jobs timeline | Driver-side work or waiting for executors, not Spark execution |
| In one stage, max task duration far above the median, and the same task's shuffle read far above the median | Skew: one key holds a large share of the rows |
| Max duration far above the median but shuffle read even across tasks | A slow executor or GC pressure, not skew; check the Executors tab |
| A join whose output rows far exceed its larger input, followed by spill | Join fan-out: duplicate keys multiplying rows |
| A `SortMergeJoin` with one input small enough to broadcast, and a large shuffle on the other | A missed broadcast |
| Thousands of tasks lasting milliseconds each | Too many partitions for the data |
| Few tasks, each spilling, with no fan-out before them | Too few partitions for the data |
| A scan reading every file or partition although the query filters on a partition column | No partition pruning |
| `BatchEvalPython` or `ArrowEvalPython` in the plan, and the stage containing it dominates | A Python UDF on the hot path |
| A `SparkException` that serialized results are bigger than `spark.driver.maxResultSize`, or the driver dies with an out-of-memory error | Too much data pulled to the driver |

The fan-out row matters most because it is the one most often misread. Spill after
a join that multiplies rows looks like a memory problem, and more executor memory
does make the job finish. It also leaves the duplicate rows in the output, where
they become a correctness problem downstream. Check the row counts before treating
spill as a sizing question.

## Fix the cause

### Joins first

A sort-merge join shuffles both sides by the join key, so every row of the large
table crosses the network to be next to its match. When one side is small, sending
a copy of it to every executor (a broadcast hash join) removes the shuffle of the
large side entirely, which is why a missed broadcast is usually the largest single
gain available.

```python
from pyspark.sql.functions import broadcast

orders.join(broadcast(customers), "customer_id")
```

Spark broadcasts on its own when it estimates a side below
`spark.sql.autoBroadcastJoinThreshold` (10 MB by default). The estimate is made
before the job runs, so a dimension that becomes small only after a filter is
often missed. AQE corrects this at runtime from the actual shuffle size and
converts the sort-merge join to a broadcast, though later than planning the
broadcast from the start would.

Three limits to check. The broadcast side is collected on the driver first, so
broadcasting something large moves the out-of-memory error to the driver instead
of removing it. An outer join cannot broadcast the side it preserves (the left
side of a left join), and a full outer join cannot use a broadcast hash join at
all; Spark then ignores the hint without an error. Confirm the strategy in the
SQL tab rather than trusting the hint.

A fanning-out join is not fixed by any join strategy. Find out why the key is not
unique on the side expected to be unique, then deduplicate or aggregate that side
before the join. If the multiplication is intended, the spill is real work, and
partition sizing below is the remedy.

### Skew

Rows are sent to shuffle partitions by a hash of the key, so every row with the
same key lands in the same task. One key holding a large share of the rows makes
one task do that share of the work while the others finish and wait. More
partitions do not help; the hot key still hashes to one of them.

**Check for null keys first.** Nulls hash together, and in an inner join they never
match anything. Filtering them out before the join removes the skew and changes no
result. In an outer join, handle them separately and union them back.

**Then let AQE try.** With `spark.sql.adaptive.skewJoin.enabled` (on by default),
AQE splits a partition of a sort-merge join that is both more than
`skewedPartitionFactor` (5) times the median partition size and larger than
`skewedPartitionThresholdInBytes` (256 MB), and replicates the matching
partition of the other side. It handles sort-merge joins only. Skew in a window
partitioned by the hot key, or in an aggregation that cannot be computed partially
(`collect_list`, for example), is untouched. Ordinary `sum`, `count` and `max`
aggregations are partly protected already, because Spark aggregates within each
input partition before the shuffle.

**Salt when AQE is off or not enough.** Add a random suffix to the key on the large
side, so the hot key spreads over N partitions, and replicate the small side N
times so every suffixed key still finds its match:

```python
from pyspark.sql import functions as F

N = 16
big_salted = big.withColumn("salt", (F.rand() * N).cast("int"))
small_salted = small.withColumn("salt", F.explode(F.sequence(F.lit(0), F.lit(N - 1))))
joined = big_salted.join(small_salted, ["key", "salt"]).drop("salt")
```

The cost is the small side multiplied by N, so choose N from how far the hot task
exceeds the median, not as large as possible. For a skewed aggregation, aggregate
by key and salt first, then by key alone. That works for `sum`, `count`, `min` and
`max`, which combine from partial results; an exact distinct count does not
combine that way.

### Partition size

A task should be large enough that scheduling overhead is small next to its work,
and small enough to fit in execution memory without spilling. Around 128 MB of
input per task meets both for most jobs; it is also the default size of a file
scan split (`spark.sql.files.maxPartitionBytes`). Separately, there should be at
least two or three tasks per executor core, or some cores sit idle.

Shuffle stages use `spark.sql.shuffle.partitions`, 200 by default, regardless of
the data. That is too many for a few hundred megabytes and far too few for a few
terabytes. AQE coalesces small post-shuffle partitions towards
`advisoryPartitionSizeInBytes` (64 MB), but it only merges: it never raises the
count above the starting number except to split skew. For a large job, set the
starting count high (`spark.sql.adaptive.coalescePartitions.initialPartitionNum`
or `spark.sql.shuffle.partitions`) and let AQE bring it down.

`repartition(n)` is a full shuffle. It can raise or lower the count and leaves
partitions even, and with a column it groups rows by that column. `coalesce(n)`
only lowers the count and avoids a shuffle by merging existing partitions. The
catch is that `coalesce` creates no stage boundary, so the work before it runs
with the reduced parallelism too: `coalesce(1)` before a write can make the whole
upstream computation run in one task. When the upstream work is heavy, a
`repartition(1)` costs one shuffle and keeps it parallel.

The same distinction governs output files. Many small files slow every later read,
which is why output is often reduced before a write. To write sorted output per
partition, repartition first and then call `sortWithinPartitions`. Sorting and then
repartitioning shuffles the rows again and loses the order the sort produced.

### Pruning

A filter on a partition column lets the scan skip whole directories, but only when
Spark can evaluate it against the partition values. Compare the column directly
with a literal. Then read the scan node in the plan: `PartitionFilters` should
contain the filter, and `PushedFilters` shows what reached the file format. A
filter that appears in neither was applied after reading everything.

### Work on the driver

`collect()` and `toPandas()` copy the whole result into the driver's memory, and
the driver is one machine. Aggregate on the cluster and collect only the summary,
or write the result to storage and read it from there. Arrow
(`spark.sql.execution.arrow.pyspark.enabled`) makes `toPandas()` faster, but the
data still has to fit on the driver. Raising `spark.driver.maxResultSize` only
postpones the failure until the data grows again.

### Python UDFs

A plain Python UDF sends every row from the JVM to a Python worker process and its
result back, one row at a time. The optimizer cannot see inside it, so it cannot
push a filter through it or generate code for it. A built-in function from
`pyspark.sql.functions` stays in the JVM and avoids all of that, so check for one
first; most string, date, array and JSON transformations have one. When Python is
unavoidable, a pandas UDF exchanges data in Arrow batches and runs vectorized code
over each batch, which removes most of the per-row cost.

### Caching

`cache()` pays off when one DataFrame is used by more than one action and is
expensive to recompute. It is lazy: nothing is stored until an action runs, and a
DataFrame cached and then used once costs the memory and the write and saves
nothing. Cached data shares executor memory with execution, so caching too much
causes the spill and eviction it was meant to avoid. The Storage tab shows what is
cached and what fraction of it fits. Call `unpersist()` when the last use is past.

## Verify before claiming an improvement

Run the changed job on the same input, on a cluster of the same size, and compare
the stage that dominated before: its duration, its shuffle read and write, its
spill, and its task-duration spread. Check that the plan changed in the way the fix
intended, for example `BroadcastHashJoin` where `SortMergeJoin` was. Then compare
the output row count and a key aggregate with the previous run, because a dedup, a
null filter or a salt that is wrong changes results while making the job faster.

A changed `explain()` is a prediction, not a result. A run on smaller data, a warm
cache or an idle cluster is not a comparison either. Report the numbers you
measured and how you measured them; if you only have the plan, say that is what you
have.
