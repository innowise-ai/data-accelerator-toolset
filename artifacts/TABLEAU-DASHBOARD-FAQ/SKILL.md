---
name: tableau-dashboard-faq
description: Writing the FAQ for an existing Tableau dashboard from the workbook file and a screenshot of the landing view - where a metric definition may legitimately come from, what the file cannot tell you, and which facts have to be asked for. Use when an existing Tableau dashboard needs documentation its readers can rely on. Not for assessing a workbook's engineering quality.
---

# Writing a dashboard FAQ

A dashboard FAQ answers the questions its readers ask in chat instead: what does
this number mean, what is it for, how do I drive it, where does it come from, how
old is it. Those answers already exist, scattered across the workbook, the
schedule, and the head of whoever built it. The work is collecting them without
inventing the parts that are missing — and a dashboard FAQ is unusually easy to
invent, because a plausible definition of "active customer" is easy to write and
impossible for a reader to tell apart from the real one.

So the discipline here is about sourcing, not about prose. Every line in the FAQ
should be traceable to the workbook, to the screenshot, or to an answer someone
gave you. Nothing else goes in.

The mechanics of reading a workbook — getting at the XML, which elements carry
which facts, and what they do not carry — are in
[references/workbook-xml.md](references/workbook-xml.md).

Its neighbours in this catalog:

- [tableau-workbook-audit](../TABLEAU-WORKBOOK-AUDIT/SKILL.md) reads the same file
  for the opposite audience. It assesses the workbook for whoever maintains it, so
  the leftovers and the risks are its findings; a FAQ is written for whoever reads
  the dashboard, and everything the dashboard does not show is noise in it.
- [dbt-model-descriptions](../DBT-MODEL-DESCRIPTIONS/SKILL.md) documents warehouse
  columns for the people who query them. A dashboard FAQ documents what a report
  shows to people who will never see the warehouse, and the two can disagree: a
  dashboard often filters, renames or re-aggregates a column it inherits.
- [kpi-definition-building](../KPI-DEFINITION-BUILDING/SKILL.md) is where a metric
  goes when this work finds it has no definition anywhere. Writing one is a
  different job with a different owner, and it is not something to do inside a
  FAQ.
- [project-documentation](../PROJECT-DOCUMENTATION/SKILL.md) records architecture
  and the decisions behind it. This is one report's user-facing documentation, not
  a record of why the reporting layer is shaped the way it is.

## Two inputs, and the second one is not optional

Ask for the workbook (`.twb`, or `.twbx` if extracts are packaged with it) **and a
screenshot of the view a user lands on**. Both, before starting.

The workbook file is the authority on the model: data sources and connections,
fields and calculations, filters, parameters, which worksheet sits in which
dashboard. It is not an authority on what anyone sees. Dashboard zones carry
coordinates, so a layout can be reconstructed from them in principle; in practice
it is a nested tree of containers with nothing to say about what renders inside
them, and the things a FAQ reader needs — which view opens first, which controls
are visible without scrolling, what a chart is actually showing — are not
recoverable from it.

Without the screenshot the "how to use it" section gets written from the field
list, which produces confident instructions for a dashboard that does not exist.
That failure is quiet: the text reads fine, and only someone with the dashboard
open notices that the filter described as a tab-wide control is a single
worksheet's quick filter.

When the dashboard has several tabs worth documenting, ask for a screenshot of
each. One screenshot documents one view honestly; it does not generalise to the
others.

## Metric definitions come from the workbook or they do not come at all

This is the part that makes the FAQ worth having, and the part most likely to be
faked.

A workbook that is maintained for its readers usually already holds its
definitions, in a calculated field whose only job is to feed tooltips: a `CASE`
over the metric name returning the definition text. That field is the source.
Read it, and carry each definition across as written.

Finding it is a heuristic, not a lookup. The field is conventionally captioned
something like `Hover Definitions`, `Tooltip`, `Tool Tip` or `Metric
Definitions`, and a project that names it anything else will not match. **A failed
search means ask, not conclude.** "I did not find a definitions field under the
usual names — what is it called here?" is one question, and the alternative is
declaring a maintained workbook undocumented.

