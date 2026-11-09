---
name: power-bi-model-audit
description: Assessing an inherited Power BI semantic model and the report on it from the project folder — the inventory worth taking, which dependencies make a change risky, and what this folder cannot call unused. Use when taking over or estimating a change to a semantic model nobody on the team built.
---

# Auditing a semantic model

The question behind this work is never "is this model good". It is one of
three: can I safely change it, what will it cost to maintain, or what did we
just inherit. The audit is worth doing because a model hides its own
complexity. Measures call other measures, a function is one body with many
callers, and a relationship decides which filters reach which numbers. An
inventory that lists eighty measures is not an audit. An audit says which few
of them a change would propagate through, and why.

Where each object lives in the project, and what a reading of one version
cannot conclude, is in
[references/model-files.md](references/model-files.md).

Its neighbours in this catalog:

- [power-bi-copilot-readiness](../POWER-BI-COPILOT-READINESS/SKILL.md) uses
  an inventory only to decide which fields should be askable. This audit is
  for someone about to change the model. What Copilot may bind to is that
  skill's question.
- [power-bi-report-faq](../POWER-BI-REPORT-FAQ/SKILL.md) writes the report's
  documentation for the people who read it. This is an engineering assessment
  for the people who maintain the model, and the two want opposite things from
  the same folder: the FAQ discards everything the report does not show, while
  here the leftovers are the point.
- [power-bi-performance-diagnosis](../POWER-BI-PERFORMANCE-DIAGNOSIS/SKILL.md)
  takes over when something is actually slow. This audit records the
  performance risks visible in the structure and stops there.
- [power-bi-model-diff](../POWER-BI-MODEL-DIFF/SKILL.md) reviews a change by
  comparing two versions. This assesses one version, with no change on the
  table.
- [power-bi-function-impact](../POWER-BI-FUNCTION-IMPACT/SKILL.md) judges
  whether introducing or changing a function is safe. This audit lists the
  callers. It does not decide that the function matches what it replaced.
- [data-quality-controls](../DATA-QUALITY-CONTROLS/SKILL.md),
  [pipeline-check-selection](../PIPELINE-CHECK-SELECTION/SKILL.md), and
  [pipeline-output-review](../PIPELINE-OUTPUT-REVIEW/SKILL.md) judge pipeline
  data. A missing measure description is a gap for the FAQ, not a failed
  quality check, and this audit does not invent a Power BI list of nulls,
  duplicates, and freshness.
- [sensitive-data-handling](../SENSITIVE-DATA-HANDLING/SKILL.md) decides what
  personal data a model may carry. This audit lists roles and which tables
  they touch. It does not decide whether a column should exist.
- [dbt-model-descriptions](../DBT-MODEL-DESCRIPTIONS/SKILL.md) writes warehouse
  column text. Column text is not a measure, and a measure often filters or
  re-aggregates the column it inherits.

## Take the inventory, and hold it as evidence

These lists, in a form you can cross-reference rather than read:

| List | Why it is needed later |
|---|---|
| Tables, and the storage mode of each partition | Import, DirectQuery, or a mix. The mode is a fact; the finding comes after |
| Relationships, with direction, cardinality, and whether they are active | The paths a filter can travel |
| Measures, with formula, format string, display folder, and description | The logic, and three different kinds of text around it |
| Calculated columns | Values fixed at refresh, which a measure that looks similar is not |
| Power Query steps, including a native query | The coupling to warehouse object names |
| User-defined functions, and every caller in this folder | One body, many results |
| Calculation groups and their items | One item wraps every measure it is applied to |
| Roles, and which tables each role's filter touches | A role that exists is not yet a role that filters |
| Visuals, and which measures they use | What a measure change reaches in this report |

Count things as you go and say what the counts are, because a reader's first
question is scale. Do not mistake counts for findings. Four hundred measures
feeding a large report can be a normal model. Thirty measures that nobody can
safely edit is a problem.

A user-defined function is a dependency, not a style choice. List its callers:
measures, calculated columns, calculation items, and other functions whose
expressions invoke it. Do not explain how to author one. If the folder has no
function text you can quote, say that no function is visible here and do not
reconstruct one.

Text an agent wrote — a measure, a bulk rename, a description — is a draft. A
generated formula is unverified until it is checked against the number it
claims to reproduce. Do not treat it as a settled dependency.

## Three kinds of measure text

A measure carries a formula, a format string, a display folder, and a
description, and a bulk edit often rewrites one of them across many measures
at once. They are not one kind of change.

- **A display folder** is where the field list files the measure. Renaming it
  is cosmetic unless something selects by that folder name: a measure, a
  calculation, or a visual that filters or titles itself from the folder.
