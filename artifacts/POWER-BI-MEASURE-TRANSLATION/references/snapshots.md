# Snapshots

Written for the translation in [`../SKILL.md`](../SKILL.md). A balance, a
stock level, and a headcount at month end are semi-additive. The number for
a period is the last snapshot in that period, or the one the SQL kept, not
the sum of the rows.

If the SQL uses a window or a row-number filter to keep one snapshot per
grain, the DAX has to keep one snapshot at that same grain. Summing the
snapshot table adds Monday’s balance to Tuesday’s. The total is larger, it
is still a currency or a count, and it is a different metric. Averaging the
daily snapshots is a third metric. Write the one the SQL wrote.

The grain of "one snapshot" has to be stated. Last balance per account is
not last balance of the whole book, and a visual that adds a column the SQL
did not group by will pick a different last row. If that grain is the
visual, the measure is not portable onto another visual. Say so in the
cases where this translation will not hold.

The check compares the snapshot the SQL kept with the snapshot the DAX
keeps, at the same grain and the same period end. A sum of both sides can
match by accident when each side kept one row. Count the rows you kept as
well as the value.
