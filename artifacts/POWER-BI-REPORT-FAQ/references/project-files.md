# Reading a Power BI project

What the folder can be asked for, and what it will not answer. Written for the
FAQ in [`../SKILL.md`](../SKILL.md), where every claim in the output has to be
traceable to a source. This is the part of that sourcing that comes out of the
files.

The same folder is how any later Power BI skill in this catalog reads a model.
The judgements below are the ones the FAQ needs. They are not a tour of an
editor, and they are not a way to rewrite the model.

## Ask for the project folder

A Power BI Project is a directory of plain text: a `.pbip` pointer, a report
folder, and a semantic-model folder. Ask for that directory.

A `.pbix` is a package. Measures, relationships, Power Query, and roles are
not honestly readable from it. Say what cannot be seen and stop. Do not
invent an export into model text, and do not unpack the package and treat the
inside as a project.

The report's `definition.pbir` says which semantic model it uses. A `byPath`
reference points at a semantic-model folder next to the report, or at one
elsewhere by a relative path. A `byConnection` reference points at a model
published in a workspace, and that model's text is not in this directory. If
the model folder is not here, ask for the project that contains it. Visual
titles are not a substitute.

Inside the semantic-model folder, the model text is the `definition/`
directory of TMDL files. A project saved as TMSL holds the same model in a
single `model.bim` instead; read it as JSON in place (measures, columns and
their `description` under `model.tables`, relationships under
`model.relationships`). Do not convert the file.

The `.pbi` directory beside the definition (a local cache, editor settings)
is not the model. Ignore it.

## Where a measure's facts live

Measures are declared in the table files under `definition/tables/`. A model
may also split objects across files, so read every `.tmdl` under
`definition/` before concluding a measure has no description. Report-level
measures, when the report defines any, live in the report part
(`reportExtensions.json`), not in the semantic model. They are still
measures, and they still need a description you can quote.

On a measure, read these and keep them apart:

| Fact | Where it is | What it is |
|---|---|---|
| Description | The `///` lines immediately above the measure, with no blank line between those lines and the measure | The business definition. This is the only one of these that may enter the FAQ as a definition |
| Formula | The expression after `=` | How the number is computed. Not the definition |
| Format string | `formatString` under the measure | How the number is drawn. The same value can look like a different number after this changes. Not the definition |
| Display folder | `displayFolder` under the measure | Where the field list files it. Not the definition |
| Annotations | `annotation` entries under the measure | Extra metadata. Not the description, unless the owner has told you that a named annotation is where this project keeps definitions |

A translated description can also sit under a culture file. If the FAQ is for
readers of that language, prefer the translation and say which one you used.
If there is no translation, the model's own description is the source, not a
translation you write.

A description an agent wrote is a draft until a person accepts it, or it was
already in the file when you opened the project. The file does not label its
author. If this session added the text, it does not count.

## What the report files record

When the report is stored as separate JSON files under its `definition/`
folder:

| Looking for | Where it is |
|---|---|
| Page order, and which page the file calls active | `pages/pages.json` |
| A page's filters, and whether the page is a tooltip or a drillthrough | that page's `page.json` |
| A visual's query, position, and formatting | `visual.json` under that page |
| State a reader reaches only through a bookmark | `bookmarks/` |
| Filters that apply to the whole report | `report.json` |

An older report may be one `report.json` instead of that folder. The same
facts are in the one file. Neither form is a picture of the report.

The active page is a file fact. It does not establish what the reader sees
first, which slicers are visible, or what a bookmark or a tooltip page shows
only when it is invoked. That is why the screenshot is an input. When the
files contain bookmarks or a tooltip page, say so and ask for those states,
because the landing screenshot will not include them.

## What the project does not contain

- **The refresh schedule.** Import mode on a partition says the table is
  loaded, not when the service reloads it. A DirectQuery partition has no
  schedule of its own. A model can mix the two. The schedule is a question
  for the owner.
- **Purpose, audience, and owner.** Nowhere in the files.
- **Whether the description is still true of the formula.** They are separate
  pieces of text. The file records no link that would tell you one was edited
  without the other.
- **Whether a column is unused.** A column absent from every visual can still
  feed a measure. The FAQ does not answer this.

Connection strings and credentials appear in data-source and Power Query
text. They do not belong in the FAQ. Name the source system and the objects a
reader needs, and leave the connection details out.

## Two versions

A commit of this folder can show which measure or visual changed, because the
model and the report are text. A commit of a `.pbix` cannot be reviewed that
way. Comparing two versions means comparing the two project folders. A text
diff of a packaged file is not a comparison, and neither is an explanation of
how to save the package as a project.
