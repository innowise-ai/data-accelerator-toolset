---
name: tableau-datasource-migration
description: Moving a Tableau workbook's connections to a different warehouse - the inventory to take first, what breaks silently when fields are rebound by name, which calculations are dialect-bound, and how to prove the dashboard still produces the same numbers. Use when a workbook has to point at a new warehouse or a replacement data source. Not for designing the warehouse it is moving to.
---

# Repointing a workbook at a new warehouse

The workbook is the last thing anyone remembers when a warehouse is replaced, and
it is the thing that fails in front of users. The migration itself is usually one
operation — swap the connection, let Tableau rebind the fields by name — and that
operation is exactly what makes this risky, because its failure mode is partial
success. Most fields rebind, the workbook opens, the dashboard renders, and some
of the numbers are different.

So the work is not the swap. It is knowing beforehand what in this workbook will
not survive it, and afterwards proving that what did survive still means the same
thing.

**Where this stops.** The question here is what in the workbook breaks. Whether
the new warehouse is modelled well, whether the tables should be restructured,
and what the pipeline that fills them should look like are all out of scope. The
temptation to redesign on the way across is strong and it turns a reversible
migration into a project — if the model genuinely has to change, that is a
separate piece of work with its own verification, run before or after this one and
not inside it.

Its neighbours in this catalog:

- [dbt-legacy-sql-migration](../DBT-LEGACY-SQL-MIGRATION/SKILL.md) ports SQL into
  dbt and reconciles it. That is the warehouse side of the same programme and it
  is where logic lifted out of this workbook should land; this artifact does not
  move logic anywhere, it repoints a report.
- [tableau-workbook-audit](../TABLEAU-WORKBOOK-AUDIT/SKILL.md) produces the
  inventory this migration starts from. Run it first if nobody knows what is in
  the workbook.
- [tableau-workbook-diff](../TABLEAU-WORKBOOK-DIFF/SKILL.md) compares the
  before-and-after workbook, which is a useful cross-check on what the swap
  actually changed in the file.

Connector-level detail — identifier casing, types, dialect-bound constructs — is
in [references/warehouse-differences.md](references/warehouse-differences.md).

## Inventory before touching anything

The migration is only as good as this list, and it is much cheaper to build before
the connection changes than after:

- **Every connection**, including the ones on data sources no dashboard uses. They
  will all try to rebind.
- **Every custom SQL relation**, with its full text and the objects it names. This
  is the largest single source of breakage, because it carries warehouse
  identifiers in a form nothing validates until it runs.
- **Every field**, with its source column, data type, role and default
  aggregation. This is the mapping the rebind will be judged against.
- **Every calculation**, flagged for anything dialect-bound — pass-through SQL
  above all, then date arithmetic and string handling.
- **Field aliases, groups, sets and hierarchies**, with the domain values they are
  defined over.
- **Data source settings that are not fields**: extract filters, the fiscal year
  start, the week start day, default date formats, geographic roles.
- **Row-level security**: user filters and any calculation referencing the current
  user, together with whatever table backs them.

Take a screenshot of each dashboard at a known filter state before starting, and
record the numbers it shows. That is the baseline, and after the swap there is no
way to reconstruct it.

## What the rebind does, and what it does quietly

Replacing a data source matches fields by name. Three outcomes, and only the first
one announces itself:

**It cannot find the field.** Visible: the field is marked as broken and
everything referencing it is broken too, including calculations several steps away.
Noisy, annoying, and the best case — you know.

**It finds a field whose name matches and whose type changed.** Partly visible.
A number arriving as a string, or a date arriving as a string, changes what the
field can do and how it sorts, and a measure that becomes a dimension stops being
aggregated. The view still renders.

**It finds a field whose name matches and whose values differ.** Invisible. The
column is called the same thing and holds something slightly different — a
different case, trimmed differently, a different unit, nulls where there were
zeros. Nothing breaks and nothing warns. This is the outcome the verification step
exists for, because no amount of reading the workbook will find it.

Two specific things to check for the third case, because they are common and look
like a rendering bug rather than a data change:

- **Aliases and groups are defined over literal domain values.** Change the
  casing or the whitespace of the underlying values and the alias no longer
  matches, so the raw value appears where the friendly label was, and a group
  quietly loses members to an "other" bucket.
- **Identifier casing propagates.** Warehouses disagree about how unquoted names
  are folded, so the same logical column can arrive with a different name and
  nothing will rebind to it. This is the most common cause of a mass rebind
  failure, and it is worth establishing before the swap rather than diagnosing
  after.

## Calculations that are not portable

Most Tableau calculations are portable, because Tableau generates the dialect. The
exceptions are worth finding individually:

- **Pass-through SQL.** A calculation that embeds raw SQL is written in the old
  warehouse's dialect by definition. It will not translate and it may not fail
  loudly. Every one of these is a hand-migration with its own check.
- **Date arithmetic at the edges.** Truncation, week and quarter boundaries, and
  anything involving a fiscal calendar depend on both the warehouse's behaviour
  and the data source's own settings, which do not move with the fields.
- **Timestamps and time zones.** A column that was naive and is now zone-aware, or
  stored in a different zone, shifts every date-bounded number by up to a day at
  the boundaries — which is exactly where a daily or monthly total is read.
- **Numeric type changes.** Integer division, and precision on a column that
  changed from a fixed decimal to a float, change results in small amounts that
  survive review and fail reconciliation.
- **Null handling.** Whether the source produces a null or an empty string decides
  what every conditional over that field does.

When a calculation has to be rewritten, treat the rewrite as unverified. Tableau's
calculation language is a narrow one and a plausible-looking replacement is wrong
more often than the difficulty suggests, especially for level-of-detail
expressions, where meaning depends on the sheet's grain rather than the formula.
The check is numbers, not inspection.

## Re-decide live against extract, deliberately

Do not carry the old choice over on the grounds that it was the old choice. The
reason it was made may have been the old warehouse's performance, or an
availability window, or a cost model, and the new one is different on all three.

Make it an explicit decision with a reason recorded. If the workbook was live
because the old warehouse was cheap to query all day, and the new one meters
compute per query, a dashboard a hundred people open becomes a line item.

## Proving it still works

This is the part the migration is judged on, and the standard has to be higher
than "the dashboard opens".

Compare the same views, at the same filter and parameter state, before and
after — using the baseline captured at the start, because after the swap there is
nothing to compare against.

Compare at more than one level. A matching headline total is weak evidence: two
offsetting errors cancel in an aggregate and separate at a lower grain. So check
the total, then check it broken down by the dimension the dashboard actually
filters on, and check a row count.

Check the specific things that fail silently:

- totals at a date boundary, where a time zone shift shows up
- a measure's null and zero counts, which decide what averages mean
- any field with aliases or groups, by looking for unlabelled values
- each row-level-security filter, by checking as a user who should see less — not
  by reading the filter

When something does not reconcile, resist repointing it back. The useful question
is which of the three rebind outcomes produced it, because that determines whether
the fix is in the workbook, in the new warehouse, or in an assumption the old
workbook was making that nobody had written down. The third one is common and it
is a finding worth more than the migration.
