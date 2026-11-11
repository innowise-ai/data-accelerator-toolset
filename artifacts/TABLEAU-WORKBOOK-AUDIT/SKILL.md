---
name: tableau-workbook-audit
description: Assessing an inherited Tableau workbook from its file - the inventory worth taking, what "unused" can and cannot mean, which dependencies make a change risky, and when a connection choice is a finding. Use when taking over, reviewing or estimating work on a workbook nobody on the team built. Not for documenting a dashboard for its readers.
---

# Auditing a Tableau workbook

The question behind this work is never "is this workbook good". It is one of
three: can I safely change it, what will it cost to maintain, or what did we just
inherit. The audit is worth doing because a workbook hides its own complexity —
drag-and-drop authoring leaves no diff, no module boundaries and no import graph,
so the only way to find out what is in one is to read the file.

What makes this hard is not reading the XML. It is that most of what an inventory
turns up is unremarkable, and the findings that matter are a handful of
relationships between items that each look fine alone. A report listing eighty
calculated fields is not an audit. An audit says which four of them a change would
propagate through, and why.

The file mechanics — what the elements are, where each fact lives, what the file
does not record — are in
[references/workbook-xml.md](references/workbook-xml.md).

Its neighbours in this catalog:

- [tableau-dashboard-faq](../TABLEAU-DASHBOARD-FAQ/SKILL.md) writes the dashboard's
  documentation for the people who read the dashboard. This is an engineering
  assessment for the people who maintain it, and the two want opposite things from
  the same file: the FAQ discards everything the dashboard does not use, while
here the leftovers are the point.
- [tableau-workbook-diff](../TABLEAU-WORKBOOK-DIFF/SKILL.md) reviews a change to a
  workbook by comparing two versions of it. This assesses one workbook in its
  current state, with no change on the table yet.
- [tableau-performance-diagnosis](../TABLEAU-PERFORMANCE-DIAGNOSIS/SKILL.md) takes
  over when something is actually slow. This audit records the performance risks
  visible in the structure and stops there, because structure suggests cost and
  only a measurement establishes it.

## Take the inventory, but hold it as evidence

Six lists, in a form you can cross-reference rather than read:

| List | Why it is needed later |
|---|---|
| Data sources, their connectors, extract or live, custom SQL | The boundary to the warehouse, and the thing most likely to break outside the workbook |
| Worksheets, and which dashboard each appears on | Tells you what is reachable; a worksheet on no dashboard is reachable only as a tab |
| Dashboards and their tabs | The unit a user thinks in, and the unit a change is judged by |
| Calculated fields, with their formulas | The actual logic of the workbook |
| Parameters, with their domains and current values | Inputs that change results without editing anything |
| Filters, with their scope | The difference between "this sheet" and "every sheet on the source" |

The lists exist so you can answer questions across them. "Which worksheets use
this calculation" is the question that makes the rest useful, and it needs the
field list and the worksheet list joined, not either one printed.

Count things as you go and say what the counts are, because a reader's first
question is scale. But do not mistake counts for findings: four hundred fields in
a workbook feeding thirty worksheets for forty analysts is a normal large
workbook, and thirty fields in a workbook nobody can safely edit is a problem.

## "Unused" is three different claims

This is where an audit most often overstates what it knows. Before writing that
anything is unused, be specific about which of these you mean, because they carry
different confidence and different recommended actions:

- **Not referenced anywhere in the file.** Defensible from the file alone: no
  worksheet, no other calculation, no filter, no parameter action, no tooltip and
  no title string mentions it. Note the last two — a field referenced only from a
  tooltip or a dynamic title is in use, and a search that only looks at shelves
  will miss it.
- **Referenced only by other unused things.** A chain of calculations ending in
  nothing. Resolve the chain before reporting any link in it, or the report
  understates by a lot.
- **Not used by anyone.** Not a claim the file can support at all. A worksheet on
  no dashboard may still be the one view a finance team opens every month; a
  hidden field may be a scaffold for an in-progress change. Usage lives in the
  server's view statistics, and in asking.

