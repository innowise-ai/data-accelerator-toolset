# Where Copilot’s facts live

Written for the readiness check in [`../SKILL.md`](../SKILL.md). A screenshot
cannot supply these. If `definition/` is missing, the hidden flags, the
descriptions, the synonyms, the relationships, the roles, and the date-table
mark cannot be seen. Say what cannot be seen and stop. A `.pbix` is a
package. `model.bim` is not TMDL. Do not convert either.

Preparing the model is editing the properties below in these files. Do not
invent a synonym. Do not write a second description for "the AI".

| Decision this skill already makes | Where it lives |
|---|---|
| Column hidden | `isHidden` on the column in `definition/tables/*.tmdl` |
| Visual/Copilot will still sum it | `summarizeBy` on that column (`sum` vs `none`). Hidden is not the only fact |
| Description Copilot will repeat | `///` immediately above the measure |
| Synonyms | linguistic metadata in `definition/cultures/*.tmdl` |
| Bidirectional filter | `definition/relationships.tmdl` |
| Role the check used | `definition/roles/*.tmdl` |
| Which date "last month" uses | `dataCategory: Time` on the table, and a calendar object when present, plus which relationship is active |

The date-table mark is `dataCategory: Time` on the table (and a calendar
object when present). A table named Date is not that mark. Order date and
ship date both answer "last month"; the active relationship is which one
a question in those words will follow.

Hide the column when the measure replaces it. If the column must stay
visible, set `summarizeBy: none`. A visible column with `summarizeBy: sum`
will be summed even when a measure was meant to replace it, and Copilot
will treat that sum as the answer.
