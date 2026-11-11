---
name: tableau-analytical-calcs
description: Implementing known metric shapes in Tableau - cohort retention, funnels, period-over-period, rolling averages, rankings and Pareto - by choosing between a row-level expression, a level-of-detail expression and a table calculation, and knowing which filters silently change the answer. Use when a settled metric has to be built as a Tableau calculation. Not for deciding what the metric should be.
---

# Implementing analytical calculations

The metric shapes here are well known. Retention by cohort, a funnel, year on
year, a rolling average, a rank, a Pareto curve — none of them is conceptually
difficult, and every one of them has a standard way of going wrong in Tableau.

The reason is that Tableau offers three places to compute something, they are not
interchangeable, and the difference only shows up once a filter is applied. A
calculation that is right on an unfiltered sheet and wrong the moment a user picks
a date range is the normal outcome of guessing between them, and it is the kind of
wrong that nobody reports as a bug because the chart still looks like a chart.

So this is about choosing the construct, and about the filter interactions that
decide whether the choice was correct. It is not a formula library: a formula
copied without the grain and filter context it assumed is how these metrics break.
Its neighbours in this catalog:

- [kpi-definition-building](../KPI-DEFINITION-BUILDING/SKILL.md) decides what the
  metric *is* — its population, grain, date and roll-up. Start there if any of
  those is unsettled, because every choice below depends on them and implementing
  an unsettled metric produces a number that cannot be checked against anything.
- [tableau-performance-diagnosis](../TABLEAU-PERFORMANCE-DIAGNOSIS/SKILL.md) is
  where a correct but slow implementation goes. Correct first: these constructs
  differ in cost, and the cheapest one that is wrong is not a trade-off.
- [snowflake-query-rewrite](../SNOWFLAKE-QUERY-REWRITE/SKILL.md) is the equivalent
  discipline in SQL — change the shape, keep the results — and it is the right
  home for logic that should not be in a workbook at all.

The queries that confirm each shape are in
[references/sql-crosscheck.md](references/sql-crosscheck.md).

## Three places a calculation can run

Choose by what the metric has to see, not by what is easiest to write:

| The metric needs | Construct | Where it runs |
|---|---|---|
| A decision per record | Row-level expression | In the query, before aggregation |
| An aggregate at a grain the view does not show | Level-of-detail expression | In the query, as extra aggregation |
| Values from other rows of the result — a previous period, a running total, a rank, a share of total | Table calculation | Locally, after the result comes back |

The distinction that matters: a level-of-detail expression is part of the query, so
it is subject to the filters that run before it; a table calculation operates on
whatever the query returned, so it is subject to the *shape* of that result —
which rows are present and in what order.

Two consequences worth holding on to:

- **If the view's grain is already the metric's grain, no level-of-detail
  expression is needed.** Reaching for one anyway is the most common piece of
  over-engineering here, and it adds a grain that then has to be kept consistent
  with the view's.
- **A table calculation cannot see rows the query did not return.** Everything in
  the next two sections follows from this.

## The shapes, and what each one actually requires

**Cohort retention.** Needs a per-entity anchor — first purchase, signup, first
activity — that does not move when the view is filtered. That is a
fixed-grain aggregate at the entity level, and it is fixed specifically so that a
date filter narrowing the view does not redefine which cohort someone belongs to.
Getting this wrong produces a retention chart where every cohort looks healthy,
because the filter silently re-anchored everyone into the visible window.

**Funnels.** Needs the furthest stage each entity reached, which is a per-entity
aggregate, then counted at the stage grain. Two defects: counting events rather
than entities, so one person visiting a page twice becomes two; and assuming the
funnel is monotonic. Whether an entity that skipped a stage counts as having
passed it is a definition question, and if the definition does not answer it the
implementation will answer it accidentally.

**Period over period and year on year.** Needs the comparable prior value on the
same row. A table calculation offset is the easy implementation and it shifts by
**position in the result, not by date** — so a month with no rows is not an empty
month, it is absent, and every comparison after it is off by one period. This is
the single most common silent defect in this whole group, it survives every spot
check on dense data, and it appears the first time a product has a quiet month.
Either guarantee a complete date spine in the result, or compute the shift in the
data where the dates are real.

**Rolling averages.** Same missing-period problem, plus a second one at the edges:
the first few points in a window average fewer values than the rest, so the series
starts with a slope that is an artefact of the window rather than the data. Decide
whether partial windows are shown, suppressed, or labelled — and say so on the
chart, because nobody reading it can tell.

**Rankings.** A table calculation ranks what the view returned. That is correct
only if the view returned the whole population the ranking is over. Filtering
before the rank changes the ranks; filtering after it — a filter applied to the
table calculation itself — keeps the original ranks and shows a subset of them.
Both are legitimate and they answer different questions: "the top ten of the
selected region" against "which of the global top ten are in this region".

**Pareto and share of total.** A running total over a sorted result, which makes
the sort part of the logic rather than presentation. And the denominator is the
total of the returned result, not of the population, unless something was done to
make it otherwise. A Pareto curve on a filtered view reaches 100% of the filtered
subset and says nothing about the whole.

**Period to date.** Depends on what "now" means and on partial periods. Comparing
a part-month against a full prior month is the most common misleading chart in
reporting, and it is produced by a correct calculation.

## Filters that change the answer without looking like it

Tableau applies filters and calculations in a fixed order, and most of the defects
above are really that order being misunderstood. Three specifics:

**A fixed-grain expression is evaluated before dimension filters.** So it does not
see them. This is a feature — it is what makes a stable cohort anchor possible —
and it is a defect wherever the metric was supposed to respect the user's
selection. The same filter promoted into context *is* seen by it, which means
adding a context filter anywhere changes every fixed-grain expression in the
workbook.

**A filter on a table calculation is applied last.** It hides marks without
removing their rows from the calculation. That is exactly right for showing part
of a ranking, and exactly wrong for a total or a share: the percentages will not
add up to what is on screen, and the reader will assume the chart is broken rather
than that the total is deliberate.

**Hiding is not filtering.** A hidden member is removed from the display while its
data remains in the result, so totals, running totals and table calculations still
include it. Using hide to drop an outlier leaves the outlier in every derived
number on the sheet. If the definition excludes something, exclude it; hiding is a
presentation choice and should only ever be used as one.

## Verify against SQL, and treat the formula as unverified until you do

This is not optional diligence on these shapes, it is how they are built.

**Tableau's calculation language is a narrow one, and it is a language where
confident answers are wrong far more often than the difficulty suggests.** A
one-line level-of-detail expression or a table calculation that reads correctly is
not evidence of anything: the same expression means different things depending on
the sheet's grain, its filters and its sort, and none of that is in the formula.
The apparent simplicity of the request is not protection — if anything it is the
risk, because an easy-looking metric does not get checked.

So: write the equivalent query, from the metric definition rather than from the
Tableau calculation, and require the numbers to match. Transcribing the
calculation into SQL reproduces the same misunderstanding and agrees perfectly.

Compare on more than one slice, and specifically at the places these shapes fail:

- a period with no data, for anything period-over-period or rolling
- the first and last periods in the range, where windows are partial
- a filtered view against an unfiltered one, which is where the construct choice
  shows
- the row count beside the value, because an entity-count metric that is counting
  events matches on totals and not on counts

And one practical note on iteration. Adjusting a formula until the number looks
plausible is not verification, and on these constructs it converges slowly. After
two or three attempts, working the logic out by hand — what grain, which rows,
which order — is usually both faster and more likely to be right than another
guess.