**When there is genuinely no definitions field, stop and say so.** Do not fall back
on listing every visible field caption. A caption list is names without meanings,
and it fails in the worst available way: it looks like a finished FAQ, it makes a
documentation checklist go green, and a reader cannot see that the definitions are
missing rather than terse. What to hand back instead is the inventory you can
source — the metrics the dashboard shows, its data sources, its filters and
parameters — plus the list of metrics waiting on a definition from the owner. That
is a smaller deliverable and an honest one, and it is the input the owner needs to
fix the workbook, which is the real fix.

## What the dashboard uses, not what the file contains

A workbook accumulates. Fields survive the worksheets that used them, data sources
stay connected after the sheet they fed was deleted, and calculations exist in
three variants of which one is wired up. All of it is in the file, and none of the
leftovers belong in a user-facing FAQ.

So the field list has to be narrowed to what the dashboard's own worksheets
reference, and narrowed again to what the reader can see: use the user-facing
caption rather than the internal field name, and leave out fields marked hidden.
Those leftovers are findings for
[tableau-workbook-audit](../TABLEAU-WORKBOOK-AUDIT/SKILL.md), where "unused" is
the interesting part. In a FAQ they are noise that costs the document
its credibility — a reader who finds one metric that is not on the dashboard stops
trusting the other twenty.

## Facts the file does not have, which have to be asked

**Refresh frequency, always.** A workbook tells you an extract exists and when it
was last refreshed. The schedule lives somewhere else — on the server, in Tableau
Cloud, or in whatever upstream job loads the table a live connection points at —
and a live connection has no refresh frequency of its own at all; it inherits the
upstream pipeline's. Guessing here is the most damaging single sentence the FAQ can
contain, because the refresh line is what a reader consults before deciding
whether today's number is in. Ask, and if nobody knows, write down that it is
unknown rather than a plausible "daily".

**Purpose.** Workbook titles and captions name things; they do not say what
decision the dashboard exists to support. That comes from the owner, from the
requirements it was built against, or from the request that prompted the FAQ.
Invented purpose is the most convincing wrong content in the whole document.

**Audience and ownership**, if the FAQ is meant to tell a reader who to go to.
Neither is in the file.

## What the FAQ has to contain

Five things, whatever shape the project puts them in:

- the metrics the dashboard shows, with their definitions
- what the dashboard is for — the question it answers
- how to use it: the filters, parameters and drill paths, and what the defaults are
- where the data comes from
- how often it refreshes

The format is the project's. Projects keep report documentation in a wiki, in a
repository, in the dashboard itself as a text zone, or in a document attached to
the report; match whichever one it already uses, because a FAQ in a format nobody
else uses is a FAQ nobody updates. Do not import a layout from elsewhere, and do
not spend the effort on styling that belongs on sourcing the content.

## The result is a draft, and should be labelled one

Definitions carried over from a workbook are exactly as true as the workbook. A
tooltip written two years ago, against a calculation that has since changed, is
still a well-formed sentence; copied into the FAQ it acquires the authority of
fresh documentation. There is nothing in the file that can tell you which
definitions are stale.

Which means the FAQ goes to the dashboard owner for review before it goes to
readers, and it is more useful if it says where each definition came from — the
workbook's definitions field, an answer from the owner, or an outstanding gap.
That turns the review from "read all of this" into "check these four", which is
the difference between a review that happens and one that does not.

Treat the FAQ as part of the dashboard from then on. It describes field names,
filters and sources that change when the workbook changes, so it decays the same
way, and nothing will flag it. Documentation that is wrong and trusted is worse
than documentation that is missing.

One last thing worth being deliberate about: the finished FAQ reproduces the
project's metric names, table names and source systems in one tidy document. It is
project documentation and belongs wherever the project keeps that, under the same
handling rules as the workbook it came from.
