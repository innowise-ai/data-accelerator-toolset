# What to compare

Written for the review in [`../SKILL.md`](../SKILL.md). Both sides are
Power BI Project folders. If either side is only a `.pbix`, stop. The
package does not yield the lists below, and converting it is not this task.

Read the model as TMDL under the semantic-model `definition/` directory, or
as TMSL JSON in `model.bim` when the project was saved that way; both hold
the same objects. If neither is there, say the text is not there and stop.
Do not convert either format into the other. Ignore the `.pbi` cache.

## Build the same inventory twice

From each version, take:

| Object | What you compare |
|---|---|
| Measure | name, formula, `formatString`, `displayFolder`, the `///` description, and the lineage tag used only to match the object to itself |
| User-defined function | the body you can quote from `functions.tmdl`, and every expression in this folder that invokes the name |
| Relationship | the columns it joins, cardinality, direction, whether it is active, and whether a security filter is carried one way or both |
| Calculated column | the expression |
| Power Query | the M on each partition and in shared expressions, judged by the rows, grain, and types it produces, not by step names |
| Role | each table permission's expression |
| Calculation item | the item's expression, and the group's precedence |
| Report and page filters | which fields, which members, which pages, include or exclude |

Visual position, size, colour, and theme are recorded only so they can be
filed as cosmetic. They are not part of the number.

## What a line diff will shout about, and why it is not the review

A save rewrites identifiers, annotation blocks, and the coordinates of
visuals. Two versions with the same measures can still differ in hundreds of
lines. Those lines are not changes of any class in the review. Drop them by
comparing the inventory, so they never enter the result.

A lineage tag is for matching an object across the two versions. It is not
itself a finding. An annotation is not a formula, a format string, or a
description. If the only difference on a measure is an annotation, it does
not belong in the result unless the owner has said that annotation is load-
bearing.

## A function whose callers you cannot see

Search this folder for invocations. A description that mentions the name is
not a caller. If `functions.tmdl` changed and you cannot list every caller —
including because another report uses this model and is not in the folder —
the body change is result-altering for an unknown set. Stop. Do not fill the
gap with a reconstructed signature, and do not describe the function from
memory when the file does not contain one you can quote.

## Agent edits

A bulk edit that renames display folders, rewrites format strings, or
rewrites descriptions touches many measures in one step. Classify each class
separately, even when one edit produced all three. A folder rename is
cosmetic unless something selects by the folder. A format string stays in
its own class. A description stays in its own class. A formula the edit also
rewrote is the first class, and it is unverified until it is checked.
