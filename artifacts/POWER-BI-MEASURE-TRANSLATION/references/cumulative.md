# Running totals

Written for the translation in [`../SKILL.md`](../SKILL.md). A running
total accumulates along a date order. It is not year-to-date, which stays
in [time.md](time.md). It is not a snapshot last-balance, which stays in
[snapshots.md](snapshots.md).

Two SQL shapes. Copy the one the query wrote.

Never resets:

```sql
SUM(Amount) OVER (ORDER BY OrderDate ROWS UNBOUNDED PRECEDING)
```

Resets on a partition — customer, year, or whichever column the SQL named:

```sql
SUM(Amount) OVER (
  PARTITION BY CustomerId
  ORDER BY OrderDate
  ROWS UNBOUNDED PRECEDING
)
```

The DAX that keeps the number is `CALCULATE` of the bound amount measure,
with the marked date table filtered to dates `<= MAX` of the bound date
column. The mark is `dataCategory: Time` on that table (and a calendar
object when present), not the name Date. For a partition, keep that
column in the filter context; do not `ALL` it away, or the reset the SQL
wrote disappears.

```dax
CALCULATE(
    [Amount],
    FILTER(
        ALLSELECTED('Date'[Date]),
        'Date'[Date] <= MAX('Date'[Date])
    )
)
```

The names in that pair are the pattern in [`../SKILL.md`](../SKILL.md).
Copy the identifiers you bound.

Unsafe, and the claim that makes each a different number:

| Form | Why it is not the SQL |
|---|---|
| Plain `SUM` with no date window | This grain only, not cumulative |
| `ALL('Date')` when the SQL’s window respected a slicer | `ALL` rather than `ALLSELECTED`; the page’s date filter disappears |
| Window on the fact date column instead of the marked date table | Holes in the fact dates, and an inactive relationship, change which days accumulate |
| Grain of the window = whatever the visual is | A card and a matrix are different running totals. Say so |

Check the running value and the row count at each step of the grain, not
only the last point. A match at the end of the series can hide a wrong
reset in the middle.

Do not add a running distinct count, or a percentage of a running total,
on the way through. Those are different metrics from the window the SQL
wrote.
