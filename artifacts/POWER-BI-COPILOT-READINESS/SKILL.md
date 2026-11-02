---
name: power-bi-copilot-readiness
description: Deciding whether a semantic model is safe for Power BI Copilot to answer from, and checking that an answer or a drafted measure used the measure that was meant. Use when a published or project semantic model should answer questions in Copilot, or a Copilot answer or a Copilot-written measure needs to be checked against the metric you meant.
---

# Preparing a model for Copilot

Copilot here is Power BI Copilot over a semantic model: questions asked of
the model, and DAX it drafts. The same readiness rules apply wherever that
model is what Copilot sees. This is not GitHub Copilot, and it is not a
wrapper around the product. The skill decides what the question engine is
allowed to bind to, and whether an answer used that binding. It does not
drive the service, and it does not click its way to a setting.

A question is bound to whatever field shares the words in the question. A
measure and a column can share a business word. The column will be summed.
If the column is a key, a rate, or a total that was already aggregated, the
sum is a confident wrong number, and the prose around it can still sound
like the metric. Hiding the column when the measure is the metric is what
makes the measure the thing that gets chosen.

Its neighbours in this catalog:

- [power-bi-report-faq](../POWER-BI-REPORT-FAQ/SKILL.md) writes what a human
  reader can rely on, sourced from the project and the screenshot. This
  skill decides what the question engine is allowed to bind to. A description
  written for the FAQ is the description Copilot will lean on. Do not
  maintain a second definition.
- [power-bi-model-audit](../POWER-BI-MODEL-AUDIT/SKILL.md) inventories a
  model for someone about to change it. This skill uses that kind of
  inventory only to decide which fields should be askable.
- [power-bi-measure-translation](../POWER-BI-MEASURE-TRANSLATION/SKILL.md)
  checks that a drafted measure returns the SQL number. This skill decides
  whether the model should have been asked, and whether the answer used the
  measure you intended.

## What an answer can bind to

Each of these changes the number. None of them is a naming preference.

**A column sitting next to the measure.** The measure is the metric. The
column is a sum waiting to happen. Hide the column when the measure replaces
it. Leaving both visible means a question that says the measure’s name can
still be answered by summing the column, and the two answers will not match.

**The description.** It is the definition the answer will repeat. It has to
state the grain, the filters, the unit, and what the metric is not. A
description copied from a warehouse column is wrong when the measure filters
or re-aggregates that column: Copilot will repeat the column’s meaning for a
number that is no longer that column. The FAQ’s description is this
description. A second sentence kept somewhere else for "the AI" will drift,
and the answer will quote the one on the measure.

**Ambiguous names.** Sales, Amount, Count, and Value occur on more than one
table in almost every model that has grown for a while. The question does
not know which table was meant. Rename or describe the field before it is
visible. A synonym belongs to a business word people actually type, and it
points at one field. A synonym that points at two fields is an invitation to
pick the wrong one.

**Which date "last month" uses.** The date table has to be the date table,
and the relationship has to be the date the question means. Order date and
ship date both answer "sales last month", and they are different numbers.
If both relationships exist, say which one a question in those words will
follow, and treat the other as a different metric that needs its own name.

**A relationship that filters both ways.** Filter context then crosses into
a table the question did not name. A question about one dimension can change
the rows of another table the author did not intend to filter. Record that
relationship as a risk to the answer, not as a style comment. The number is
different because the population is different.

**The role.** Row-level security is part of the answer the user sees. A
check run as a role that sees everything is a different population from the
answer a salesperson gets. Say which role the check used. A verified
question that does not name its role is verified for someone else.

## Preparing the model

Preparing the model is editing what is visible and what is described. One
measure per business concept. Columns hidden when a measure replaces them.
Descriptions and synonyms written from the definition you can source, not
from a paraphrase of the formula and not from a description an agent wrote
and nobody accepted. The date table identified. A short set of verified
questions.

Each verified question names the measure, the filters, and the grain. The
answer is a number you computed at that grain under those filters. Do not
invent a verified answer you did not compute. A question without a number
next to it is a candidate, not a verified question.

If you cannot see the model, stop and ask for the measure list, the
descriptions, which columns are hidden, the relationships, and the date
table. A report screenshot does not carry those. Do not invent them from
the page.

## Checking an answer or a drafted measure

Restate which measure was used and which filters were applied. If you cannot
tell, the answer is unchecked. An answer that summed a column the measure
was meant to replace has failed, even when the sentence around the number
sounds right. The prose is not the check. The binding is.

A measure Copilot drafted is not checked here by rewriting it again in
looser words. Hand that DAX to
[power-bi-measure-translation](../POWER-BI-MEASURE-TRANSLATION/SKILL.md).
The equivalence check against the SQL metric lives there. Until that check
has been run, the drafted measure is unchecked. This skill’s job is to say
whether the model should have been asked, and whether the answer used the
measure you intended.

## What to hand back

- What Copilot can currently bind to: the visible measures, the visible
  columns that share their words, the dates, and the relationships that
  filter both ways.
- What should be hidden or renamed, and why that field would change the
  number if it stayed askable.
- Descriptions and synonyms that are missing, against the definition you can
  source. A missing description is a gap, not a sentence you invent.
- Verified questions you could actually check, each with its measure, its
  filters, its grain, and its role.
- Any answer or drafted measure under review: the measure it used, the
  filters, and whether that number was checked. Unchecked stays unchecked.
