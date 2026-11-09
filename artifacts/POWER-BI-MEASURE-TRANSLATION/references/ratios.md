# Ratios

Written for the translation in [`../SKILL.md`](../SKILL.md). A ratio is the
pattern most often "fixed" by averaging a column that was already a rate.

`SUM` of a ratio column is not a ratio of sums. `AVG` of a rate column is
not `SUM(numerator) / SUM(denominator)` unless the source SQL did that and
each row is one equal event. A row that is an order line and a row that is
an order are not equal events. Averaging the line rate weights a one-unit
line the same as a thousand-unit line, which is a different metric from the
one the business usually means by "margin".

Write the division the SQL wrote.

```dax
DIVIDE([Margin], [Revenue])           -- SQL: SUM(margin) / SUM(revenue)
-- not this, unless the SQL averaged a precomputed rate:
AVERAGEX(Fact, Fact[MarginPct])
```

The names are the pattern in [`../SKILL.md`](../SKILL.md). Copy the
identifiers you bound. If the SQL divides two aggregates, the DAX divides
two measures, each of which has the same grain and the same filters as its
SQL aggregate. If the SQL averages a precomputed rate, the translation
averages that rate, and the assumption "each row is one equal event" is
stated, not implied. If you cannot tell which of those the SQL did, the
ratio is a guess. Stop.

The check is both sides of the division, not only the quotient. Two errors
can cancel in the ratio and show up in the numerator. Compare numerator,
denominator, and quotient at the grain the SQL grouped by, under the
filters the SQL applied. A match at the grand total only is an unchecked
translation.
