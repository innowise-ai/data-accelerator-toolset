# Differences between warehouses that reach the workbook

Supporting detail for [`../SKILL.md`](../SKILL.md). These are the places where two
warehouses holding the same data produce a different dashboard.

This is deliberately not a vendor comparison matrix. Those go stale, they vary by
engine version and by connector, and a wrong cell in one is worse than no table at
all, because it is quoted. What follows is the set of behaviours that differ
between engines, each written as something to establish against the actual target
before the swap — usually with one query.

## Identifiers

Engines disagree about what an unquoted name means. Some fold it to upper case,
some to lower case, some preserve it and compare case-insensitively. Snowflake
folds to upper; the Postgres family folds to lower.

This matters more than it sounds, because Tableau rebinds fields by matching
names. If the same logical column arrives upper-cased where it used to be
lower-cased, the match fails across the board, and what looks like a catastrophic
migration is a casing rule.

Establish it first: list the columns of two or three target tables as the engine
reports them, and compare against the names in the workbook's field inventory.

## Values, not just names

Three value-level behaviours that change filters, aliases and groups without
changing a single number's type:

- **String comparison.** Some engines compare case-sensitively by default and some
  do not, which decides whether a filter on `Active` also matches `active`.
- **Padding and trimming.** Fixed-length character types pad; comparison
  semantics for the padding differ. A value with trailing spaces is a different
  value to an alias definition.
- **Empty string against null.** At least one major engine treats the empty string
  as null. Every conditional and every null check over that field behaves
  differently depending on which side of that line the new warehouse sits.

All three produce the same symptom: friendly labels disappearing and values
dropping out of groups, which reads as a formatting problem and is a data
comparison problem.

## Types

| What changed | What it does in the workbook |
|---|---|
| Fixed decimal becomes floating point | Small differences that survive review and fail reconciliation |
| Integer division semantics | A ratio that was truncated is now fractional, or the reverse |
| No native boolean, exposed as 0/1 or Y/N | The field arrives as a number or a string, so it stops behaving as a boolean and conditionals over it change |
| Naive timestamp becomes zone-aware | Every date-bounded total shifts at the boundary, which is where daily and monthly figures are read |
| Zone-aware timestamp rendered per session | The same query returns different day boundaries depending on the session's time zone, so two people can read two different numbers |
| Wider or narrower integer types | Rarely a problem, occasionally an overflow in a calculation that aggregates before dividing |

The timestamp rows are the ones to spend time on. A time zone change is invisible
in the schema, invisible in the workbook, and visible only as a total that is
slightly wrong at the start and end of every period.

## Dates and calendars

Date truncation, week boundaries, ISO against non-ISO week numbering, and quarter
and fiscal-year definitions all vary. Two of them are not even warehouse
properties: the fiscal year start and the week start day are Tableau data source
settings, and they do not travel with the fields when a connection is replaced.
Check them explicitly after the swap, because a reset fiscal calendar reshuffles
every year-to-date figure on the dashboard.

## Things attached to the connection rather than the data

Easy to miss because they are not fields and not formulas:

- **Initial SQL.** A connection can carry statements that run when it opens —
  session settings, a role or warehouse selection, parameters. Dialect-specific by
  nature, and silently absent after a swap.
- **Custom SQL.** Named tables and columns in the old dialect, plus functions that
  may not exist in the new one. A filter in the workbook is applied around the
  custom SQL rather than inside it, so the subquery runs as written on every
  query. Each custom SQL relation is a hand-migration.
- **Pass-through SQL in calculations.** Raw SQL embedded in a Tableau calculation,
  in the old dialect by definition.
- **Connector capabilities.** Features that depend on what the connector can do on
  the engine's side — the temporary-table work behind context filters is the usual
  example — are not uniform across connectors. Worth confirming on the target
  rather than assuming the behaviour carried over.
- **Row-level security.** A user filter either embeds names or joins to a table
  that maps users to data. The table has to exist in the new warehouse, with the
  same usernames, or the filter silently stops restricting.

## Published data sources change the blast radius

If the connection is a published data source rather than an embedded one, the swap
happens once in a place every consuming workbook inherits. That is an advantage
for the migration and a hazard for everything else: workbooks nobody mentioned
change at the same moment, including ones whose owners are not in the
conversation.

Before repointing a published data source, find out what consumes it. The server
knows; the workbook in front of you does not.

## The checks worth running against the target first

Each of these is cheap and settles one of the above before anything is repointed:

- list the columns of a few tables as the engine reports them, and compare the
  casing against the workbook's fields
- select one row of each type-sensitive column and look at how the value arrives:
  a timestamp's zone, a decimal's precision, a boolean's representation
- count nulls and empty strings in the columns the dashboard filters on
- run one of the custom SQL statements unchanged, and record which functions it
  complains about
- compare the distinct values of a field that carries aliases or groups against
  the alias definitions in the workbook
