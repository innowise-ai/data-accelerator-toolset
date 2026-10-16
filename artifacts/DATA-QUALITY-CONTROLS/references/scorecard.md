# Quality scores per segment and stage

A scorecard computes the same quality measures for every segment, so each one can
be compared with the others, and for more than one stage, so the effect of a
processing stage such as cleansing or enrichment can be measured. Typical
measures: the share of records with a required field filled, the number of
children per parent (images per product, lines per order), the share of values in
a valid format, text length, the number of languages a description is available
in.

## Define each measure once

A measure definition is data: an id, the entity type and field, what is computed
(a share, a mean, a median, a count, the share above a target), which direction
is better, and an optional target. Compute it from the same definition on any
stage and for any grouping (segment, batch, entity type), and store each result
with its keys and its batch, so trends over time come for free.

Decide what "filled" means per field before computing a fill rate. An empty
string, `N/A`, `0` or a placeholder image is present but not filled, and a fill
rate that counts it overstates quality in exactly the segments that use
placeholders the most. Where validity can be checked (a check digit, a date that
parses), report "valid" separately from "present".

## Comparing a segment with all segments

Show each segment's value beside the value across all segments and the segment's
rank. Compute the cross-segment value **over segment results, not over all
records together**: the median of the segments' fill rates, not the fill rate of
the combined data. Pooled records let the largest segment set the "market" value,
and every smaller segment ends up compared with that one segment.

Report both the median and the mean across segments. One extreme segment moves
the mean and not the median, and the difference between them says how spread out
the segments are.

## Before and after a stage

Compute the same measures on the data as delivered and on the data after a
processing stage, and report the difference as that stage's uplift. The raw
measures show how good the source is; the processed ones show what users get; the
difference shows what the stage contributes.

This only works if both are computed from the same definitions over the same
records. If the processed stage has dropped quarantined records or added records
of its own, compare over the records present in both, or the uplift partly
measures which records were counted.

## Sharing a scorecard with one segment

A segment may be shown its own values, the value across all segments and its
rank, and nothing that names or reveals another segment. Removing the names is
not enough when there are few segments:

- With two segments, the mean across segments and one's own value give the
  other's value exactly.
- With three or four, the median is often another segment's own value, and a
  rank of last out of three says a lot about the other two.

Set a minimum number of segments, agreed with the project, below which shared
scorecards show only the segment's own values and trend. Produce shared exports
from a query filtered to the segment, as with the quarantine.

## One score or several

A single weighted score is easy to rank by and hard to act on: a segment that
drops two places cannot tell which measure moved. If the project wants one, the
weights are a business decision, not a technical one; ask for them, publish them,
and always show the individual measures beside the score.
