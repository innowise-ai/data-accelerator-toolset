---
name: dataset-quality-assessment
description: Judging which columns of a dataset can be trusted before any chart or metric, including missing values, placeholders kept apart from real zeros, duplicates at a stated grain, and outliers kept apart from domain-impossible values. Use when an analyst has a dataset and needs to know which columns can be trusted before building a chart or a metric.
---

# Assessing a dataset before analysis

A chart will happily plot a column that is mostly a placeholder, and a metric
will happily double-count a fact whose join fanned out. The overall rate can
look fine while one file, one segment or one month is empty. This is a
read-only judgement for the person about to analyse. It changes nothing: no
quarantine table, no published state, no test in a project.

This skill covers that judgement. Its neighbours:

- Building quarantine, a release diff and per-source scorecards into a pipeline
  is [data-quality-controls](../DATA-QUALITY-CONTROLS/SKILL.md). Those controls
  run on every delivery and stop or quarantine records. This assessment runs
  once, on the dataset in front of the analyst, and it writes a judgement
  rather than a table the pipeline owns.
- Reviewing what one pipeline run produced, against a contract and usually a
  baseline, is [pipeline-output-review](../PIPELINE-OUTPUT-REVIEW/SKILL.md).
  That review needs a run. This assessment does not: a file with no previous
  version is still a dataset, and the absence of a baseline is not a gap here.
- Column tests declared on dbt models are
  [dbt-model-testing](../DBT-MODEL-TESTING/SKILL.md). A failing test fails a
  build. This writes something a person reads before they chart, and it does
  not add a test.

The written picture of the dataset, and the dashboard backlog built from it,
are [dataset-eda-report](../DATASET-EDA-REPORT/SKILL.md) and
[dashboard-concept-draft](../DASHBOARD-CONCEPT-DRAFT/SKILL.md). They cite this
assessment. They do not recompute it.

## Classify the source before any check

The class decides what a count means. A rate on a filtered export is not a rate
on the system, and a duplicate count taken after a relationship has multiplied
rows is not the table's grain. The column rules below are the same once the
class is known. Only the way you reach the rows changes.

The five classes (a flat file, a queryable table or view, SharePoint, a
published Power BI semantic model, a published Tableau data source) and what
to do when the source cannot be read are in
[references/sources.md](references/sources.md).

If the source cannot be read, stop. Ask for the smallest substitute that still
supports the claim: column names and types, the row count, a sample, the
stated grain, and any declared relationships. Do not invent a schema. Do not
ask for secrets or connection strings.

Record the class, the object name, the grain, whether the profile is the
population or a sample, and what you could not see. The later skills inherit
that block unchanged.

## Missing values

Null, blank, and whitespace-only are missing. A value that is present and
empty of meaning is not missing; that is the next section. Mixing the two
hides both: a column of `N/A` looks complete, and a column of blanks looks
like a placeholder problem when the feed simply did not send the field.

A count of nulls is not the missing rate. Blank and whitespace-only are
present to a null count. Say which predicate separated them.

Report the rate, and whether the missingness clumps in one segment, one file,
or one time slice. A flat overall rate hides a broken source. Two percent
missing overall can be one file that arrived empty, or one month after a feed
changed. The clump is the finding. The overall rate without the slice is how
that source looks healthy.

## Placeholders, kept apart from missing

A placeholder is a value that is present and still empty of meaning. Typical
ones are `0` used as unknown, `N/A`, `-1`, `1900-01-01`, `9999-12-31`, a
single repeated string, a default image.

Decide per column what "filled" means before computing a fill rate, and write
that decision down. The decision is part of the result. A later reader cannot
tell a high fill rate from a high placeholder rate unless the decision sits
next to the number. This is the same decision a pipeline scorecard has to
make, for the same reason: counting a placeholder as filled overstates quality
exactly where placeholders are used most. Here it is written once, for the
person about to analyse, not stored as a measure the pipeline recomputes.

A zero in a measure column can be a real zero. A zero in an identifier is not.
Report a zero rate where zero is meaningful, and a placeholder rate where the
same character stands in for unknown. A column can need both: a quantity can
be genuinely zero and also carry `-1` as unknown. One rate cannot say which.

## Duplicates are three claims

Name which claim failed. A key duplicate and an exact duplicate have different
fixes, and a finding that only says "duplicates" sends the reader to the wrong
one.

**Exact duplicate rows.** Every column agrees. The grain is not in question.
The usual fix is to drop the copy, once you know the copy is not a second
delivery you were meant to keep.

**Duplicate business keys at the stated grain.** The rows differ, and the key
that should identify one entity identifies two. The fix is the grain or the
key, not a deduplication of identical rows. Dropping one of them deletes a
real difference.

**Fan-out from a join or a relationship.** One parent, many children, counted
as if they were one. The rows are not duplicates of each other. The
relationship multiplied them, and a sum at the parent's grain counts each
child's parent again. The fix is the join or the grain of the count. Dropping
rows would delete real children.

If nobody stated the grain, the grain is an assumption and every duplicate
result is conditional on it. Say so on the finding. A footnote is easy to
miss, and a conditional result read as a fact will be "fixed" by deleting
rows that were never duplicates.

An approximate distinct count can show that a column is nowhere near unique.
It cannot clear a key. Clearing a key is an exact comparison of row count to
distinct keys. Where that would be a full scan the user has not agreed to,
the claim stays insufficient evidence.

## Outliers

State the method: a fence, a quantile, or a domain bound such as a negative
quantity or a date in the future. A statistical outlier is a candidate, not a
defect. The row may be the one the dataset exists to show, the large order
or the new region, and calling it invalid throws away the signal.

Keep domain-impossible values in their own list. A negative quantity, a date
in the future on a column that is a completed event, a percentage past the
bound the definition allows: those are defects, and they are defects whether
or not a fence would have caught them. A fence will also flag the legitimate
tail, so the two lists must not be merged.

If no domain bound was given, say the check was statistical only. Do not
promote a fence result into "invalid".

## What to report, every time

- The source class, and exactly what was read: the file, the query, the field
  list, the model extract. The row count of what was profiled, and whether
  that was the population or a sample.
- The grain you assumed, and who stated it. If nobody stated it, say the grain
  is an assumption.
- A column table: type, missing rate, placeholder rate, zero rate where zero
  is meaningful, distinct count, min/max or top values. The "filled" decision
  sits on the same row.
- Duplicate findings at the stated grain, plus fan-out if relationships exist.
- Outlier findings with the method, the count, and a few example keys.
- A short list of columns that are unsafe as metrics or as join keys, each
  with the reason.
- Gaps marked as insufficient evidence. Never fill a rate you did not compute.
  A blank cell that looks like zero is a rate you invented.

```markdown
## Dataset assessment: <object>

### Source
- Class:
- What was read:
- Rows profiled:
- Population or sample:
- Not seen:

### Grain
- Grain:
- Stated by: <who, or "assumed; duplicate findings are conditional">

### Columns
| Column | Type | Missing | Placeholder | Zero, where meaningful | Distinct | Min / max or top values | Filled means |
|--------|------|---------|-------------|------------------------|----------|-------------------------|--------------|

### Duplicates
| Claim | Result | Evidence |
|-------|--------|----------|
| Exact rows | | |
| Business key at the stated grain | | |
| Fan-out | | |

### Outliers
| Column | Method | Count | Example keys | Domain-impossible, or statistical only |
|--------|--------|-------|--------------|----------------------------------------|

### Unsafe as a metric or a join key
| Column | Unsafe as | Reason |
|--------|-----------|--------|

### Insufficient evidence
- <rate or check that was not computed, and why>
```
