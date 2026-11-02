---
name: dashboard-concept-draft
description: Drafting the pages, chart types, metrics and KPIs a dataset can support, each one named with its source fields, its grain and any quality caveat. Use when an analyst wants a build list grounded in a dataset they already have, before any report file exists.
---

# Drafting a dashboard from a dataset

This is a backlog someone could build from: pages, chart types, metrics,
KPIs. It is not a wireframe, not a Power BI file, and not a Tableau
workbook. The build has not started. The draft says what to build and what
was considered and dropped, so the next pass does not propose the same
visual again.

Its neighbours:

- [requirements-brainstorming](../REQUIREMENTS-BRAINSTORMING/SKILL.md) works
  out a vague software request before any code. This skill starts from a
  dataset and ends in pages and measures. A request that has no dataset
  yet belongs there. This skill starts once a dataset is in hand.
- [power-bi-report-faq](../POWER-BI-REPORT-FAQ/SKILL.md) documents a report
  that already exists, and it takes each metric from the measure description
  rather than from memory. This skill drafts a report that does not exist
  yet. It does not invent a metric definition the model or the user did not
  supply. Where a published model has a measure description, that description
  wins over a column name. A column named revenue is not a definition of
  revenue.

## What you consume

The EDA report and the quality assessment. Every proposed metric names its
source fields, its grain, and any quality caveat those fields carry. A
column the assessment marked unsafe is either dropped or proposed with the
caveat in the same line. A caveat parked in an appendix is how an unsafe
column becomes a KPI: the page lists the number, and the warning sits where
nobody building the visual will read it.

If either document does not exist, run it first or mark the proposals that
depend on it as insufficient evidence. Do not profile the dataset again
inside the draft. The rates live in the assessment. The grain, the units and
the questions live in the EDA report.

Inherit the source block unchanged. The class rules live once, in
[references/sources.md](../DATASET-QUALITY-ASSESSMENT/references/sources.md).
A visual at a grain the source class cannot support is wrong even if the
chart type is sensible. A flat file has no declared relationship to hang a
cross-table visual on. A blend is not a join to draw as one row. A measure
and the column of the same name are not interchangeable. If that file is not
available, say the source class was not classified, and do not propose a
visual whose grain depends on a class you did not establish.

## Audience, and the one assumption

Name the audience, the decision the dashboard serves, and what is out of
scope. Mark assumptions.

If the audience or the decision is unknown, write one assumption and keep
the list short enough to revise, rather than producing a full product. A
full page list for a decision you invented is a product nobody asked for.
Revising it costs more than writing the short list again once someone states
the decision. One assumption, stated, is a draft. A long page list built on
personas nobody named is a guess.

## Pages

For each page: the question it answers, the chart type and why that type
fits the grain, the fields, the filters, and the grain of the visual.

The chart type has to fit the grain, not the other way round. A line needs
an order, usually time, at that visual's grain. Without it the line invents
a sequence from whatever order the rows happened to arrive in. A bar
compares categories at one grain. A scatter needs two measures at the same
grain. A table is the honest visual when the question is which entities, at
the grain of the row.

A single visual that mixes grains is a finding, not a proposal. A line of
monthly revenue beside a count of customers at another grain reads as one
picture and is two. The reader cannot see the join, and neither can the
person who builds it from a draft that drew them on one page as if they
shared a row.

State each metric in business language plus grain. Do not write DAX or a
level-of-detail expression unless the user asks. The expression is an
implementation of a definition, and this skill stops at the definition. An
expression written early becomes the definition, and the business sentence
is then whatever the expression happens to compute.

## A KPI is not a breakdown

A KPI is one number with a comparison: against a previous period, a target,
or another segment, at one grain. A breakdown chart is that number split.
They fail for different reasons. The KPI fails when the comparison has no
baseline or no target. The breakdown fails when the split fan-outs or when
the segment is the one the assessment said was empty. Keep them apart so the
caveat can name which one it is about.

Direction of good belongs on the KPI. Without it, a movement has no
meaning, and the unit from the EDA report is what makes the direction
decidable. If the unit was never named, the direction is an assumption.
Mark it.

## Ideas considered and dropped

Each dropped idea carries the reason: no time column, a null rate, fan-out,
grain unknown, a column marked unsafe, a question the EDA report said the
dataset cannot support. The section exists so the same idea is not proposed
again on the next pass, and so a reader can see the refusal was about the
data rather than about taste.

If nothing was dropped, say what you considered beyond the proposals. An
empty section reads as a search that did not happen.

## Before building

Say what you would need before anyone builds: a grain confirmation when the
grain was assumed, a business definition the model and the user did not
supply, access you did not have. This is the assessment's insufficient
evidence, carried forward. Do not fill it by writing the definition yourself.

```markdown
## Dashboard draft: <object>

### Source
<the assessment's block, unchanged>
EDA: <where it is, or "not written; proposals that need it are insufficient evidence">

### Audience
- Who:
- Decision this serves:
- Out of scope:
- Assumptions:

### Pages
| Page | Question | Chart type, and why it fits the grain | Fields | Filters | Grain of the visual |
|------|----------|----------------------------------------|--------|---------|----------------------|

### Metrics and KPIs
| Name | KPI or breakdown | Plain-language formula | Grain | Source fields | Direction of good | Quality caveat, or dropped |
|------|------------------|------------------------|-------|---------------|-------------------|----------------------------|

### Considered and dropped
| Idea | Reason |
|------|--------|

### Before building
- <grain confirmation, business definition, or access you did not have>
```
