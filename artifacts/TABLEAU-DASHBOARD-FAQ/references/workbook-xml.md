# Reading a Tableau workbook file

What the file can be asked for, and what it will not answer. Written for the FAQ
in [`../SKILL.md`](../SKILL.md), where every claim in the output has to be
traceable to a source; this is the part of that sourcing that comes out of the
file.

## Getting at the XML

A `.twb` is already XML. A `.twbx` is a zip archive around one: the `.twb`, plus
whatever the workbook packaged with it — extracts, file-based data, images. Unzip
it and work on the `.twb` inside.

```bash
unzip -o <workbook>.twbx -d <tmp>
```

The extracts in the archive are compiled data, not a readable source of
definitions; there is nothing in them this task needs. Work on the XML.

Searching the XML line by line finds captions but loses their context: a match
tells you the string exists, not which field, worksheet or data source owns it,
and ownership is the fact that matters. Use something that can follow the nesting
— an XML parser, or an editor that folds the tree — and read the element you
landed in along with its parent.

Workbooks are large and repetitive. Pull out the parts you need rather than
reading end to end, and expect several hundred elements of scaffolding for every
one that carries a fact.

## Where each fact lives

| Looking for | Where it is |
|---|---|
| Data sources and what they connect to | Each data source element carries a caption and a connection whose class names the connector |
| Custom SQL | A relation whose type marks it as text, with the query as its body — as opposed to a relation naming a table directly |
| Extract or live | An extract element inside the data source, pointing at the packaged extract file. Its absence means the connection is live |
| Fields | Column elements, each with an internal name, a user-facing caption, a datatype, and a role marking it a dimension or a measure |
| Calculated fields | A column with a calculation child holding the formula as a string |
| Parameters | Columns on the workbook's parameters data source, marked with a parameter domain type and carrying their current value and allowed values |
| Filters | Inside the worksheet that carries them; filters applied across a data source sit on the data source instead |
| Which worksheets make up a dashboard | The dashboard's zone tree, where a zone naming a worksheet is that worksheet's place on the dashboard |

Two details that decide what reaches the FAQ:

- **Caption, not name.** The internal name is a bracketed identifier, sometimes
  generated, and often nothing like what the reader sees. The caption is what the
  view labels the field. A FAQ that uses internal names describes a dashboard its
  readers do not recognise.
- **Hidden fields.** A column can be marked hidden; it exists in the model and not
  in the view. Hidden fields do not belong in user-facing documentation.

## The definitions field

The definitions this task is after are a calculated field, which means they are a
formula string on a column like any other. What distinguishes it is shape rather
than location: a `CASE` or nested `IF` over a metric name, returning definition
text per branch, with no arithmetic anywhere in it. It is wired into tooltips, so
the text is written for a reader rather than for an engineer.

Captions seen in practice are `Hover Definitions`, `Tooltip`, `Tool Tip` and
`Metric Definitions`. Treat those as where to look first and not as the set of
possibilities — the convention is a team's, not Tableau's, and a project with its
own name for the field is common. If none of them match, two things are worth
doing before reporting the workbook has no definitions: look for a calculated
field of that shape under any caption, since the shape is the real signal; and
ask what the project calls it.

Read the formula, not a rendered tooltip. A tooltip assembles the calculation's
output with other field values at render time, so a screenshot of one tooltip
gives you one metric's definition, while the formula gives you the set the author
wrote.

## What the file does not contain

Each of these is a question a FAQ reader asks, and none of them has an answer in
the workbook.

- **The refresh schedule.** The file records that an extract exists and when it
  was last refreshed. When and how often it refreshes is held by the server or
  site that runs it. A live connection has no schedule of its own at all — it is
  as current as the table behind it, which is the upstream pipeline's business.
- **What the dashboard looks like.** Zones carry coordinates in an abstract grid,
  so the geometry is technically present, and it is still not an answer: the tree
  says a container holds a container holds a worksheet, with nothing about what
  renders, what is legible, what is visible without scrolling, or which view opens
  first. This is why the screenshot is an input and not a nicety.
- **Purpose, audience and owner.** Nowhere in the file, in any form. They come
  from people.
- **Whether anything in it is still true.** A formula, a caption and a tooltip
  definition are three independently editable strings, and the file records no
  relationship between them. A definition can describe a calculation that has
  since changed, and the XML looks exactly the same either way.
