---
name: power-bi-measure-translation
description: Translating an existing metric between SQL and DAX so the number stays the same, and labelling the result unchecked when it cannot be compared. Use when someone has a metric in SQL and needs the same number in DAX, or has a DAX measure and needs the SQL that reproduces it.
---

# Translating a metric between SQL and DAX

SQL and DAX can both produce a number that looks like "sales". They do not
mean the same thing until someone has said which rows were included, at what
grain, under which filters, and on which date. A translation that skips that
sentence is a new metric with the old name. The number moves, the report
still opens, and the disagreement is discovered by a reader, not by the
formula.

This skill rewrites an existing metric in either direction. It does not
invent the business question the metric answers. It stops at whether the
two expressions are the same number. It does not tune the report, and it
does not decide what the metric means when the description and the formula
already disagree.

The patterns that are long enough to get wrong on their own are in
[references/ratios.md](references/ratios.md),
[references/time.md](references/time.md),
[references/snapshots.md](references/snapshots.md), and
[references/fan-out.md](references/fan-out.md). The rules below are the ones
those pages share.

Its neighbours in this catalog:

- [nl2sql-query-validation](../NL2SQL-QUERY-VALIDATION/SKILL.md) generates
  SQL from a question and validates it before it runs. This skill starts
  from an existing metric and rewrites it. It does not invent the business
  question.
- [power-bi-performance-diagnosis](../POWER-BI-PERFORMANCE-DIAGNOSIS/SKILL.md)
  decides whether a report is slow and treats generated DAX as unverified
  until it is measured. This skill stops at equivalence of the number. It
  does not tune.
- [power-bi-datasource-migration](../POWER-BI-DATASOURCE-MIGRATION/SKILL.md)
  treats DAX as stable across a warehouse change. This skill is the case
  where the SQL and the DAX are being brought into line.
- [power-bi-report-faq](../POWER-BI-REPORT-FAQ/SKILL.md) takes a metric's
  meaning from the measure description, not from a paraphrase of the formula.
  When a description and a formula disagree, say so and do not pick a third
  definition.
- [power-bi-copilot-readiness](../POWER-BI-COPILOT-READINESS/SKILL.md) decides
  whether a model is safe to ask questions of. When Copilot has drafted DAX,
  the equivalence check belongs here.

## Refuse a guess

A formula is a guess when the grain, the filters, or the date are not known.
Write that down and stop. Filling the gap with a plausible `SUM` or a
plausible `CALCULATE` produces a number nobody can tell from the real one.

Read the source expression as it is written. If the source is DAX, read it
from the project’s TMDL, not from a paraphrase and not from a `.pbix`. If
the model text is not there, say what cannot be seen and stop. If the source
is SQL, the query text is the source, including its `GROUP BY`, its
`WHERE`, and its joins. A description of the query is not the query.

An unchecked translation is labelled unchecked. A translation you cannot run
is not a verified one. "It compiles" and "the visual shows a number" are
both short of a check.

## What the two languages do not share

**Grain.** SQL writes the result grain in `GROUP BY`. DAX has filter context
from the visual, and row context inside an iterator. A measure that matched
a grouped query is a different number on a visual that adds a column, because
the visual’s grain was never in the SQL. If the grain of a window or a
running total is the visual, the measure is not portable onto another visual.
Say so. Window functions that rank or run a total stay in the translation
only when the target is an explicit iterator or a window at a grain you can
name.

**Filters.** A `WHERE` clause is a filter on the query. It removes rows
before the aggregate. A `CALCULATE` filter replaces or adds filter context
depending on how it is written, and a visual-level filter the SQL never had
is an extra population. Name that filter, or leave it out of the measure.
Carrying it in silently makes the DAX "correct" only on the page that
happens to set it.

**The date.** A time comparison needs a date table marked as a date table,
at the grain the comparison uses. The SQL’s date column and the model’s date
table are the same claim only when you say which column binds them. Holes in
the date table change year-to-date, prior period, and same-period-last-year
results, and they will not show up in the DAX text. The detail is in
[references/time.md](references/time.md).

**Where the value is computed.** A calculated column is computed at refresh,
in row context, and then summed like any other column. A measure is computed
in the visual’s filter context. A SQL expression that depends on the query’s
filters does not survive as a calculated column: the filters are not there
at refresh. Translate that expression as a measure.

## Patterns that share those rules

**Conditional aggregation.** `SUM(CASE WHEN … THEN amount END)` keeps the
rows that fail the condition in the query and contributes zero, or null, for
them. The DAX that matches is a sum filtered to that condition, not a sum of
a column that was already reduced to the passing rows, and not an iterator
that changes the grain. Write the condition the SQL wrote.

**Distinct counts.** `COUNT` of a key after a join is not `COUNT` of the fact
rows, and neither is `DISTINCTCOUNT`. Match the SQL’s distinctness exactly:
count rows, count a key, or count distinct values of a column. The join is
why they diverge, which is
[references/fan-out.md](references/fan-out.md).

**A metric already filtered in SQL.** The filter is part of the metric. If
the DAX leaves it to the visual, the measure is a different metric the moment
the visual’s filter changes. Put the SQL’s filter in the measure, and name
any further filter as belonging to the visual, not to the translation.

**Ratios, time comparisons, and snapshots** each fail in their own way. A
sum of ratios, a date table with holes, and a snapshot that got summed are
three different wrong numbers. They are the reference pages.

## What to hand back

Every translation, in either direction, contains the same six parts.

1. The source expression, unchanged.
2. Assumptions: grain, filters, population, date column, and the
   relationships with their cardinality and filter direction. Mark each as
   stated or assumed. An assumed grain is a reason the result is unchecked,
   not a footnote.
3. The target expression.
4. Why that construct preserves the number: which grain it aggregates at,
   which filters it keeps, and which context it does not invent.
5. The cases in which it will not, for this metric. A generic list of DAX
   pitfalls is not this part. Name the visual, the join, or the date that
   would move this number.
6. The check: the same grain, the same filters, the same population,
   compared as a number. If you cannot run it, the result is unchecked, not
   done.
