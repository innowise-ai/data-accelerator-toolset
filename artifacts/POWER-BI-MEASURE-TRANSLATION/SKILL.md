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
[references/snapshots.md](references/snapshots.md),
[references/fan-out.md](references/fan-out.md),
[references/conditional.md](references/conditional.md), and
[references/cumulative.md](references/cumulative.md). The rules below are
the ones those pages share.

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

A formula is a guess when the grain, the filters, the date, or the bindings
are not known. Write that down and stop. Filling the gap with a plausible
`SUM` or a plausible `CALCULATE` produces a number nobody can tell from
the real one.

An unchecked translation is labelled unchecked. A translation you cannot
run is not a verified one. "It compiles" and "the visual shows a number"
are both short of a check.

## Bind the model before any target formula

A translation that names objects the model does not have is that guessed
formula. Assess the model by reading TMDL in the Power BI Project. The
project folder is the model. If `definition/` is absent, the tables, the
measures, the relationships, and the date-table mark cannot be seen. Say
what cannot be seen and stop. A project saved as TMSL keeps the same model
in a single `model.bim`; read it as JSON in place (measures under
`model.tables[].measures` with their `expression`, relationships under
`model.relationships`), and do not convert it. If the only input is a
`.pbix`, stop. A package is not
the measures.

SQL to DAX, in this order, because each step is a claim the next one
depends on:

1. **The source SQL.** A pasted query, a `.sql` file, or a native SQL
   string inside a partition M. A description of the query is not the
   query: it does not name the `GROUP BY`, the `WHERE`, or the joins, and
   those are the grain and the filters.
2. **The semantic-model `definition/` folder**, as TMDL.
3. **An inventory from those files**, only what this translation needs —
   not a second copy of the audit. Tables and columns live in
   `definition/tables/*.tmdl`. Read every `.tmdl` under `definition/`
   before concluding something is absent; a model can split objects
   across files. Existing measures are the expression after `=`. If one
   of them already is this metric, reuse it. A second measure with the
   same name and a different body is a different number. Relationships —
   cardinality, filter direction, active or inactive — are in
   `definition/relationships.tmdl`. The date-table mark is
   `dataCategory: Time` on the table, and a calendar object on newer
   projects. A table named Date is not the mark. Time intelligence on an
   unmarked table is a different calendar from the one the SQL used.
4. **Bind** each SQL table, column, and date to a TMDL object. Mark each
   binding stated or assumed. Copy identifiers as they are written in the
   TMDL and in the SQL. Tidying a name is inventing a name.
5. **Only then write DAX**, using only bound names.
6. **Stop** if a SQL column has no counterpart, if a join has no
   relationship you can state, or if the grain, the filters, or the date
   are unknown. Do not invent names.

DAX to SQL uses the same bindings in the other direction. The DAX source
is the expression after `=` in `definition/tables/*.tmdl`, not a
paraphrase. Warehouse object names come from the partition M and from
native SQL, and they can differ from the TMDL names. Bind those too, or
the SQL you write will query objects the warehouse does not have.

| Fact | File |
|---|---|
| Measure expression | after `=` in `definition/tables/*.tmdl` |
| Cardinality and filter direction | `definition/relationships.tmdl` |
| Valid SQL source | pasted query, `.sql` file, or native SQL in partition M |
| Same facts in TMSL | `model.bim`: `model.tables[].measures`, `model.relationships` |
| Not a source | query description, screenshot, `.pbix` |

## What the two languages do not share

**Grain.** SQL writes the result grain in `GROUP BY`. DAX has filter context
from the visual, and row context inside an iterator. A measure that matched
a grouped query is a different number on a visual that adds a column, because
the visual’s grain was never in the SQL. If the grain of a window or a
running total is the visual, the measure is not portable onto another visual.
Say so. Unbounded and partitioned running totals are
[references/cumulative.md](references/cumulative.md), not year-to-date.
Window functions that rank or run a total stay in the translation only when
the target is an explicit iterator or a window at a grain you can name.

**Filters.** A `WHERE` clause is a filter on the query. It removes rows
before the aggregate. The SQL’s filter belongs inside the measure; a visual
slicer is a second filter. `CALCULATE` replaces filter context on the
columns it names, so a page that already slices those columns can lose that
slice while the grand total still matches.

The names `Fact[Amount]`, `Fact[Status]`, and `'Date'[Date]` below are the
pattern only. A real translation copies identifiers from the TMDL and from
the SQL, character-for-character. Never emit `Fact[Amount]` unless those
are the names you bound from the model.

```dax
-- replaces any Status filter the visual already has
CALCULATE(SUM(Fact[Amount]), Fact[Status] = "Shipped")
-- keeps SQL's filter AND the page
CALCULATE(SUM(Fact[Amount]), KEEPFILTERS(Fact[Status] = "Shipped"))
```

