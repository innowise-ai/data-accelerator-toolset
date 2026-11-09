---
name: power-bi-performance-diagnosis
description: Finding out why a Power BI report is slow — whether the time is in refresh, in an interaction's query, or in rendering — and what a measurement can and cannot prove. Use when a report is slow and the cause is not yet established.
---

# Diagnosing a slow report

A slow report attracts confident advice: remove the iterators, turn the
relationships one way, switch DirectQuery to import, cut the visuals. Each of
those is sometimes the answer and usually not, and acting on the wrong one
costs a rewrite plus the original problem. The expensive mistake is being
persuasive about the wrong cause, because a plausible fix that changes
nothing is also a fix that nobody re-examines.

So this is diagnosis, and it ends at a cause with evidence behind it. A
rewrite starts after that, and not in this skill.

What a Desktop recording contains, what a server trace adds and still
does not prove, and which file is a timing rather than a model-size dump,
is in [references/measurements.md](references/measurements.md).

Its neighbours in this catalog:

- [power-bi-measure-translation](../POWER-BI-MEASURE-TRANSLATION/SKILL.md)
  stops at whether a SQL metric and a DAX measure are the same number.
  Generated DAX stays unverified until it is measured, which is this skill
  when the question is speed, and that skill when the question is the number.
- [power-bi-model-audit](../POWER-BI-MODEL-AUDIT/SKILL.md) notes the structural
  risks it can see: iterator measures, bidirectional relationships, visual
  count, DirectQuery. Those are hypotheses. This skill tests them.
- [snowflake-query-profile-diagnosis](../SNOWFLAKE-QUERY-PROFILE-DIAGNOSIS/SKILL.md)
  takes over when the time is a DirectQuery query against Snowflake. The split
  is the first thing to establish. Getting it wrong is how a team spends a
  week on a model whose warehouse queries were the wait.
- [snowflake-cost-hotspots](../SNOWFLAKE-COST-HOTSPOTS/SKILL.md) finds which
  warehouse queries are worth attention at all, which is the question when the
  report is fast and the warehouse bill is not.
- [error-diagnosis](../ERROR-DIAGNOSIS/SKILL.md) is the general version of the
  same discipline: narrow it down, prove it, then change something.

## "Slow" is three different problems

They share almost no causes, and a fix for one does not touch the others.

| What is slow | What would actually move it |
|---|---|
| Refresh | Power Query, the load into an imported table, the warehouse statement that refresh runs. Not a visual |
| An interaction's query | The query that interaction sends: a slicer change, a bookmark, a drill. One interaction, one set of queries |
| Rendering | Drawing the visuals after the data has already come back |

Ask which of the three, and for whom, and since when. "Fifteen seconds" and
"ninety seconds" rarely have the same cause, and "slower than it used to be"
is a different investigation: something changed, and finding what changed
beats profiling. Half the time this conversation narrows the problem to one
interaction, or rules the model out, before any file is opened.

## Structure is a hypothesis

These are worth recording, and none of them is a cause until a measurement
says the time is there:

- A measure that iterates a large table, or that filters inside the
  iteration, can force work the storage engine does not answer in one scan.
- A relationship that filters both ways can make one slicer expand into a
  much larger query than the visual suggests.
- A page with many visuals can be slow because each one queries, or because
  drawing them dominates after the queries return. The count does not say
  which.
- DirectQuery means an interaction can wait on the warehouse. It does not
  mean this interaction does.

Present a structural reading as candidates ranked by likelihood. Presenting
one as the cause is the failure mode of this task, and it is invisible in the
write-up.

## A measurement, and what it does not split

A Desktop performance recording times one interaction on the machine that
captured it. For each visual it separates the time spent waiting for that
visual's query from the time spent drawing the visual, plus a remainder that
is neither. That split is enough to tell a query problem from a rendering
problem for that interaction.

It is not enough to tell engine time from formula time from warehouse time.
The query duration is one number. On an imported table that number mixes the
formula engine and the storage engine. On DirectQuery it includes the wait
for the warehouse. The recording does not contain those parts, and it does
not time a service refresh at all. A recording from Desktop is also not the
report running in the service under the capacity its readers use. Say which
machine and which interaction the number belongs to.

If a server trace of that same interaction is present, read it for the split
the Desktop recording lacks. Formula-engine time is DAX the storage engine
did not answer, including the cases where the formula engine calls back into
the data row by row. Storage-engine time is scans of imported data. On
DirectQuery, the trace can carry the warehouse statement and how long that
statement took. Those parts explain where the query duration went. They do
not prove that this query is the one the reader complained about, that a
structural smell caused it, or that a different formula would be faster. A
trace of a different interaction is evidence about that other interaction.

When the time is in a DirectQuery statement against Snowflake, stop and hand
the statement to
[snowflake-query-profile-diagnosis](../SNOWFLAKE-QUERY-PROFILE-DIAGNOSIS/SKILL.md).
When the warehouse is not Snowflake, the finding is still that the time is
outside the model. Name the statement if the trace has it, and stop. This
skill does not diagnose a warehouse it cannot read, and it does not rewrite
the measure to avoid the query.

Refresh is the case with no interaction to record. Ask for the refresh
duration from the service. A native query or a step that does not fold is a
hypothesis until that duration, or the warehouse's own history of the
statement refresh ran, says the time is there.

## Do not rewrite the measure

Generated DAX, including DAX an agent wrote, is unverified until it is
checked. A formula that compiles and returns a plausible number can still be
a different number. This skill stops at the cause. It does not produce a
replacement measure, and it does not accept one that arrived without a
comparison against the original at the same grain and the same filters.

If the cause is rendering, a rewritten measure does not touch it. If the
cause is refresh, a rewritten measure does not touch it either, unless the
measure is a calculated column in disguise and the refresh trace says so.
Say that before anyone starts editing.

## Anti-patterns

- Rewriting the measure here. Diagnosis ends at a cause; a replacement that
  was never compared at the same grain and filters is a different number,
  and it does not touch rendering or refresh.
- Diagnosing Snowflake SQL here instead of handing the statement off. This
  skill cannot read a warehouse, and a week on the model is how the wait
  stays in the query.
- Treating iterator measures, bidirectional relationships, visual count, or
  DirectQuery as the cause. Structure is a hypothesis until a timing says
  the time is there.
- Reading query duration as "the DAX is expensive". A Performance Analyzer
  JSON does not split formula engine from storage engine or from the
  warehouse.
- Reading a `.vpax` or a `.pbix` as why a page is slow. VertiPaq Analyzer
  is model size, not a timing, and a package is neither size nor a timing.
- Treating a Desktop recording as the service refresh, or as the report
  running under the capacity its readers use. The JSON is one interaction
  on the machine that captured it.
- Using a trace of a different interaction as evidence about this one. A
  slow bookmark is not a slow slicer.
- Treating generated DAX that compiles as verified. A plausible number can
  still be a different number.
