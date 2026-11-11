# Conditional aggregation

Written for the translation in [`../SKILL.md`](../SKILL.md). A `CASE`
inside a `SUM` is a filter on which rows contribute an amount. It is not
a change of grain, and it is not a column computed at refresh.

## The filter, not the grain

```sql
SUM(CASE WHEN Status = 'Shipped' THEN Amount END)
```

```dax
CALCULATE(SUM(Fact[Amount]), Fact[Status] = "Shipped")
```

The claim that makes them the same number is that both keep the original
grain and drop the failing rows from the sum. `SUMX` over a table that
is not the fact grain changes which rows exist, so it is a different
metric even when the condition looks identical. A calculated column of
the `CASE` is computed at refresh, in row context, with none of the
query’s filters. Translate the SQL as a measure.

The names in that pair are the pattern in [`../SKILL.md`](../SKILL.md).
Copy the identifiers you bound from the TMDL and from the SQL.

## Blank versus zero

```sql
SUM(CASE WHEN Status = 'Shipped' THEN Amount END)        -- null; those rows are absent once DAX filters
SUM(CASE WHEN Status = 'Shipped' THEN Amount ELSE 0 END) -- zeros stay
```

`CASE` without `ELSE` yields null for the rows that fail. `SUM` skips
nulls, and once DAX has filtered to the passing rows those failing rows
are absent. `ELSE 0` yields zero, and the zeros stay in the grain. The
total can still match, because zero does not change a sum. Matrix
subtotals often do not: the zeros occupy groups the filtered measure
never creates. The check is at the visual grain, not only the grand
total.

Write the `ELSE` the SQL wrote, or the absence of one. Treating null and
zero as the same contribution is how a card matches and a matrix does
not.
