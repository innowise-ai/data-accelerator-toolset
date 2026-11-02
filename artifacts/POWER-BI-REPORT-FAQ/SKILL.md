---
name: power-bi-report-faq
description: Writing a report FAQ from a Power BI Project folder and a screenshot of the landing page, taking each metric definition from the measure description rather than from the formula. Use when an existing Power BI report needs documentation its readers can rely on.
---

# Writing a report FAQ

A report FAQ answers the questions its readers ask in chat: what this number
means, what the report is for, how to drive it, where the data comes from, and
how old it is. Those answers are already scattered across the project, the
service, and the person who owns the report. The work is collecting them
without inventing the parts that are missing. A report FAQ is unusually easy
to invent, because a plausible sentence for "active customer" reads exactly
like a real one, and a reader has no way to tell them apart.

So the discipline is sourcing. Every line in the FAQ should be traceable to
the project, to the screenshot, or to an answer someone gave. Nothing else
goes in.

Where each fact lives in the project, and which facts the files do not hold,
is in [references/project-files.md](references/project-files.md).

Its neighbours in this catalog:

- [dbt-model-descriptions](../DBT-MODEL-DESCRIPTIONS/SKILL.md) writes warehouse
  column text for people who query the tables. A report FAQ writes what a
  report shows to people who will never see the warehouse. The two can
  disagree: a measure often filters, renames, or re-aggregates a column it
  inherits, and the column's description does not become the metric's.
- [project-documentation](../PROJECT-DOCUMENTATION/SKILL.md) records
  architecture and the decisions behind it. This is one report's
  reader-facing documentation, not a record of why the reporting layer is
  shaped the way it is.
- [sensitive-data-handling](../SENSITIVE-DATA-HANDLING/SKILL.md) decides what
  personal data a model may carry. The FAQ repeats metric names, source
  systems, and definitions in one document, so it belongs wherever the
  project keeps the report, under the same handling. Deciding whether a
  column should be in the model at all is that skill's question.
- [power-bi-measure-translation](../POWER-BI-MEASURE-TRANSLATION/SKILL.md)
  rewrites a metric between SQL and DAX. When a description and a formula
  disagree, that skill does not pick a third definition. The description
  remains the meaning.
- [power-bi-copilot-readiness](../POWER-BI-COPILOT-READINESS/SKILL.md) decides
  what a question engine may bind to. The description written here is the
  description it will lean on. A second definition kept for Copilot will
  drift from this one.
- [power-bi-model-audit](../POWER-BI-MODEL-AUDIT/SKILL.md) reads the same
  folder for the opposite audience. It assesses the model for whoever
  maintains it, so the leftovers and the risks are its findings. A FAQ is
  written for whoever reads the report, and everything the report does not
  show is noise in it.

## Two inputs, and the second one is not optional

Ask for the Power BI Project folder and a screenshot of the page a reader
lands on. Both, before starting.

The project is a folder of plain text: a report part and a semantic-model
part. It is the authority on tables, measures, relationships, filters, and
visuals. It is not an authority on what anyone sees. The files can name an
active page and can mark a page as a tooltip or a drillthrough, and that is
still not a picture of the landing view, of which slicers are visible without
scrolling, or of anything that appears only after a bookmark or on a tooltip
page. Without the screenshot, "how to use it" gets written from the field
list, which produces confident instructions for a report that does not exist.

When bookmarks or tooltip pages are in the project, one shot of the default
page is not the whole view. Ask for a screenshot of each state a reader can
actually reach. A tooltip page that only appears on hover is part of what the
report shows, and the landing screenshot will miss it.

A `.pbix` is a package. Measure descriptions, relationships, Power Query, and
roles are not honestly readable from it. Say that and stop. Do not invent an
export into model text.

If the report points at a semantic model that is not in this folder, the
definitions are not here either. Ask for that model's project. Do not fill
the gap from visual titles.

## The definition is the measure description

This is the part that makes the FAQ worth having, and the part most likely to
be faked.

The business definition of a metric is the description on its measure. The
DAX formula is the formula. It says how the number is computed, in a language
the FAQ's reader does not speak and that does not state the business rule the
formula was written to follow. A format string says how the number is drawn.
A display folder says where the field list files it. None of those is the
definition.

Read the description and carry it across as written. If it is missing, stop
on that metric. Do not translate the formula into business English, and do
not dump every visual title in its place. A title list looks like a finished
FAQ, makes a documentation checklist go green, and leaves a reader unable to
tell that the definitions are absent rather than terse. Hand back the
inventory you can source — the metrics the page shows, the sources, the
filters — and the list of metrics waiting on a definition from the owner.
That is a smaller deliverable and an honest one.

A description and a formula are edited separately. The description can
describe a calculation that has since changed, and the file looks
well-formed either way. Copied into the FAQ, a stale sentence acquires the
authority of fresh documentation. There is nothing in the formula that
certifies the description.

Text an agent wrote is a draft. A description counts only when someone has
accepted it, or it was already in the model when you opened the project. A
description this session just added, or a bulk rewrite nobody has accepted,
is not a source. Treat it as a gap and say so.

## What the reader sees, not what the model contains

A model accumulates. Columns survive the visuals that used them, and a column
that is absent from the page can still feed a measure, a relationship, or
another report on a shared model. "Unused" is not this skill's question. The
FAQ documents the metrics the reader can see, under the names the screenshot
shows, and leaves the rest out. A reader who finds one metric that is not on
the report stops trusting the others.

When a visual title and the measure name disagree, use the name the reader
sees and keep the measure's description. Note the mismatch. Do not invent a
reconciliation.

A calculation item selected on the page (a year-to-date variant, a prior-year
variant) changes which number the reader is looking at. If the screenshot
shows that control, "how to use" has to say so. The item's own text is not a
business definition of the measure. If the item has no description you can
quote, mark that variant as a gap rather than explaining the formula.

## Facts the project does not have, which have to be asked

**Refresh frequency, always.** The model can say whether a table is imported
or queried live. The schedule lives in the service, and a live connection has
no refresh of its own; it is as current as the warehouse behind it. A
composite model is both, on different tables. Guessing here is the most
damaging sentence the FAQ can contain, because the refresh line is what a
reader checks before trusting today's number. Ask. If nobody knows, write
that it is unknown rather than a plausible "daily".

**Purpose.** Page names and visual titles name things. They do not say which
decision the report exists to support. That comes from the owner, from the
request that prompted the FAQ, or from requirements you were given. Invented
purpose is the most convincing wrong content in the document.

**Audience and ownership**, when the FAQ is meant to say who to go to.
Neither is in the project.

## What the FAQ has to contain

Five things, in whatever shape the project already uses:

- the metrics the report shows, with their definitions
- what the report is for
- how to use it: the slicers and other controls a reader can see, what the
  defaults are, and what a bookmark or a tooltip page adds
- where the data comes from, named at the level a reader needs, without
  connection strings or credentials
- how often it refreshes

The format is the project's. Projects keep report documentation in a wiki, in
a repository, on a page of the report, or in a document attached to it. Match
that. A FAQ in a format nobody else uses is a FAQ nobody updates. Do not ship
a layout of your own.

## The result is a draft until the owner accepts it

Label where each definition came from: a measure description already in the
model, an answer from the owner, or an outstanding gap. That turns the review
from "read all of this" into "check these", which is the difference between a
review that happens and one that does not.

The FAQ describes measure names, filters, and sources that change when the
project changes. A commit of the project folder can show which measure or
visual moved; the FAQ will not update itself, and nothing will flag it.
Documentation that is wrong and trusted is worse than documentation that is
missing.
