# Fan-out

Written for the translation in [`../SKILL.md`](../SKILL.md). A join that
multiplied rows is already baked into a SQL `SUM`. The model does not keep
that join as a `JOIN`. It keeps it as a relationship, and the measure
aggregates a column in filter context.

A relationship filters the fact table; it does not duplicate fact rows. So
re-aggregating the fact column returns the sum at the fact grain, which is
not the SQL number if the join inflated it. Decide with the author whether
that inflation was a bug or the metric they meant. If it was a bug, the DAX
is the corrected number and the difference is reported, not hidden. If it
was intended, the DAX has to reproduce the multiplication explicitly, for
example by iterating the joined rows. Either way, state the cardinality and
the filter direction of the relationship that replaces the join. A many-to-many, or a relationship
that filters both ways, is not the join the SQL wrote, and the number can
move without the measure text changing.

Aggregating a column that already contains the joined total counts the
fan-out twice. The SQL summed an amount after the join had duplicated the
fact rows, so the amount is already repeated. Summing that amount again in
DAX, or summing a column on the many side that was itself a total brought
down from the one side, counts the repetition as if it were new facts. State
the grain you aggregated at: the fact grain, or the grain after the join. If
you cannot tell which column still holds one row per fact, stop. Guessing
which side is "the amount" is how the fan-out gets counted twice.

`COUNT` after that join, `COUNT` of the fact rows, and `DISTINCTCOUNT` of a
key are three results. Match the SQL’s distinctness exactly, at the grain
the `GROUP BY` named:

```dax
COUNTROWS(Fact)              -- SQL COUNT(*) of fact rows
COUNT(Fact[OrderId])         -- SQL COUNT(col): non-blank
DISTINCTCOUNTNOBLANK(Fact[OrderId]) -- SQL COUNT(DISTINCT col)
```

`DISTINCTCOUNT` counts BLANK as one value; SQL `COUNT(DISTINCT col)` ignores
NULL. On a column that has blanks, only `DISTINCTCOUNTNOBLANK` matches.

The names are the pattern in [`../SKILL.md`](../SKILL.md). Copy the
identifiers you bound. If you cannot tell which column still holds one
row per fact, stop. The check includes the row count at that grain, not
only the aggregate. A sum can match while the row count shows the fan-out
is still in one side.
