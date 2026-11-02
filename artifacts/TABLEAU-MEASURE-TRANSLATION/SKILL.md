---
name: tableau-measure-translation
description: Translating an existing metric between SQL and a Tableau level-of-detail expression so the number stays the same, and labelling the result unchecked when it cannot be compared. Use when someone has a metric in SQL and needs the same number as a Tableau level-of-detail calculation, or has a FIXED, INCLUDE, or EXCLUDE expression and needs the SQL that reproduces it.
---

# Translating a metric between SQL and a level-of-detail expression

A query and a calculation can both return something called "revenue per
customer". They are the same metric only once someone has said which rows were
included, at what grain, under which filters, and on which date.

Tableau adds a sentence SQL never needs: the grain of the sheet the expression
will sit on. A level-of-detail expression does not carry a complete meaning by
itself. The view supplies the other half, and the same formula on two sheets is
two numbers. So a translation that hands back only an expression has not
finished — it has moved the undefined part somewhere the next person will not
look for it.

This skill rewrites an existing metric in either direction. It does not invent
the business question the metric answers, and it stops at whether the two
expressions are the same number. It does not tune the workbook.

The three keywords and what each does to the result are in
[references/lod-expressions.md](references/lod-expressions.md). Where a filter
sits, and why that decides whether it survives the translation, is in
[references/filter-order.md](references/filter-order.md).

Its neighbours in this catalog:

- [nl2sql-query-validation](../NL2SQL-QUERY-VALIDATION/SKILL.md) generates SQL
  from a question and validates it before it runs. This skill starts from an
  existing metric and rewrites it, so there is no question to interpret.
- [kpi-definition-building](../KPI-DEFINITION-BUILDING/SKILL.md) decides what
  the metric is — population, grain, which date, how it rolls up. Go there when
  the two expressions disagree because nobody ever settled the rule; a
  translation cannot close a gap in the definition, it can only report it.
- [tableau-analytical-calcs](../TABLEAU-ANALYTICAL-CALCS/SKILL.md) builds a
  known shape — cohort retention, a funnel, year on year, a rank — from the
  metric's definition, and chooses between the three places a calculation can
  run. This skill has both expressions already and only has to preserve the
  number between them.
- [tableau-pulse-readiness](../TABLEAU-PULSE-READINESS/SKILL.md) checks that a
  Pulse metric's insight matches the intended number. When the data source's
  calculation is why it does not, the rewrite belongs here.
- `power-bi-measure-translation` is the DAX counterpart. Its rules are not
  transferable: filter context and a Tableau order of operations are different
  mechanisms, and a translation that borrows the other product's constructs
  computes a different number with the same confidence.

## A level-of-detail expression is not a table calculation

This is the first thing to settle, because the two are easy to confuse from a
SQL window function and the mistake is unrecoverable later.

A level-of-detail expression aggregates at a grain you name. It is part of the
query. A table calculation works on the rows the query already returned — a
previous row, a running total, a rank, a share of the total — and runs after the
result comes back. `RANK`, `ROW_NUMBER`, `LAG`, `LEAD` and a running
`SUM(...) OVER (...)` are table calculations, not grains.

So when the SQL window is doing one of those, say so and stop. There is no
`FIXED` that reproduces a rank, and the expression that looks as if it does is
aggregating at a grain the ranking never had. If the user wants the request
rewritten as a level-of-detail grain instead, that is a new metric and it has to
be agreed as one.

## Two grains, named every time

Every translation states both: the grain of the view the expression will sit on,
and the grain the expression itself computes at. Almost everything below is a
consequence of the pair.

`FIXED` ignores the view's dimensions entirely and computes at the dimensions it
names. The view then aggregates that result again. **That second aggregation is
the part a translation forgets.** A `FIXED` sum per customer, placed on a sheet
broken down by month, returns the customer's whole figure on every month and
sums to several times the real total. Switch the roll-up to an average and
nothing looks broken — the number is simply a different metric, the mean of
per-customer totals rather than anything the SQL computed.