- **A format string** changes what the reader sees. The value can be unchanged
  and look like a different number. Keep it apart from a formula change.
- **A description** is the sentence the FAQ will repeat. Rewriting it can make
  that FAQ lie while the formula stays put. It is not evidence that the
  calculation changed, and it is not evidence that the calculation is right.

## "Unused" is three different claims

Before writing that anything is unused, say which of these you mean:

- **Not referenced in this folder.** No measure, calculated column,
  relationship, role, calculation item, or visual mentions it. Defensible
  from the files. A column that is absent from the page can still feed a
  measure; that column is referenced.
- **Referenced only by other unreferenced things.** A chain that ends in
  nothing. Resolve the chain before reporting any link in it.
- **Not used by anyone.** Not a claim this folder can support. Another report
  can use a shared model, and a column can feed a role. Ask whether other
  reports use the model before calling anything dead.

Report the first two and say which. The useful finding is "these are
unreferenced in this folder, which is worth confirming against the other
reports on this model before anyone removes them". A deletion the files
cannot justify is how an audit loses the reader.

## The dependencies that make a change risky

A change-risk finding needs a reason, not a count of dependents.

**A measure or function that others are built on.** Editing it edits every
caller, and nothing in the folder will highlight which visuals moved. For a
function, the callers you can see are only the ones in this project. Callers
on other reports that share the model are invisible. If that set is unknown,
say the blast radius is unknown and stop short of calling the change safe.

**A relationship that filters both ways, or a many-to-many.** Filter context
reaches tables that look unrelated. A change that is correct on one table is
then wrong on another, and the path is the finding.

**A calculated column standing in for a measure.** The column is computed at
refresh and stored. A measure is computed when the visual asks, in that
visual's filter context. Replacing one with the other changes when the value
is fixed. Name the column and the measure that look equivalent, and say what
would move.

**Power Query that names warehouse objects**, especially a native query. A
rename upstream breaks refresh, and nothing upstream knows this model exists.
Record the objects it names.

**A calculation group.** An item wraps whatever measure it is applied to, so
one edit moves every measure a reader can select it on. Where two groups can
both apply, precedence decides which body runs. That precedence is the
dependency.

**A role that does not reach the tables a reader sees, or a relationship that
carries a filter past the role.** Read which tables the role's filter touches
and which relationships carry a filter in a security context. A role with no
filter on a table does not filter that table. A relationship that carries the
filter both ways can filter tables the role never names. This is an
inspection of the role that is already in the model. It is not a guide to
creating one.

## When storage mode is a finding

Import, DirectQuery, and composite are not quality settings. "Should be
import" is a bad finding and a common one. The mode is a finding only when
you can say what would break or what it costs to change.

| What you see | When it is a finding |
|---|---|
| Import, and the report is treated as live | The number is as old as the last refresh, whatever the page implies |
| DirectQuery on a table used to slice a large imported table | Every interaction waits on the warehouse, including slicers that look local |
| A mix of modes | The relationship where the two meet is where a change gets expensive, because a filter has to cross from one engine to the other |
| Dual mode | The table can be answered from the imported copy or by a query. Changing it changes both refresh cost and query cost; say which one the report is paying |

If you cannot say the consequence, record the mode in the inventory and do
not promote it to a finding.

Performance risks — iterator measures, bidirectional relationships, visual
count, DirectQuery — are recorded here and left for a measurement.
[power-bi-performance-diagnosis](../POWER-BI-PERFORMANCE-DIAGNOSIS/SKILL.md)
is where that measurement happens. Structure suggests cost. It does not
establish a cause.

## What an audit of this folder cannot conclude

Whether the numbers are correct. Why the report is slow. What a reader sees
first. Who uses it. Whether a description is still true of its formula: they
are separate pieces of text. A `.pbix` does not substitute for the folder. If
that is the only input, say what cannot be seen and stop. `model.bim` is
not TMDL; do not convert it.

## Anti-patterns

- Treating a count of measures as a finding. Four hundred measures feeding
  a large report can be a normal model; thirty that nobody can safely edit
  is a problem, and the count does not say which.
- Calling something unused because it is absent from this report. Another
  report can use a shared model, and this folder cannot see those callers.
- Promoting storage mode to a finding without a consequence. Import,
  DirectQuery, and composite are facts; "should be import" is not.
- Treating iterators, bidirectional relationships, visual count, or
  DirectQuery as a performance cause. Structure suggests cost; the cause is
  a measurement.
- Reconstructing a function that is not in `functions.tmdl`. Inventing a
  signature is how a review approves a function the model does not contain.
- Taking a `.pbix` or `model.bim` as the model. Neither is the
  `definition/` folder, and converting them is not this task.