So report the first two and say which. The useful finding is not "delete these
twelve fields" but "these twelve are unreferenced in the file, which is worth
confirming against view statistics before anyone removes them". Recommending a
deletion the file cannot justify is how an audit loses the reader.

## The dependencies that make a change risky
A change-risk finding needs a reason, not a count of dependents. Four shapes are
worth looking for specifically:

**A calculation many others are built on.** Editing it edits every dependent, and
nothing in the workbook will tell you which views moved. The risk scales with how
far the chain goes rather than how many direct dependents there are, because a
long chain is where the author's intent gets hard to recover.

**A field whose aggregation is decided somewhere else.** A row-level expression
can be aggregated differently on each shelf that uses it, so the same field means
different things on different sheets, and a change that is correct on one is wrong
on another. Any field used at more than one grain is a finding on its own.

**Custom SQL.** It couples the workbook to table and column names in the
warehouse, invisibly from the warehouse's side: a rename upstream breaks the
workbook and nothing upstream knows the workbook exists. Record every custom SQL
relation and the objects it names, because this is the dependency most likely to
break without anyone touching the workbook.

**A parameter with no constraint.** Parameters change results, are user-settable,
and do not have to be validated against anything. One that drives a calculation
and accepts any value is a way for a reader to produce a wrong number without
doing anything wrong.

## When a connection choice is a finding

Live versus extract is not a quality setting, which is why "should be an extract"
is a bad finding and a common one. Each is correct for a different requirement,
and the finding is a mismatch between the choice and what the dashboard is for:

| What you see | What it means |
|---|---|
| Live connection, dashboard used for reviewing yesterday's numbers | Every view costs the warehouse a query for freshness nobody needs |
| Extract, and the dashboard is described as real-time | The data is as old as the last refresh, whatever the dashboard claims |
| Extract whose row count is far beyond what the views aggregate to | The filtering should be happening before the extract, not after |
| Live connection onto custom SQL | The custom SQL runs on every interaction, and it is not a table the warehouse can optimise for |
| Several data sources that connect to the same table | Each one is a separate query path and a separate place to fix a change |

Which means you have to know what the dashboard is for before the connection can
be assessed. If nobody has told you, that is a question, not an assumption.

## Maintainability findings worth the reader's attention

Not style. The things that cost the next person real time:

- **Duplicate logic.** Several calculations computing the same thing under
  different names, usually because the author could not find the existing one.
  The cost is that a rule changes in three places and gets changed in one.
- **Logic that belongs upstream.** A calculation reimplementing a join, a
  deduplication or a business rule the warehouse could hold once for every
  consumer. This is a real finding and also the one most likely to be out of
  scope — say it, do not design the migration.
- **Names that do not survive their author.** Fields captioned for a context that
  is gone, or distinguished only by a suffix. A reader cannot tell which to use,
  so they make a fourth.
- **A dashboard assembled from sheets that nothing else uses, nested several
  containers deep.** Rearranging it is then far more expensive than it looks, and
  that matters for an estimate.

## What this audit cannot conclude

Say these out loud in the report rather than leaving a reader to assume
otherwise. An audit that states its own blind spots is trusted on the rest.

- **Whether a number is right.** The file contains formulas, not results. A
  calculation can be read, found plausible, and still be wrong against the
business rule, and the file holds no business rule to check it against.
- **Whether anything is actually slow.** Structure suggests where cost would come
  from. It does not measure it, and the usual suspects are frequently not the
  cause.
- **What it looks like.** The rendered result is not in the file. Any finding
  about a view's readability or layout needs a screenshot.
- **Who uses it.** Server-side statistics, not the workbook.

A formula is also the place to be least confident. Tableau's calculation language
is a small one, and reading someone else's level-of-detail expression or table
calculation correctly is harder than it looks — the same formula means different
things depending on the shelves around it. When a finding depends on what a
formula does, say what you read and treat the reading as provisional until someone
who knows the workbook confirms it. A confidently wrong summary of a calculation
is worse than a flagged uncertainty, because it ends the conversation that would
have caught it.
