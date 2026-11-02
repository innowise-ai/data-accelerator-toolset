# Implementing a settled definition in Tableau

An adapter for [`../SKILL.md`](../SKILL.md). The definition is the product; this is
what it takes to express one in a Tableau workbook without losing a clause, and
the check that proves nothing was lost.

Nothing here changes the definition. If implementing it raises a question the
definition cannot answer, that is a gap in the specification and it goes back to
the specification.

    10|## A ratio is a ratio of totals

The most common way a correct definition becomes a wrong number. A rate defined as
"on-time deliveries divided by deliveries" has to be computed as the quotient of
two aggregates:

```
SUM([On Time Deliveries]) / SUM([Deliveries])
```

Writing the division at row level and then aggregating it — an average of
per-row or per-day ratios — gives a different answer, weighted by nothing in
    20|particular. It matches the correct value when every denominator is equal and
diverges the rest of the time, which is why it survives a spot check.

This is the same point as the re-aggregation question in the definition, and it
is where that question pays for itself: a definition that says "this rate rolls
up as total over total, and cannot be averaged across periods" leaves no room for
the wrong implementation.

## Put the exclusions where they travel

A definition's exclusions are part of the metric, not part of a view. Implement
    30|them so they cannot be left behind:

- Inside the calculation, so the field carries its own population — the condition
  goes inside the aggregate rather than on a filter shelf.
- Or on the data source, where every sheet inherits them.

What not to do is implement an exclusion as a worksheet filter. It is invisible
from the field, nothing carries it to the next sheet, and the second sheet someone
builds with that field reports a different metric under the same name.

Set the field's default aggregation too. Without it, a field that is only
    40|meaningful as a ratio gets summed by whoever drags it onto a shelf next.

## The order of operations is the real trap

Tableau applies filters and level-of-detail expressions in a fixed order, and a
fixed-grain expression is evaluated before dimension filters are applied. The
consequence is specific and catches almost everyone once:

**A metric computed at a fixed grain ignores the dashboard's filters.** Define
"revenue per customer" as a fixed expression per customer and it returns the
customer's all-time figure, unchanged when the user selects last month. The view
    50|renders, the number is wrong, and it is wrong in a plausible direction.

The fixes are to use a grain-relative expression that respects the dimension
filters, or to promote the filter into context so it applies before the fixed
expression. Which one is right depends on the definition — specifically, on
whether the metric's population is "within the selected period" or "all time,
shown for the selected period", which is the kind of clause a definition has to
settle explicitly.

Note also that a filter becoming a context filter changes results for every fixed
expression in the workbook, not only the one being fixed.

    60|## Nulls and zero denominators

Two defaults to make deliberate, because Tableau's behaviour is reasonable and is
not always what the definition says:

- **Aggregates skip nulls.** A sum ignores them, an average divides by the
  non-null count. If the definition says nulls count as zero, that has to be
  written into the calculation; it does not happen by itself, and the totals match
  either way while the averages do not.
- **Division by zero yields null, and a null mark is simply absent.** So
  "undefined and suppressed" is what you get for free. If the definition says the
    70|  metric is zero when the denominator is zero, write it.

## The check that has to agree

Write a query against the warehouse directly from the definition text, and compare
it with what the view shows.

**Write it from the definition, not from the Tableau calculation.** A query
transcribed from the calculation reproduces whatever was misunderstood, agrees
perfectly, and proves nothing. The whole value is that the two paths are
independent.

    80|```sql
-- from the definition text: population, date column, grain, exclusions
select date_trunc('month', <the date the definition names>) as period,
       sum(<numerator expression>) / nullif(sum(<denominator expression>), 0) as metric,
       count(*)                                             as rows_considered
from <the table the definition names>
where <the exclusions the definition lists>
group by 1
order by 1;
```

    90|Compare at more than one level. Equal monthly totals are weak evidence: two
offsetting errors cancel in an aggregate and separate when the figure is broken
down by the dimension the dashboard filters on. Check the row count beside the
value, because a metric can be right while the population is wrong.

Match the filter and parameter state when comparing. A view at its defaults is not
the same query as the one the SQL expresses unless the defaults are part of the
comparison.

Keep the query next to the definition once it agrees. It is the regression test
for the metric, and it is the fastest answer available the next time two reports
   100|disagree.

## Treat any calculation you did not verify as unverified

Tableau's calculation language is a narrow one, and both level-of-detail
expressions and table calculations mean different things depending on the sheet's
grain, its filters and its sort — none of which is visible in the formula. A
confident-looking expression is wrong here more often than the apparent difficulty
suggests, and the simplicity of the request is not protection.

So no calculation counts as correct because it reads correctly. It counts as
   110|correct when its numbers match the independent query, on more than one slice.
Iterating on a formula until it looks right is not verification, and after a few
rounds of that, working the logic out by hand is usually both faster and more
trustworthy than another attempt.