The first form can match the SQL at the total while the page’s Status
slicer is silently dropped. Name the visual’s filter, or keep it with
`KEEPFILTERS`. Carrying a page filter in silently, or dropping it
silently, makes the DAX "correct" only on the page that happens to set it.

**The date.** A time comparison needs a date table marked as a date table,
at the grain the comparison uses. The mark is `dataCategory: Time` on the
table, and a calendar object when present. A table named Date is not that
mark. The SQL’s date column and the model’s date table are the same claim
only when you say which column binds them. Holes in the date table change
year-to-date, prior period, and same-period-last-year results, and they
will not show up in the DAX text. The detail is in
[references/time.md](references/time.md).

**Where the value is computed.** A calculated column is computed at refresh,
in row context, and then summed like any other column. A measure is computed
in the visual’s filter context. A SQL expression that depends on the query’s
filters does not survive as a calculated column: the filters are not there
at refresh. Translate that expression as a measure.

## Patterns that share those rules

**Conditional aggregation.** `SUM(CASE WHEN cond THEN amount END)` with no
`ELSE` contributes null for the rows that fail the condition. `SUM` skips
those nulls. `ELSE 0` contributes zero and keeps the rows in the grain.
Null and zero are not one thing: totals often match while matrix subtotals
do not, because the zeros still occupy the grain. The DAX that matches is
a sum filtered to that condition, not a `SUMX` that changes the grain, and
not a calculated column of the `CASE`, which is computed at refresh with
no query filter. The pairs are in
[references/conditional.md](references/conditional.md). Write the
condition the SQL wrote.

**Distinct counts.** `COUNT` of a key after a join is not `COUNT` of the fact
rows, and neither is `DISTINCTCOUNT`. Match the SQL’s distinctness exactly:
count rows, count a key, or count distinct values of a column. The join is
why they diverge, which is
[references/fan-out.md](references/fan-out.md).

**A metric already filtered in SQL.** The filter is part of the metric. If
the DAX leaves it to the visual, the measure is a different metric the moment
the visual’s filter changes. Put the SQL’s filter in the measure, and name
any further filter as belonging to the visual, not to the translation.

**Ratios, time comparisons, snapshots, and running totals** each fail in
their own way. A sum of ratios, a date table with holes, a snapshot that
got summed, and a plain `SUM` with no date window are four different wrong
numbers. They are the reference pages.

## What to hand back

Every translation, in either direction, contains the same six parts.

1. The source expression, unchanged.
2. Assumptions: grain, filters, population, date column, and the
   relationships with their cardinality and filter direction. Include the
   bindings — model table, model column, relationship, date column — and
   mark each as stated or assumed. An assumed grain or an assumed binding
   is a reason the result is unchecked, not a footnote.
3. The target expression, using only bound names.
4. Why that construct preserves the number: which grain it aggregates at,
   which filters it keeps, and which context it does not invent.
5. The cases in which it will not, for this metric. A generic list of DAX
   pitfalls is not this part. Name the visual, the join, or the date that
   would move this number.
6. The check: the same grain, the same filters, the same population,
   compared as a number. If you cannot run it, the result is unchecked, not
   done. A match at the grand total only is unchecked.

## Anti-patterns

- Inventing `SUM` or `CALCULATE` when the grain, the filters, the date, or
  the bindings are unknown. A guessed formula produces a number nobody can
  tell from the real one.
- Copying teaching-pair names (`Fact[Amount]`) into a real handback. Those
  names are the pattern only; a translation that does not copy the bound
  TMDL and SQL identifiers is inventing objects.
- Reading a paraphrase, a screenshot, or a `.pbix` as the source. None of
  those is the query or the measure text. `model.bim` is the measure text in
  TMSL; read it, but converting it is not this task.
- `AVERAGEX` of a rate when the SQL divided two aggregates. Averaging a
  precomputed rate weights every row as one equal event, which is a
  different metric from a ratio of sums.
- Time intelligence on a table named Date that is not marked
  `dataCategory: Time`. The name is not the mark, and the calendar the
  SQL used is then a different set of days.
- `SAMEPERIODLASTYEAR` on order date when the SQL used ship date. Both
  answer "last month"; they are different numbers.
- Summing a snapshot table. The SQL kept one row at the grain it named;
  adding Monday’s balance to Tuesday’s is a different metric.
- `ALL` on the date table when the SQL’s window respected the slicer. The
  page’s date filter disappears, which is `ALL` rather than `ALLSELECTED`.
- Treating "it compiles" or "the visual shows a number" as a check. Both
  are short of comparing the same grain, filters, and population.
- A match at the grand total only. Two errors cancel there and show up in
  the slices.
- `CALCULATE` without `KEEPFILTERS` when the visual also filters the same
  column. Totals can match while the page’s slicer is silently dropped.
