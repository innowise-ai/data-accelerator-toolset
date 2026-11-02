---
name: tableau-pulse-readiness
description: Defining Pulse metrics on a published data source so the generated insight is a statement about the intended number, and checking an existing insight against the SQL metric it claims to represent. Use when a published Tableau data source should feed Pulse metrics, or a Pulse insight needs to be checked against the SQL metric it claims to represent.
---

# Getting a data source ready for Pulse metrics

Pulse is a metrics layer over a published data source. A metric is a small
definition — one measure with an aggregation, a time dimension, optional
filters, the dimensions it may be broken down by, and a comparison over time.
An insight is a sentence about that comparison: it went up, it went down by
this much, this segment drove it.

That sentence is the problem. An insight is generated prose about whatever the
definition selected, and it reads with the same fluency whether the definition
was right or wrong. A dashboard shows a reader a number in a context they can
argue with; an insight hands them a conclusion. So the whole question is whether
the definition picks out the number someone meant, because nothing downstream
will reveal that it did not.

This skill defines and checks that metric. It does not subscribe users, post to
a channel, or call an API.

The queries that settle a comparison are in
[references/comparison-crosscheck.md](references/comparison-crosscheck.md).

Its neighbours in this catalog:

- [tableau-measure-translation](../TABLEAU-MEASURE-TRANSLATION/SKILL.md)
  rewrites the calculation when the data source's formula is why the insight
  disagrees with SQL. This skill chooses the measure, the time column and the
  filters, and checks the comparison; it does not rewrite the field.
- [kpi-definition-building](../KPI-DEFINITION-BUILDING/SKILL.md) settles what
  the metric is before any of this. A Pulse definition is narrow — one measure,
  one date, a filter set — and a metric whose population or date was never
  agreed cannot be made safe by binding it to a narrow definition.
- [tableau-dashboard-faq](../TABLEAU-DASHBOARD-FAQ/SKILL.md) takes a metric's
  meaning from the definition the workbook already carries rather than from a
  field name. The same discipline applies here: do not invent a field
  definition. A caption, a calculated field and a warehouse column can share a
  word, and the metric binds to the one you name, not to the one the word
  suggests.

## What decides whether the insight is the metric you meant

**The aggregation has to be the SQL's aggregation.** Summing a rate, a
percentage, or a value that was already aggregated upstream produces a smooth,
confident insight about a quantity nobody defined. A ratio is a numerator and a
denominator, carried as two measures and divided, not an average of per-row
ratios — unless the SQL metric genuinely is that average, in which case say so,
because the two are told apart by the definition and by nothing else.

**The time dimension is part of the definition, not a display setting.** Order
date and ship date both support "last month" and they answer different
questions, by an amount that varies with how the business is running. Name the
column. And the column's grain has to match the comparison: a daily fact rolled
up to months is a month's activity, while a monthly snapshot summed across its
days is not a month-end balance, it is that balance multiplied by the number of
days recorded.

**Filters are the population.** Data source filters, extract filters and the
metric's own filters stack, and the insight is about whatever survived all of
them. An insight that does not state its population is not comparable with a
query that had a `WHERE` clause, and the usual outcome is a long disagreement
about a difference that was a filter nobody mentioned. Write down which filters
are in force and where each one lives.

**Breakdown dimensions have to sit at or above the metric's grain.** A dimension
that fans the fact out — one that arrives through a join which multiplies rows —
changes the number the moment a reader slices by it, so the total and the sum of
its parts stop agreeing. Whether the fan-out already happened is decided by how
the data source combines its tables: a relationship aggregates each table at its
own grain before combining, a physical join can multiply rows first, and a blend
matches on the linking fields only. Allow the breakdowns you have checked rather
than everything the source exposes.

**A level-of-detail field has already collapsed the grain.** A `FIXED`
expression computes at the dimensions it names and ignores everything else, so
by the time Pulse aggregates it the figure is a per-entity total being added up
again. Hand that field to
[tableau-measure-translation](../TABLEAU-MEASURE-TRANSLATION/SKILL.md) before
accepting it as a measure. Do not re-aggregate it on the assumption that the
result still means what the field's name says.

**An extract has a refresh time; a live connection does not.** An insight
computed on an extract is a statement about the extract, which is as old as the
last refresh — so an insight can be accurate about yesterday and wrong about
this morning, with nothing in its wording to say which. Record which kind of
connection the source uses, and the refresh time if you can get it, as part of
what the metric covers.

**A goal is a target, not a second measure.** It only becomes one when a target
column exists in the data and the metric binds to it. Otherwise it is a number
someone typed, and an insight comparing against it is comparing against that
person's intent at the time they typed it.

## Checking an insight

An insight is checked when the comparison behind it has been recomputed
independently. The steps are short and the third one is the one to be honest
about.

Write the comparison out in words first: which measure, this period against
which previous period, at which grain, under which filters. Most disagreements
are already visible here, because stating the previous period forces out whether
it was a complete period or a partial one.

Then recompute it from the SQL metric — or from the translated SQL, when the
source is a level-of-detail field — and compare the two numbers, not the two
directions. An insight that says "up" when the real figure is up is agreement on
one bit of information, and a metric can produce the right direction from the
wrong population for a long time.

If it cannot be recomputed, the insight is unchecked, and that is the finding to
report. A well-worded sentence is not a check, and neither is an insight that
looks consistent with last week's.

When the data source itself cannot be read, stop and ask for what makes the
definition legible: the field list, which field is the measure and what
aggregation it carries, the time column, the filters in force at every level,
whether the source combines tables with relationships, joins or a blend, and
whether it is an extract or live. Those are the inputs; guessing any of them
produces a definition that validates and means nothing.

## What to hand back

The metric's definition — measure, aggregation, time column, filters, the
breakdowns that are allowed, and the goal if there is one — stated as a
definition rather than as settings.

Then what it actually covers: the population the filters leave, and the
freshness the connection gives it, including the refresh time when the source is
an extract.

Then the breakdowns that would change the grain, named as such, because the
reader who finds one is otherwise entitled to assume every dimension is safe.

And for any insight under review: the comparison in words, the independently
computed number, and whether the two agreed — or, where they could not be
compared, the statement that the insight is unchecked.
