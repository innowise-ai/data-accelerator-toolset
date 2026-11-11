---
name: tableau-performance-diagnosis
description: Finding out why a Tableau dashboard is slow - which interaction is slow and for whom, splitting query time from Tableau's own compute from rendering, and what the workbook's structure can and cannot prove. Use when a dashboard or a worksheet is slow and the cause is not yet established. Not for rewriting calculations before the cause is known.
---

# Diagnosing a slow dashboard

A slow dashboard attracts confident advice: reduce the marks, switch to an
extract, replace the level-of-detail expressions. Each of those is sometimes the
answer and usually not, and acting on the wrong one costs a rewrite plus the
original problem. The expensive mistake here is not failing to find the cause. It
is being persuasive about the wrong one, because a plausible fix that changes
nothing is also a fix that nobody re-examines.

So this is diagnosis, and it ends at a cause with evidence behind it. A rewrite
starts after that, and only for the cause you proved.

Its neighbours in this catalog:

- [snowflake-query-profile-diagnosis](../SNOWFLAKE-QUERY-PROFILE-DIAGNOSIS/SKILL.md)
  takes over when the time turns out to be in the warehouse. The split between the
  two is the first thing this skill establishes, and getting it wrong is how a
  team spends a week on a workbook whose queries were queueing.
- [snowflake-cost-hotspots](../SNOWFLAKE-COST-HOTSPOTS/SKILL.md) finds which
  queries are worth attention at all, which is the question when the dashboard is
  fast but expensive.
- [tableau-workbook-audit](../TABLEAU-WORKBOOK-AUDIT/SKILL.md) notes performance
  risks it can see in a workbook's structure. Those are hypotheses; this skill is
  about testing them.
- [error-diagnosis](../ERROR-DIAGNOSIS/SKILL.md) is the general version of the
same discipline — narrow it down, prove it, then change something.

How to read a performance recording, and what the workbook's structure does and
does not imply, are in
[references/performance-recording.md](references/performance-recording.md).

## Find out what "slow" means first

"The dashboard is slow" is four different problems, and they share almost no
causes:

| What is slow | Where to look first |
|---|---|
| First load, every time | Query volume and the cost of the initial queries at default filter state |
| First load for the first user of the day, fast afterwards | Caching, warehouse or extract warm-up — the workbook may be fine |
| Changing a filter or parameter | What that control re-triggers, and how many sheets it touches |
| Switching tabs | The queries of the newly shown sheets, which were not run until now |
| One specific worksheet | That sheet alone, which is a much cheaper investigation |
| Slow for some users only | Permissions, row-level filtering, network, or a different device layout — not the calculations |

Ask for the number too. "Fifteen seconds" and "ninety seconds" rarely have the
same cause, and "slower than it used to be" is a different investigation
altogether: something changed, and finding what changed beats profiling.

This conversation is not a formality. Half the time the answer narrows the problem
to one sheet or rules out the workbook entirely, before anything has been opened.

## Split the time before explaining it

Three places time goes, and a cause in one of them cannot be fixed in another:

1. **Running the queries** — the warehouse for a live connection, the extract
   engine for an extract.
2. **Tableau's own compute after the data arrives** — table calculations, totals,
   sorting, data blending.
3. **Building and rendering the view** — layout and marks.

A performance recording gives you this split directly, which is why it is worth
asking for before theorising. It attributes events to a category and a worksheet,
so the output is "sheet X spent eleven of its twelve seconds executing one query"
rather than an opinion.

Without a recording you can still reason from structure, but say which you are
doing. A structural reading produces candidates ranked by likelihood; it does not
produce a cause. Presenting one as the other is the failure mode of this whole
task, and it is invisible in the write-up.

## What each kind of time usually means

**Query time dominates, connection is live.** This is a warehouse question now,
not a workbook one. Get the query Tableau sent and diagnose it where the engine
can be measured. The workbook's contribution is what it asked for — the grain, the
filters it pushed down, and the joins it defined — and that is worth checking
before concluding, but the time is being spent elsewhere.

**Query time dominates, connection is an extract.** The extract is doing work it
should not have to. Usually it holds far more rows or columns than the views
aggregate to, or the views ask for a grain the extract cannot answer without
scanning all of it. An extract is not a performance setting; it is a copy, and a
copy of too much data is slow in the same way the original was.

