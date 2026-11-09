# What does not survive a connection swap

Written for the migration in [`../SKILL.md`](../SKILL.md). These are the
parts of a model that depend on the warehouse. DAX does not, which is why a
review that starts by rewriting measures is looking in the wrong place.

Read the model from the project folder. Connections are in
`definition/dataSources.tmdl`. That file is often empty: the connection is
frequently only in the partition M. An empty `dataSources.tmdl` is not "no
sources". Power Query is the partition `source` and
`definition/expressions.tmdl`. A native query is an M expression that embeds
a SQL string. Types are on the columns. Which measures and functions depend
on a column is the call graph from the audit's inventory. If the only input
is a `.pbix`, say what cannot be seen and stop. If the model is only
`model.bim`, stop; do not convert it.

## Folding

A step folds when the connector turns it into SQL and the warehouse does the
work. The two connectors do not fold the same set of M functions, and a step
that folded against the old warehouse may be evaluated locally against the
new one. Local evaluation can change the result, not only the time: a date
boundary, a rounding, or a null comparison then happens in M rather than in
the warehouse, and the two do not agree.

The evidence is a captured native SQL string: the SQL the connector sends,
captured on the old connection and again on the new one, for the steps the
report relies on. That string is not a project file. If you cannot see it,
folding is unverified. Do not infer it from the M looking simple.

A native SQL string does not fold further. Steps after it run locally. The
string itself is dialect. Identifiers, date functions, and quoting that were
legal on the old warehouse are the lines to read, not the DAX.

## Types

A column that rebinds by name arrives with the new warehouse's type. The
failures that move numbers without breaking the report:

- A timestamp that changes zone or loses its zone, so a date boundary shifts
  by hours and a daily total moves.
- A decimal whose scale changed, so a sum that looked exact is now rounded,
  or the reverse.
- A blank that was an empty string and is now null, or the reverse, on a
  column a filter treats as "missing". The filter still runs. The set it
  keeps is different.

Check these on the columns the report filters and aggregates. A type change
on a column nothing uses is inventory, not a finding.

## Date tables

DAX time intelligence needs a date table that is complete at the grain the
measures assume, marked as the date table, and related to the facts. The
mark is `dataCategory: Time` on the table, and a calendar object when
present. A table named Date is not that mark. A date table generated in
the model travels with the model and is not the swap's problem. A date table loaded from the warehouse does not travel. If the new
table has gaps, a different week start, or a different set of fiscal
periods, every time-intelligence measure moves and none of their formulas
changed.

Compare the old and new date tables as tables: row count, minimum, maximum,
and the gaps. Do not compare them by reading the DAX.

## What not to take from this list

This is not a design for the new warehouse. A column that should be renamed,
a grain that should change, and SQL that should move into a transformation
tool are
[dbt-legacy-sql-migration](../../DBT-LEGACY-SQL-MIGRATION/SKILL.md). Doing
that work inside the swap removes the baseline you needed to prove the
report. Sequence them. Do not merge them.
