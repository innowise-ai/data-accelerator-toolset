# Comparing the next publish with the last one

Before a segment's data is published, compare what is about to be published with
what was published last time for that segment. The point is to catch problems on
the source's side that no record rule can see, because every record is valid on
its own: a fifth of the records missing, every price up 40%, a field that was
filled yesterday now empty everywhere. The same comparison confirms that an
expected change has arrived, such as a newly agreed field now filled.

## What is compared with what

**The validated state of the batch** (after quarantine) **against the last
published snapshot of the same segment.** Not against the previous batch: that
batch may never have been published, and the question is what users will see
change.

Three things must hold for the numbers to mean anything:

- **Structural failures stop the batch before this point.** A dropped column
  otherwise reports the field as removed from every record.
- **Quarantined records are reported separately, not as deletions.** An order
  that failed validation is not gone; it is waiting for a fix, and its published
  version stays where it was. Counting it as deleted puts a data problem in the
  wrong column and makes real deletions harder to see.
- **Deletion follows the project's rule.** If a record missing from one batch is
  only deleted after several batches without it, the comparison reports it as
  "missing, not yet deleted" until then.

## What to report, per segment and entity type

| Measure | Content |
|---|---|
| Volume | Previous count, new count, added, deleted, changed, unchanged, as numbers and as a share of the previous count |
| Fields | For each field, the share of existing records where a value was added (empty before, filled now), removed (filled before, empty now) or modified |
| Numeric fields | Mean and median relative change, a distribution of changes, the largest increases and decreases, and the number beyond an outlier threshold |
| Children | Children added and removed, and parents whose set of children changed |
| Validation | Records quarantined in this batch, by rule and entity type |

Define "changed" once, before the first report. Decide which differences count:
trailing spaces, letter case, `1.0` against `1`, a reordered list. Without a
normalisation rule, a source that reformats a column reports every record as
changed, and the report stops being read.

A relative change is undefined when the previous value is zero or empty. Report
those records as their own group rather than as infinite growth or as zero.

## Thresholds flag a run, they do not block it

Each measure can have a warning threshold: deletions above 5%, mean price change
above 10%, a field's fill rate down by more than 20 points. Keep them in
configuration with a global default and per-segment overrides, because what is
normal differs by segment: a source that replaces its whole range every season
would trip a global deletion threshold every season.

A crossed threshold marks the run as needing attention. Whether that also stops
the publish is the gate, below.

## Snapshots make bundles and gates possible

Store each published state of each segment as a versioned snapshot, and each
batch's validated result as a pending state. Two things become possible that are
not possible otherwise.

**Releasing several batches together.** If batches accumulate for a week before
publishing, compare the **latest pending state with the last published
snapshot**, not each batch with the one before. Changes inside the week cancel
out: a value changed on Monday and changed back on Wednesday is no change to
users, and summing batch-to-batch differences would report it twice.

**An approval gate.** The publish step reads a mode per segment: automatic, or
waiting for approval. Build the step with that switch from the beginning, set to
automatic, and the gate can be turned on for one segment later without rebuilding
anything. While it is off, the comparison is information; that is still worth a
great deal.

Record every publish: who or what published it, when, which batches it included,
and which comparison they saw. Without that record, nobody can later tell whether
a bad publish was approved with the warning visible or went out without anyone
looking.
