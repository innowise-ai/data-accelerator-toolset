# Time comparisons

Written for the translation in [`../SKILL.md`](../SKILL.md). Year to date,
prior period, and same period last year all move when the date is the wrong
date, even if the DAX text is the usual one.

The SQL names a date column. The model has a date table, and that table is
the date table only once it is marked as one and related to the fact at the
grain the comparison uses. Those two dates are the same claim only when you
say which column binds them. Order date and ship date both answer "last
month". They are different numbers. If the SQL filters one and the
relationship is on the other, the translation has changed the metric. Say
which binding you used, and mark it stated or assumed.

Holes in the date table change time intelligence and do not appear in the
DAX. A missing day, a week that starts on a different weekday, or a year
that skips a date makes "year to date" and "prior period" land on a
different set of days from the SQL, which used the calendar the warehouse
query actually saw. Compare the date table to the SQL’s date spine: row
count, minimum, maximum, and the gaps. Do not compare them by reading the
DAX.

A visual date slicer the SQL did not have is an extra filter. Name it, or
the check is not at the same filters. The comparison itself belongs in the
measure. Leaving "prior year" to a slicer the reader happens to set is a
different metric.