**Many short queries rather than a few long ones.** A dashboard issues at least
one query per worksheet, plus queries for filter domains. Nothing is slow
individually and the dashboard still takes twenty seconds. The fix is fewer
queries — fewer sheets, shared data sources, filters that do not each need their
own lookup — not faster ones.

**Compute after the data arrives.** Table calculations, totals and sorting happen
locally on the returned result, so this time scales with how many rows came back,
not with how many are displayed. A view showing twelve numbers can return a
million rows to compute them. Data blending lands here too, and it is worth
checking early when exactly one sheet is slow.

**Layout and rendering.** Mark count is the thing that matters, and it is easy to
underestimate: a text table is one mark per cell, so a crosstab a user scrolls
through can carry tens of thousands. Custom shapes, many filter controls shown on
the dashboard, and heavy formatting add to it. This is also the only category a
faster warehouse cannot help with.

## Filters are the most common fixable cause

Worth checking early because the cost is configuration rather than design, so the
fix is cheap once identified.

- A filter set to show only relevant values has to query for its own list of
  values, and query again whenever a related filter changes. One such filter is
  fine; a row of them means every interaction fans out into several queries.
- A filter over a long list of discrete members is more expensive than a range or
  a relative date over the same column, and gets slower as the member list grows.
- A context filter materialises an intermediate result. That pays off when it cuts
  the data down a lot and rarely changes, and costs an extra round trip when it
  does not. It is not a general speed-up, despite being recommended as one.
- A filter on a calculated field cannot always be pushed down the way a filter on
  a stored column is, so the calculation gets evaluated before the filter applies.
- A filter applied to all sheets using a data source multiplies the queries that
  re-run on every change to it.

Note what is *not* in this list: hiding or showing a filter control, and tidying
up which filters are visible. Those change what a user can do and what the view
returns, not what it costs. Treat a change in the filter set as a change in
results until proven otherwise.

## Calculations: where the work happens

The useful distinction is not complex against simple. It is where the calculation
runs:

- **Row-level and level-of-detail expressions run in the query.** An LOD becomes
  additional aggregation in the SQL Tableau generates, so its cost shows up as
  query time, and nesting them compounds there.
- **Table calculations run locally, on the returned result.** Their cost is
  Tableau's compute plus the data transfer needed to feed them, because the result
  set has to carry every row the calculation addresses.

That is why "replace the table calculation with an LOD" sometimes helps and
sometimes moves the cost from a place that was fine to a place that was not. Which
direction is an improvement depends on which of the three times was dominating,
which is the measurement you took first.

String operations and long nested conditionals are plausible contributors, and
plausible is all they are. Measure them; do not lead with them.

## Prove the cause, then change one thing

The standard that makes this diagnosis worth anything: name the cause, say what
evidence supports it, and predict what the fix will do before doing it. Then do
one thing and measure again. Changing the filter configuration, the extract shape
and three calculations together leaves you with a dashboard that is faster for
reasons nobody knows, which is a dashboard that will be slow again.

When the fix is a calculation rewrite, the measurement is only half the check. The
other half is that the numbers did not change.

**This is the part to be slowest about.** Tableau's calculation language is a
narrow one, and rewriting level-of-detail expressions and table calculations in it
is the kind of task where a confident answer is wrong far more often than the
difficulty suggests — the same expression means different things depending on the
shelves, the filters and the sheet's grain, and nothing in the formula says which.
Simplicity of the request is not protection; a one-line rewrite is as likely to be
wrong as a complicated one.

So treat any rewritten calculation as unverified until the view's numbers are
compared before and after, at the same filter and parameter state, on more than
one slice — and where the number has an independent source, until a query against
the warehouse agrees with it. Iterating on a formula until it looks right is not
verification, and after a few rounds of it, working the logic out by hand is
usually both faster and more trustworthy than another attempt.

## When to stop and say it is not the workbook

Some causes are outside the file, and the sooner they are named the better,
because every one of them survives a workbook rewrite:
- the warehouse is saturated and the queries are queueing
- row-level security or a user filter makes each user's query a different, harder
  query
- the extract refresh is what is slow, not the dashboard
- the network between the user and the server, or a device layout nobody tested
- the dashboard was never fast and is only now being complained about, in which
  case the question is what it is expected to do rather than why it does not

A dashboard can also be as fast as its design allows. A view over a billion rows
with no aggregation is not a defect to diagnose, it is a requirement that needs
renegotiating, and saying so is a more useful outcome than a list of
micro-optimisations that will not add up to the difference.
