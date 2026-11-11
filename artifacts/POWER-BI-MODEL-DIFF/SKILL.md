---
name: power-bi-model-diff
description: Comparing two versions of a Power BI Project — which changes can move a number, which are format strings or descriptions, and which are cosmetic — and why a line diff of the files is not the review. Use when reviewing a change to a semantic model or a report, or working out what differs between two versions of a project.
---

# Comparing two project versions

Two folders arrive as "here is the old one and the new one, what changed".
The answer that matters is not the list of differences. It is which of them
can move a number, which change what a reader sees without changing the
value, which can make the documentation lie, and which cannot do any of
those. The classes look identical in a line diff, which is why the
classification is the review.

[code-change-review](../CODE-CHANGE-REVIEW/SKILL.md) is the general version
of a review, and it assumes a readable source diff. A Power BI Project is
the exception: the files are text, and a line diff of them is still not
something a reviewer can read. Everything here exists because of that.

Its other neighbours:

- [power-bi-model-audit](../POWER-BI-MODEL-AUDIT/SKILL.md) assesses one
  version, with no change on the table. This compares two, and reuses that
  inventory as the thing being compared.
- [power-bi-function-impact](../POWER-BI-FUNCTION-IMPACT/SKILL.md) is the
  proof a function-body change asks for: each caller still matches the
  calculation it replaced. This skill classifies the edit and stops when the
  caller set is unknown. It does not run that proof.
- [power-bi-report-faq](../POWER-BI-REPORT-FAQ/SKILL.md) is what a description
  change puts at risk. The FAQ repeats the measure description. A description
  can be rewritten while the formula stays, and the FAQ then lies with the
  formula untouched.
- [power-bi-performance-diagnosis](../POWER-BI-PERFORMANCE-DIAGNOSIS/SKILL.md)
  is where "it got slower after this change" goes once the change is
  identified. This skill does not time anything.

What to compare, and what to discard before classifying, is in
[references/what-to-compare.md](references/what-to-compare.md).

## Compare the two folders, not a package

Both inputs are Power BI Project folders. A text diff of a `.pbix` is
useless: the package is not the measures, the relationships, the Power
Query, or the roles. Say that and stop. Do not invent an export in order to
obtain a diff.

A line diff of the TMDL and the report JSON is also not the review. It is
noisy. Identifiers, annotations, and visual layout move when nothing a
reader would call a change has happened, and the three lines that matter sit
inside hundreds that do not. The review is the classification below. Build
the same inventory from each version and compare the inventories.

Match an object that was renamed to its previous self, instead of reporting
a deletion and an addition. A lineage tag that is stable across the two
versions is the match. When the tag moved as well, you cannot tell a rename
from a replacement. Say so, and do not guess.

Text an agent wrote is a draft. A bulk rename, a bulk format-string edit, or
a bulk description rewrite is classified by the classes below, one class per
kind of edit. A generated formula is unverified until it is checked. Do not
treat "the agent applied it" as a review.

## Sort the differences, and keep the classes apart

Report them separately and in this order. A reviewer reads the first class
carefully and skims the rest, which is the right use of their attention and
only works if the classes are honest.

A difference is a candidate. Classification says the change can move a
number, or can change what the reader sees, or can make the FAQ lie. It does
not by itself prove the published number moved. Name the comparison that
would settle it: the same filters, the same grain, the old version against
the new.

### Can change the number

- **A measure's formula.** Including a tidy-up. Whitespace that does not
  change the expression is not this class; an expression that changed is.
- **A user-defined function's body.** Result-altering for every caller,
  including callers on reports that are not in this folder. List the callers
  you can see. If the caller set is unknown — because other reports share the
  model, or because you cannot find the call sites — say so and stop. Do not
  call the change safe, and do not guess at callers you cannot see.
- **A relationship.** Active or inactive, direction, cardinality, or the
  columns it joins. A filter then reaches a different set of rows.
- **A calculated column's expression.** The value is fixed at refresh, so
  this changes stored data, not only a visual.
- **Power Query** that changes which rows come back, the grain, or a type.
  A rename of a step that leaves the expression the same is not this class.
- **A role's filter.** Who sees which rows. A role that gained or lost a
  table permission changes the audience of every number on the tables it
  reaches.
- **A calculation item's expression**, or which group wins when more than
  one can apply. The item wraps every measure a reader can select it on.
- **A report filter or a page filter.** Members added or removed, a filter
  moved from one page to the report, an exclude turned into an include. The
  default state of the report is what a new reader sees.

### Format string

Its own class, not a formula change and not cosmetic. `formatString` decides
how the value is drawn. The stored number can be unchanged and look like a
different number: a percent against a decimal, a different scale, a date
drawn in another form. Review it on its own, and do not let it hide inside a
formula diff or get dismissed with the colours.

### Description

Its own class. The `///` text on a measure can be rewritten while the formula
stays put. The FAQ will repeat the new sentence. The number did not change,
and the documentation of the number may now be false. A description an agent
wrote counts only when someone accepts it or it was already in the model.
Until then it is a draft in this class, not an accepted definition.

### Cosmetic

- Position, size, colour, and theme.
- A display-folder rename, when nothing selects by that folder. If a measure,
  a calculation, or a visual selects by the folder name, the rename is in
  the first class. Look before filing it here.
- A rename of a measure or column whose expression did not change, once you
  have matched it to its previous self. Say what still points at the old
  name. A visual title that was not updated is a label change, and it belongs
  here only if the query behind the visual still resolves.

Identifiers, annotation noise, and visual-layout coordinates do not appear
in any of these classes. Leaving them out is the point of comparing
inventories.

## What the comparison still cannot prove

That the published report shows the new number. The folders can differ while
the service still runs the previous refresh. That a function change is safe
for a report you do not have. That a format string which looks harmless is
harmless to a reader who compares this month's screenshot with last month's.
State the limit next to the class it belongs to, rather than adding a
conclusion the files do not support.

## Anti-patterns

- Treating a line diff of the TMDL as the review. Identifiers, annotations,
  and layout move when nothing a reader would call a change has happened,
  and the three lines that matter sit inside hundreds that do not.
- Diffing a `.pbix`. The package is not the measures, the relationships,
  the Power Query, or the roles, and converting it is not this task.
- Filing a format-string or description change as cosmetic. The format
  string changes what the reader sees without changing the value; the
  description can make the FAQ lie while the formula stays put.
- Calling a function-body change safe when callers outside this folder are
  unknown. Other reports that share the model are invisible here, and a
  function that is right for this report can be wrong for one you cannot
  see.
