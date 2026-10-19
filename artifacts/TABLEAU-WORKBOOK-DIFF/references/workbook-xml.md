# Comparing two workbook files

The mechanics behind [`../SKILL.md`](../SKILL.md): what to pull out of each
version so the two can be compared, and what to throw away before comparing
anything.

## Getting at the two files

A `.twb` is XML. A `.twbx` is a zip around one, plus extracts and other packaged
resources.
    10|
```bash
unzip -o <old>.twbx -d <tmp>/old
unzip -o <new>.twbx -d <tmp>/new
```

Compare the `.twb` from each. The rest of the package is not the change: extracts
differ between two saves of the same logic, and an identical workbook over
refreshed data produces different numbers with nothing to compare.

## Why the raw diff has to be discarded
    20|
Tableau writes the document whole on every save. A no-op save changes, among other
things:

- the order of elements within their parents
- generated internal names for new or re-created fields
- the recorded Tableau version and build the file was saved with
- window and view state — zoom, selected tab, panel sizes
- the packaged preview image

    30|None of that is authored content, and all of it lands in a line-based diff. The
ratio is bad enough that the diff cannot be triaged: a genuine three-field change
arrives inside hundreds of changed lines, and a reviewer who tries to read it
either gives up or stops at the first plausible-looking difference.

Normalising the XML — sorting elements, stripping state — makes the diff smaller
and still does not make it semantic. Two formulas that differ only in whitespace
show as changed; a filter whose scope moved from one sheet to a whole data source
shows as an element appearing somewhere unrelated. The inventory comparison
avoids both.

    40|## What to extract from each version

Pull these into a comparable form, keyed as noted. The key is what decides whether
a difference reads as a change or as a deletion plus an addition.

| Extract | Key on | Compare |
|---|---|---|
| Data sources | Caption | Connector class, live or extract, extract filters |
| Relations | Data source | Custom SQL text, table names, join types and clauses |
| Fields | Internal name | Caption, datatype, role, default aggregation, hidden flag |
| Calculated fields | Internal name | Formula text, and the caption separately |
    50|| Parameters | Caption | Current value, data type, allowed values or range |
| Filters | Owning sheet or data source, plus field | Included or excluded members, range bounds, whether in context, whether applied across the data source |
| Worksheet field usage | Sheet, plus base field | Which aggregation the field is used with, and the sort |
| Dashboards | Caption | Which sheets are placed, and the tab order |

Keying fields on the internal name and reporting them by caption is what
separates a rename from a replacement. The reverse — keying on caption — turns
every rename into a pair of unrelated findings and loses the fact that the formula
behind it is unchanged.

Keying parameters and data sources on caption is the pragmatic choice in the other
    60|direction: their internal names are less stable across edits, and a caption
collision is rare enough to notice.

## Differences that need a second look rather than a class

Three cases where the inventory comparison reports something true and the obvious
reading of it is wrong:

- **A formula that differs only in formatting.** Whitespace and line breaks are
  part of the stored string. Compare with whitespace normalised before reporting a
  formula as changed, or the result-altering list fills with non-changes and stops
    70|  being read.
- **A field present in one version and absent in the other, with its formula
  appearing under a different internal name.** Tableau can re-create a field
  during some edits. The content is unchanged; the identity moved.
- **A filter that appears in the new version on a sheet that is also new.** Not a
  filter change — a new sheet that came with filters. Classify it with the sheet,
  or the filter list implies an effect on existing views that does not exist.

## What neither file holds

- **Any number.** No results, no row counts. The comparison names candidates and
    80|  cannot settle them.
- **What either version looks like.** Zone coordinates are not a rendering. A
  layout change is reviewed from two screenshots.
- **Who changed it or why.** Workbooks carry no history of their own. If the
  project keeps them in version control, the commit message is the only place
  intent exists; if it does not, intent has to be asked for, and the comparison is
  worth much less without it.
