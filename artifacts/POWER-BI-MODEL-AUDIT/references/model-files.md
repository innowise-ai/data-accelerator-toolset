# Reading a model for an audit

Where each inventory item lives, and what one version of the folder cannot
tell you. Written for the audit in [`../SKILL.md`](../SKILL.md).

Ask for the Power BI Project folder: the report part and the semantic-model
part. A `.pbix` is a package. Measures, relationships, Power Query, and roles
are not honestly readable from it. Say so and stop. Do not invent an export
into model text.

The model text is `definition/` under the semantic-model folder, as TMDL. A
project saved as TMSL holds the same model in a single `model.bim` instead.
Read it as JSON in place: tables, columns and measures under
`model.tables`, with `isHidden`, `summarizeBy` and `dataCategory` on each
object, relationships under `model.relationships`. Do not convert the file. Ignore the
`.pbi` cache next to the definition.

If `definition.pbir` points at the model with `byConnection` and the
semantic-model folder is not here, you are looking at a report without its
model. Ask for the model's project. Visuals are not a substitute for it.

## Where each list lives

| List | Where it is |
|---|---|
| Tables, columns, measures, calculated columns, partitions, calculation groups | `definition/tables/*.tmdl`. A model can split objects across files, so read every `.tmdl` under `definition/` before concluding something is absent |
| Relationships | `definition/relationships.tmdl`. Direction, cardinality, whether the relationship is active, and whether a security filter is carried one way or both |
| Shared Power Query | `definition/expressions.tmdl`, plus the `source` of each partition |
| Connections | `definition/dataSources.tmdl` |
| User-defined functions | `definition/functions.tmdl`, when the model has any. Absence of the file means no function is in this model |
| Roles | `definition/roles/*.tmdl`. A role names the tables it filters |
| Cultures | `definition/cultures/`. Translated descriptions, not a second model |
| Visuals, page filters, report filters, bookmarks | the report's `definition/` folder, or one `report.json` if the report was saved that way |

On a measure, keep the formula (the expression after `=`), `formatString`,
`displayFolder`, the `///` description immediately above the measure, and
`annotation` entries apart. They are four different facts. A calculated
column is a column whose declaration carries an expression. A data column
names a `sourceColumn` and does not. A visible column with
`summarizeBy: sum` will be summed even when a measure was meant to replace
it. Hidden is not the only fact.

The date-table mark is `dataCategory: Time` on the table, and a calendar
object when present. A table named Date is not that mark.

A partition's `mode` is `import`, `directQuery`, or `dual`. Composite is not
a mode on one partition. It is a model that mixes those modes, or that
reaches another model and holds imported tables beside it. Read the modes and
say which tables sit on which side of a relationship.

A calculation group is a table that contains a `calculationGroup` and
`calculationItem` entries. The item's expression is the body that wraps the
measure it is applied to. Precedence, when more than one group exists, is on
the group.

Power Query is the M expression on the partition, and any shared expression it
calls. A native query is M that embeds a SQL string. Record the objects that
string names. The steps are the dependency. Do not rewrite them here.

## Callers of a function

A function's callers are the expressions in this folder that invoke its name:
measures, calculated columns, calculation items, and other functions. A
mention inside a description or an annotation is not a caller. Reports that
share the model and are not in this folder contribute callers you cannot see.
Say that the caller list is the one this folder contains.

If `functions.tmdl` is missing, or a declaration is not text you can quote,
do not reconstruct a signature. Describe the dependency in words only if the
call sites are visible, and stop rather than inventing the body.

## What one version does not record

- Whether other reports use this model.
- Whether a description still matches its formula.
- Who wrote a measure. Text an agent wrote is a draft until a person accepts
  it or it was already in the model; the file does not label its author. A
  formula you cannot check against a result is unverified.
- Why a visual is slow. The structure can suggest it. The cause is a
  measurement.
- What the reader sees. That is a screenshot, and it belongs to the FAQ.

A commit of this folder can show which object changed. Comparing two versions
is a different job from reading one. A line diff of the TMDL is noisy
(identifiers, annotations, layout) and is not this audit.
