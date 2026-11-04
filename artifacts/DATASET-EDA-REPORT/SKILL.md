---
name: dataset-eda-report
description: Writing the picture of a dataset a later dashboard can be based on: grain, coverage, distributions, declared and inferred relationships, and the questions the data can and cannot support. Use when an analyst needs that picture before deciding what to build.
---

# Writing the picture of a dataset

This report answers what the dataset is and which questions it can support.
It is the picture a later dashboard is based on. It is not a review of a
pipeline run, and it does not need a baseline to exist.

Its neighbours:

- The missing rates, the placeholders, the duplicate claims and the outliers
  are [dataset-quality-assessment](../DATASET-QUALITY-ASSESSMENT/SKILL.md).
  Cite that assessment. Do not recompute the same tables here. Two
  computations of the same rate will drift, and the dashboard will be built
  on whichever one was written last.
- Reviewing one pipeline run against a contract is
  [pipeline-output-review](../PIPELINE-OUTPUT-REVIEW/SKILL.md). That review
  is of a run, and its honest verdict when the baseline is missing is that
  drift was not assessed. This report is of a dataset. Absence of a baseline
  is stated. It is not a failed review.
- The pages and measures someone could build from this picture are
  [dashboard-concept-draft](../DASHBOARD-CONCEPT-DRAFT/SKILL.md). That draft
  consumes this report. It does not rediscover the grain.

## Start from the assessment

If the assessment does not exist yet, run it first, or mark the sections that
depend on it as insufficient evidence. A distribution written on top of an
unprofiled column is a guess about the column, and it reads like a finding.

Inherit the assessment's source block unchanged: class, object name, grain,
population versus sample, what was not seen. The class rules live once, in
[references/sources.md](../DATASET-QUALITY-ASSESSMENT/references/sources.md).
Do not reclassify the source to make a later chart possible. If that file is
not available, the source class is insufficient evidence. Do not reconstruct
the five classes from memory.

## What a row is

Say what entity each row is, the grain, and the time coverage: the minimum,
the maximum, the gaps, and freshness if a timestamp exists.

A gap is a period the coverage claims and the data does not contain. A
minimum and a maximum with a hole between them is not continuous coverage,
and a chart that draws the hole as zero has invented a value. Freshness is
the distance from the latest timestamp to when you read it, and only if a
timestamp exists. If there is no timestamp, say there is no freshness to
report. A file's modified time is the file's time, not the data's. Label it
as the file if you mention it at all.

If the grain was an assumption in the assessment, it is still an assumption
here. A question that needs a grain nobody stated is a question the dataset
cannot support yet. Say that, rather than picking a grain because a chart
needs one.

## Distributions

Describe the main distributions: concentration, where one category dominates;
heavy tails; and units. Name the unit of each measure. A measure without a
unit cannot become a KPI later, because "better" has no direction until you
know whether the number is a currency, a count, a duration or a ratio. A
heavy tail is why a mean will not represent the column. Say so, and leave
the outlier table in the assessment. Cite the method and the count. Do not
recompute them.

Concentration matters for the same reason a flat missing rate hides a broken
source. An aggregate that is one category is not a property of the dataset.
It is a property of that category. The segment section is where that goes.

## Relationships

Declared relationships are the ones the source says exist: a model
relationship, the joins written in a view's SQL, a SharePoint lookup. Label
them declared. Inferred relationships are the ones you noticed: a name match,
an inclusion rate. Label them inferred, and give the evidence. A name match
is a hypothesis. An inclusion rate is how often the child's key is found in
the parent, which is evidence of overlap, not a declaration that the join is
the grain.

Never upgrade an inferred join to a declared one. The upgrade is how a
guess becomes a page someone builds. A flat file has no declared
relationships. Any join used on one stays inferred, which the source
contract already says. Repeat the label here. Do not quietly drop it because
the inclusion rate was high.

## Segments worth splitting by

Name the segments where the aggregate hides a different picture. The reason
is the same as in the assessment: a rate that is calm overall can be one
segment that is broken, and the calm number is what a single KPI would show.
A segment is worth splitting by when the decision would change if that
segment were looked at alone. A segment that moves the number by a rounding
error is not.

## Questions it can support, and questions it cannot

A question it can support names the column and the grain it uses, and any
quality finding that limits that use. A clean column needs no finding
attached to it. A question it cannot support is tied to a missing column, a
broken grain, or a finding in the assessment. That question is a finding. It
is not a request to go and add the column.

## Baseline

This report does not need a baseline. If a baseline is present, a short
drift note is allowed, and it must name the baseline's date. A comparison
against "last time" with no date is not a comparison. If no baseline is
present, say there is no baseline. Do not borrow a pass or fail from a
pipeline review. There is no threshold here unless someone stated one, and
an unstated threshold is a verdict you invented.

## What was not seen

List it. The unseen items from the source block belong here as well as in
the assessment: the base tables behind a view, the role you were not in, the
partitions you were not shown, the list behind a capped view. A reader of
this report should not have to open the assessment to learn what the picture
leaves out.

```markdown
## EDA: <object>

### Source
<the assessment's block, unchanged>
Assessment: <where it is, or "not run; sections below that need it are insufficient evidence">

### Grain and coverage
- Entity each row is:
- Grain, and who stated it:
- Time: min, max, gaps, freshness (or "no timestamp"):

### Distributions
| Measure or category | Unit | Shape (concentration, tail) | Cited quality finding |
|---------------------|------|-----------------------------|-----------------------|

### Relationships
| From | To | Declared or inferred | Evidence |
|------|----|----------------------|----------|

### Segments the aggregate hides
| Segment | What the aggregate hides |
|---------|--------------------------|

### Questions
| Question | Can support? | Tied to |
|----------|--------------|---------|

### Baseline
<none, or a drift note that names the baseline's date>

### Not seen
-
```
