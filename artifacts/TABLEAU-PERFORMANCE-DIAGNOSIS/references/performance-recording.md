# Reading a performance recording, and reasoning without one

Supporting detail for [`../SKILL.md`](../SKILL.md). The recording is the only
input that measures rather than suggests, so most of this file is about reading it
honestly; the last section is what structure can contribute when no recording is
available, and how far that goes.

## Getting one

Recording is a setting rather than a tool: it is switched on in Tableau Desktop
before the slow interaction and switched off after, and on a published dashboard
it is requested on the view's URL. Either way the output is a workbook, not a log
file — the recording ships as a Tableau workbook whose summary views are the
intended way to read it.

Three things decide whether the recording is worth reading at all:

- **Record where the complaint is.** A recording made in Desktop measures Desktop:
  its connection, its caches, its machine. If users are slow on the published
  dashboard and Desktop is fine, Desktop's recording explains nothing, and the
  difference between them is itself the finding.
- **Record the interaction that is slow**, not opening the workbook. Start the
  recording, do the one thing, stop. A recording of a whole session is a pile of
  events nobody will attribute.
- **Decide about the cold run.** The first run of anything includes warm-up and
  cache misses. If the complaint is about every load, that is the run to record;
  if it is about repeated use, record the second run. Recording both is cheap and
  the comparison is often the answer by itself.

Recording adds overhead, so read the proportions between events rather than their
absolute durations. "This one query is 80% of the time" survives the overhead;
"the query takes 4.2 seconds" does not.

## What the recording contains

Events, each with a duration, a category and the worksheet it belongs to. The
categories are the diagnosis — they are the split between query time, Tableau's
own compute, and building the view:

| Category | What it is telling you |
|---|---|
| Executing Query | Time in the warehouse or the extract engine. The recording carries the query text, which is the handover point to query diagnosis |
| Compiling Query | Tableau turning the view into SQL. Large when the view is complicated, rarely the cause on its own |
| Connecting to Data Source | Connection establishment. Significant here usually means an authentication or network problem, not a workbook one |
| Generating Extract | Extract refresh, which is a different complaint from a slow dashboard |
| Blending Data | Blending, executed locally after separate queries return. Expensive, and often confined to one sheet |
| Computing Table Calculations | Local compute on the returned result, scaling with rows returned rather than rows shown |
| Computing Totals | Same place, same reason |
| Sorting Data | Local sort, which gets expensive on wide result sets |
| Geocoding | Mapping place names to coordinates. Only appears on geographic views, and is fixable by using real coordinates |
| Computing Layout | Building the view. Tracks mark count and formatting, and is the one category a faster warehouse cannot improve |

Read it in this order: sort events by duration, take the longest, note which
category and which sheet it belongs to, and only then look at the workbook. That
order matters because opening the workbook first supplies a theory, and a theory
will find evidence for itself in a list of events.

Two readings that are commonly got wrong:

- **Many events of the same category, each short.** Not a slow query — a lot of
  them. The fix is on the dashboard, in how many sheets and filter domains it
  needs, not in any one query.
- **One sheet accounting for almost everything.** The best possible outcome,
  because the investigation shrinks to one view. Check whether that sheet blends,
  or carries a table calculation, before reading its query.

When Executing Query dominates, the query text in the recording is the thing to
carry forward. It is generated SQL, and reading it as if a person wrote it is
misleading, but it answers the two questions that matter: what grain was asked
for, and which filters made it into the query rather than being applied after.

## Reasoning from structure, and its limits

No recording is a weaker position, not a hopeless one. These are visible in the
workbook file and each is a candidate worth testing:
- how many worksheets a dashboard contains, which sets the floor on how many
  queries a load issues
- how many data sources it touches, and whether several connect to the same table
- whether each connection is live or an extract, and what the extract was filtered
  to when it was built
- filters set to show only relevant values, filters over long discrete lists, and
  filters applied across a data source
- blending, as opposed to joins or relationships, since blending is local work
- the physical join tree, where a large-to-large join defined in the workbook
  inflates every query over it
- level-of-detail expressions, which add aggregation to the query, and table
  calculations, which add local compute and transfer
- filters on calculated fields rather than stored columns

And these are not in the file, which bounds what a structural reading can claim:

- **Mark count.** It depends on the data, not the definition. A view defined on
  one dimension renders as many marks as that dimension has members, and the file
  does not know how many that is.
- **Rows returned.** Same reason, and this is what local compute scales with.
- **Any duration at all.** No timings, no row counts, no cache state.
- **What the warehouse did.** Live connections spend their time in a system the
  workbook cannot see into.

So a structural reading produces a ranked list of candidates and an explicit note
that nothing has been measured. That is a legitimate deliverable — it is often
enough to decide what to record next — and it becomes a bad one the moment it is
written as a conclusion.
