# Cross-referencing a Tableau workbook file

The file mechanics behind the audit in [`../SKILL.md`](../SKILL.md). The inventory
is the easy half; this is about the joins between its lists, which is where the
findings are, and about the ways a naive search gets them wrong.

## Getting at the XML

A `.twb` is XML already. A `.twbx` is a zip around one, together with whatever the
workbook packaged: extracts, file-based data, images.
    10|
```bash
unzip -o <workbook>.twbx -d <tmp>
```

A consequence worth knowing before anyone quotes file size as complexity: a
`.twbx` is mostly its extracts. A hundred-megabyte package can hold a trivial
workbook, and a small one can hold the worst workbook in the project.

The root element records the Tableau version the workbook was last saved with.
That is a cheap and useful audit fact — it bounds which features can be present,
    20|and a version several years behind the project's current one says something about
when anyone last opened this file deliberately.

## Where each fact lives

| List | Where it comes from |
|---|---|
| Data sources | Data source elements, each with a caption and a connection whose class names the connector |
| Extract or live | An extract element inside the data source; its absence means live |
| Custom SQL | A relation marked as text, carrying the query as its body, rather than one naming a table |
| Joins defined in the workbook | The relation tree on the data source, where join relations carry their clauses |
    30|| Fields | Column elements: internal name, user-facing caption, datatype, dimension or measure role, and whether hidden |
| Calculated fields | A column with a calculation child, whose formula is a string attribute |
| Parameters | Columns on the parameters data source, with a domain type, a current value and the allowed set |
| Worksheets | Worksheet elements, each naming the data sources it uses and carrying its own filters |
| Dashboards | Dashboard elements with a zone tree; a zone naming a worksheet places that worksheet |

## The one mechanic the audit depends on

**A formula refers to another field by its internal name, not its caption.** For a
calculated field the internal name is usually generated and looks nothing like the
caption a user sees.

    40|That single fact decides whether the audit is right or useless:

- Searching for a caption finds the field's **declaration**. It will not find a
  single use of it, because no formula contains the caption.
- Searching for the internal name finds the **uses**. This is the search that
  answers "what depends on this".

So the usable index is built in two passes: collect every field as a pair of
internal name and caption, then search for each internal name across the whole
file. Report in captions, search in internal names. Skipping the first pass is the
   50|standard way to produce a report claiming most of a workbook is dead.

## Everywhere a reference can hide

A field counts as used if anything at all mentions it, and several of these are
easy to miss because they are not shelves:

- another calculated field's formula
- a filter, including a data-source-level filter
- a tooltip or a dynamic title, where fields are embedded in formatted text
- a group, set, bin or hierarchy built on the field
- a reference line, band or trend-line definition
   60|- an action — filter, highlight, parameter or set — which can carry source and
  target field names
- a sort, when the sort is by a field rather than by the displayed value

Tooltips and titles are the two that matter most in practice, because a field used
only there is invisible to anyone scanning shelves, and removing it breaks text
that a reader of the dashboard sees.

## Reading aggregation, and why it is a finding

A worksheet does not refer to a raw field. It refers to an instance of the field
    70|that names the base field plus the aggregation applied to it, which is why the
same measure can be summed on one sheet and averaged on another with nothing in
the field's own definition recording either.

For the audit this means two things. Collecting usages has to resolve the instance
back to its base field, or the dependency graph misses edges. And a field that
appears under more than one aggregation, or at more than one grain, is itself a
finding worth reporting: whatever a change to it does, it will not do the same
thing everywhere.

Level-of-detail expressions and table calculations are the place to be most
    80|careful. Their result depends on the shelves and the filters around them, so the
formula alone does not determine what the field computes. Read it, say what you
read, and mark the reading as provisional.

## What the file will not support

- **Any claim about usage by people.** Nothing in the file counts views. A
  worksheet on no dashboard, a hidden field and a leftover data source all look
  identical to something kept deliberately.
- **Any claim about runtime.** No timings, no row counts, no query text as
  executed. Structure is a hypothesis about cost.
    90|- **Any claim about the rendered view.** Zones carry coordinates and nothing about
  what renders in them.
- **Any claim about correctness.** Formulas without the business rule they were
  written against cannot be judged, and the rule is not in the file.
