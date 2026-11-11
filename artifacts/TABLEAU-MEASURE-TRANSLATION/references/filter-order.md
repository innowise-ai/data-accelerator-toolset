# Where a filter sits, and whether it survives the translation

A reference for [`../SKILL.md`](../SKILL.md). A `WHERE` clause is one thing; a
Tableau filter is one of several things depending on where it was created, and
the position decides which expressions can see it.

## The order

Tableau applies these in a fixed sequence. Everything above a level-of-detail
expression reduces what it sees; everything below it does not.

| Order | Stage | Seen by `FIXED`? | Seen by `INCLUDE` / `EXCLUDE`? |
|---|---|---|---|
| 1 | Extract filters | yes | yes |
| 2 | Data source filters | yes | yes |
| 3 | Context filters | yes | yes |
| 4 | **`FIXED` expressions**, and at the same stage sets, conditional filters and Top N filters | — | — |
| 5 | Dimension filters | no | yes |
| 6 | **`INCLUDE` and `EXCLUDE` expressions** | — | — |
| 7 | Measure filters | no | no |
| 8 | Table calculation filters | no | no |

The gap between rows 4 and 5 is the one that produces wrong numbers in practice.
A dimension filter is the ordinary kind — the thing a user gets when they drag a
field onto the filter shelf, and the thing a dashboard's quick filters are — so
the default position for a filter is *after* `FIXED` and invisible to it.

The same gap catches Top N. A Top N or conditional filter is evaluated before the
ordinary dimension filters, so "top ten customers" with a region filter beside it
ranks across every region and then hides the ones outside the selection, often
leaving fewer than ten. A `WHERE region = …` followed by `LIMIT 10` is only
reproduced once the region filter is promoted to context.

## Translating in from SQL

A `WHERE` clause reduces the rows before anything is aggregated. That is rows 1
to 3 above, not row 5. So a metric whose SQL filters on region and then
aggregates per customer is not reproduced by a `FIXED` per customer with a
region filter on the shelf: the expression computes each customer's figure
across every region and the filter then hides rows of the result.

Which of the first three positions is right depends on what the filter is for:

- An **extract filter** changes what the extract contains. Everything downstream
  sees a smaller data set and nothing can recover the excluded rows. It matches
  a `WHERE` that is true of the metric permanently.
- A **data source filter** applies to every sheet using that source. It matches
  a `WHERE` that belongs to the metric rather than to one view, which is most
  population exclusions: test accounts, internal orders, cancelled records.
- A **context filter** is a view-level filter promoted to run early. It matches a
  `WHERE` the user is meant to control while the level-of-detail expression still
  respects it.

Context is the one to be careful with. Promoting a filter to context changes the
result of **every** `FIXED` expression in that workbook, not only the metric
being translated. A translation that recommends it has to say what else is on the
sheet, or it is trading a known wrong number for an unknown one.

## Translating out to SQL

Read the position first, then write the clause that matches it:

- Extract, data source and context filters become the `where` of the inner query,
  the one that feeds the aggregate.
- Dimension filters become a `where` on the *outer* query, after the subquery has
  been joined back — which is what makes them invisible to the `FIXED` grain.
- Measure filters are conditions on an aggregate, so they become `having`, or a
  predicate applied to the result of the grouped query. A measure filter cannot
  be moved into the inner `where` without changing the metric.
- Table calculation filters are applied last, to a result that has already been
  computed. They correspond to filtering the final result set and they do not
  remove rows from any aggregate above them.

## Two things that are not filters

**Hiding is not filtering.** A hidden member is removed from the display while
its rows stay in the result, so totals, running totals and anything computed
across the result still include it. In SQL terms there is no clause for it at
all. When a translation has to account for a member that is "not in the view",
establishing whether it was filtered or hidden comes before writing anything,
because only one of the two has an equivalent.

**A parameter is not a filter.** It is a single value, and it does nothing until
a calculation or a filter reads it. Two sheets can read the same parameter in
different places and get different populations from the same selection. For a
translation, the parameter's current value is part of the stated assumptions —
the SQL has a literal where the workbook has a control, and the comparison is
only valid at the value that was used.