`INCLUDE` and `EXCLUDE` are relative. `INCLUDE` adds dimensions to the view's
grain; `EXCLUDE` takes them away. Neither means anything until the view is
known, so when the view was not stated, the missing view is the answer to give
back. An expression chosen by guessing the sheet is not a translation, and a
`FIXED` that happens to look similar is the most common way that guess gets
written down.

## What else changes the number

**Filter position.** A filter that survives in SQL can disappear in Tableau, or
the reverse, purely because of where it sits. Extract and data source filters
apply before a `FIXED` expression; so does a context filter. An ordinary
dimension filter applies *after* it and does not reduce it. `INCLUDE` and
`EXCLUDE` do see the dimension filters. A `WHERE` clause is not automatically a
context filter, and promoting one to context changes every `FIXED` expression in
the workbook, not just this metric's. Name each filter's position or the
translation is incomplete. The order is in
[references/filter-order.md](references/filter-order.md).

**Relationships, joins and blends are three different grains.** A relationship
aggregates each table at its own grain and then combines, so the fact table is
not multiplied. A physical join can multiply rows before anything is aggregated,
which is where a sum that matched the query quietly doubles. A blend is neither:
it aggregates the secondary source and matches on the linking fields only, so it
cannot express a row-level condition across sources at all. Translate against
the one the data source actually uses and name it. If the data source cannot be
read, the grain is unknown, and an expression written on an unknown grain is
unchecked rather than wrong.

**Aggregates that do not compose.** A sum of ratios is not a ratio of sums, and
the two agree whenever the denominators are equal, which is what gets the wrong
one through review. A distinct count has to match the SQL's distinctness exactly
— rows, a key, or distinct values of a column — and after a join those are three
numbers. A field that is already aggregated in the extract is not a row-level
column; aggregating it again produces a metric with no definition.

**The date grain.** A time comparison needs the grain the SQL used. A `FIXED`
expression at month, joined back to daily rows, repeats the month's value on
every day of it — correct as a month-to-date denominator, wrong as a daily
series, and identical in the formula either way. Say whether the view is meant
to show the month's value or the day's.

## Direction: SQL to a level-of-detail expression

Compare the grain the SQL grouped at with the grain of the view. When they are
the same, no level-of-detail expression is needed and a plain aggregate is the
translation. When the metric's grain is coarser or finer than the view's, that
difference chooses the keyword.

Prefer the coarsest expression that preserves the number. `FIXED` on every
dimension in the view is the view's own grain written the long way: it adds a
grain that now has to be kept in step with the sheet, and it stops responding to
the dimension filters that the view still honours.

## Direction: a level-of-detail expression to SQL

`FIXED` becomes a subquery grouped by the fixed dimensions and joined back to
the detail on those dimensions. `INCLUDE` becomes a grouping by the view's
dimensions plus the included ones. `EXCLUDE` becomes a grouping by the view's
dimensions minus the excluded ones.

The join keys are part of the translation, not plumbing. A missing key is a
fan-out: the subquery's value lands on more rows than it should, and the sum
does not match while every individual row looks reasonable. Write the keys down
beside the query so the next reader can check them. The skeletons are in
[references/lod-expressions.md](references/lod-expressions.md).

## What to hand back

Every translation, in either direction, contains the same six parts.

1. The source expression, unchanged.
2. Assumptions: the view's grain, the expression's grain, each filter and its
   position, whether the data source uses relationships, physical joins or a
   blend, the population, and the date grain. Mark each one stated or assumed.
   An assumed grain is the reason a result is unchecked, not a footnote.
3. The target expression.
4. Why that construct preserves the number — including what happens when the
   view aggregates the result a second time, which is the part a reader cannot
   work out from the formula.
5. The cases where it will not, for this metric. Not a general list of
   level-of-detail pitfalls: the sheet, the join, or the filter that would move
   this number.
6. The check, run at the same grain, with the same filters, over the same
   population. Unrun means unchecked, and an unchecked translation is labelled
   as one rather than handed over as finished.
