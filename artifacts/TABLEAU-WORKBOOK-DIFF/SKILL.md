---
name: tableau-workbook-diff
description: Comparing two versions of a Tableau workbook - why a text diff of the file is close to useless, which differences can change the numbers, which are cosmetic, and what a comparison still cannot prove. Use when reviewing a change to a workbook or working out what differs between two versions of one. Not for assessing a single workbook on its own.
---

# Comparing two workbook versions

Workbooks arrive as "here is the old one and the new one, what changed". The
answer that matters is not the list of differences — it is which of them can move
    10|a number, and a reviewer cannot get that from the difference list alone, because
the two classes look identical in the file.

Two properties of workbooks make this harder than reviewing code, and both have to
be worked around rather than lived with:

**A text diff of the file is close to useless.** Tableau rewrites the whole
document on save. Element order shifts, generated identifiers change, internal
state and the version the file was saved with update, and the packaged thumbnail
is new. Save a workbook twice with no edits at all and the two files still differ
    20|substantially. So a diff tool will report hundreds of changed lines with the three
that matter somewhere inside, which is worse than no diff: it looks like evidence.

**A difference in the file is not a difference in the output.** A renamed field
changes nothing. A filter that gained one member changes everything downstream of
it. Nothing in the file marks which is which, and the ranking is the whole value
of this work.

Its neighbours in this catalog:

- [code-change-review](../CODE-CHANGE-REVIEW/SKILL.md) is the general version, and
    30|  it assumes a readable diff. Everything here exists because this artifact does
  not have one.
- [tableau-workbook-audit](../TABLEAU-WORKBOOK-AUDIT/SKILL.md) assesses one
  workbook as it stands. This compares two, and reuses the audit's inventory as
  the thing being compared.
- [tableau-performance-diagnosis](../TABLEAU-PERFORMANCE-DIAGNOSIS/SKILL.md) is
  where "it got slower after this change" goes once the change is identified.

The file mechanics the comparison needs, and the noise it has to discard, are in
[references/workbook-xml.md](references/workbook-xml.md).

    40|## Compare inventories, not files

Build the same inventory from each version — data sources and connections,
calculated fields and their formulas, parameters and their domains, filters and
their scope, worksheets, dashboards and their tabs — then compare the inventories
by name.

This is more work than running a diff and it is the only approach that produces a
reviewable answer. It also drops the noise automatically: generated identifiers,
element order and save metadata are not in the inventory, so they cannot appear in
the result.

    50|One handling note: match by caption where you report, and by internal name where
you compare. A field whose caption changed and whose formula did not is a rename;
if you match on caption it looks like one field deleted and another added, which
is the most common false finding in a workbook comparison.

For packaged workbooks, compare the `.twb` inside and ignore the rest of the
package. Two `.twbx` files with identical logic differ in their extracts, and
their extracts are not the change under review — which cuts the other way too,
and is worth saying out loud to whoever asked: if the extract data changed, the
numbers changed with no difference in the workbook at all.

    60|## Sort the differences into three classes

Report them separately and in this order. A reviewer reads the first class
carefully and skims the rest, which is the correct allocation of their attention
and only works if the classes are honest.

### Can change the numbers

- **A calculated field's formula.** Including a change that looks like a tidy-up.
- **Filter membership or scope.** Members added or removed, a filter moved from
  one sheet to all sheets using the source, an exclude turned into an include.
    70|- **A context filter added or removed.** This is the subtle one. Context changes
  what fixed level-of-detail expressions see, so adding a context filter can move
  every number produced by an LOD elsewhere in the workbook, on sheets the change
  never touched.
- **A data source filter or extract filter.** Applies before everything else, so
  its effect is total and easy to miss.
- **The aggregation a field is used with**, on any shelf. Same field, different
  number.
- **The join or relationship structure**, including a join type change. An inner
  becoming a left join changes row counts, and a new join at a different grain
    80|  changes every measure over it.
- **A parameter's default value or allowed set.** The default is what a new viewer
  sees, so this changes the numbers the dashboard shows without changing any
  formula.
- **The sort on a sheet carrying a table calculation.** Table calculations are
  computed along the ordering of the result, so a sort change is a logic change
  there, while being invisibly cosmetic anywhere else.
- **A change from extract to live or back.** Different data as of different
  moments, and different behaviour for anything that was relying on one of them.
- **A field's data type or default aggregation.**
    90|
### Cosmetic to the numbers, but not free

Worth a separate section rather than being dismissed, because each of these has a
cost that is not about correctness:

- **Captions and labels.** Nothing computes differently; every piece of
  documentation that named the old caption is now wrong, including any FAQ written
  from the workbook.
- **Tooltip and title text.** Same, and worse if the tooltip is where the project
  keeps its metric definitions — then a tooltip edit is a definition change that
   100|  no reviewer will class as one.
- **Colours, fonts, formatting, number formats.** Number formatting deserves a
  glance: rounding displayed values is cosmetic, and it changes what a reader
  believes the number is.
- **Zone geometry and layout.** Cheap to change, expensive to review, and the
  place where a screenshot comparison beats reading the file.
- **Worksheet or tab order.** Changes what a user lands on.

### Context for everything else

- **The Tableau version the workbook was saved with.** If it moved, the change set
   110|includes whatever that upgrade did by default, and the comparison is no longer
  only about the author's edits. Report it first; it changes how much the rest can
  be trusted.
- **New fields, sheets or data sources that nothing references.** No effect today.
  Say so, and say they are there.

## What the comparison cannot prove

It cannot tell you the numbers changed. It identifies where they could have, which
is a different and much weaker claim, and the gap between the two is where a
review of this kind usually overreaches.

   120|The proof is running both versions and comparing output at the same filter and
parameter state: the same views, the same slices, and at a lower grain as well as
the headline figure, because an aggregate hides two errors that cancel. When that
comparison is not possible, say that the finding is a candidate and name the
comparison that would settle it.

Be careful with formulas specifically. Reading a changed level-of-detail
expression or table calculation and concluding it is equivalent to the old one is
the single most error-prone judgement in this task — the meaning depends on the
sheet's grain, its filters and its sort, none of which are in the formula. "This
   130|rewrite looks equivalent" is a hypothesis. Two formulas that produce the same
number on the sheet you checked can differ on a sheet you did not, and the only
honest version of that finding says which sheets were compared.

## What the review should hand back

A comparison is finished when a reviewer can act on it without redoing it:

- the changes that can move numbers, each with the sheets or dashboards affected
- the cosmetic changes, as a list, without commentary
- the save-version change, if there was one
- the comparison you ran, or the one you could not run and why
   140|- what you could not classify, by name

That last line matters. A workbook comparison always has residue — a difference
whose effect depends on data you do not have, or a formula you are not sure you
read correctly. Listing it is useful. Silently sorting it into "cosmetic" because
the report wanted two tidy classes is how a result-altering change ships.
