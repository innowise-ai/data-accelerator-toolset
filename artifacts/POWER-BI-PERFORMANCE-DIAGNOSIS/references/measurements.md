# What a measurement contains

Written for the diagnosis in [`../SKILL.md`](../SKILL.md). This is how to
read a recording someone already has. It is not a path through the product
to capture one.

The diagnosis names a measurement. These are the files that measurement
arrives as. Do not read a `.vpax` as why a page is slow. Do not read query
duration as "the DAX is expensive". Refresh duration still comes from the
service, not from these files.

| Artifact | What it is | What it is not |
|---|---|---|
| Desktop recording | Performance Analyzer export, JSON, one interaction; per visual: DAX query duration, DirectQuery duration when a table is DirectQuery, render duration, remainder | not engine split, not refresh, not the service |
| Server trace | DAX Studio server timings or a profiler trace | the only artifact that splits formula-engine / storage-engine time, and the one that carries the warehouse statement text |
| `.vpax` | VertiPaq Analyzer: model size | not a timing |
| `.pbix` | a package | neither size evidence nor a timing |

## A Desktop recording of one interaction

The recording belongs to one interaction: the slicer change, the bookmark,
the page open, the drill that was slow. It lists each visual that did work
and attributes that visual's time to these buckets:

- **The query.** How long that visual waited for a result.
- **Direct query.** When a table is DirectQuery, how long the external
  query took to return results.
- **The display.** How long that visual spent drawing after the result
  arrived.
- **The remainder.** Time in the interaction that is neither of those.

The DAX query bucket is one duration. It does not split formula-engine time
from storage-engine time. Do not read a long query duration as "the DAX is
expensive". On DirectQuery, read the Direct query duration first: it is the
warehouse's part of the wait. The formula-engine / storage-engine split is
not in this file.

The recording does not include:

- A service refresh. Refresh has no visual to time.
- Other interactions the reader did not capture. A slow bookmark is not
  evidence about a slow slicer.
- The service under the capacity readers use. Desktop is one machine. If the
  complaint is about the published report, say that this number is not that
  complaint unless it was captured there.

## A server trace, when one is present

A trace of the same interaction can separate what the Desktop recording
adds together.

| Part | What it means | What it does not prove |
|---|---|---|
| Formula engine | DAX evaluated outside a storage-engine scan | That an iterator in the model is this time. The trace has to name the query |
| Storage engine | Scans of imported data, including callbacks: a scan whose xmSQL shows `CallbackDataID` calls the formula engine row by row, and that time sits inside the storage-engine query | That the model is "too big". A scan of a small table can dominate if the query runs it repeatedly |
| DirectQuery statement | The SQL the interaction sent, and how long the warehouse took | That the wait is the model's to fix. If the statement is the time, the next diagnosis is the warehouse's |

Match the trace to the interaction. A trace collected at a different moment,
or under different filters, is a different measurement. Duration without the
query text is a number you cannot act on. Query text without a duration is a
hypothesis.

## Refresh

Ask for the refresh history from the service: which table, how long, whether
it failed or merely took the time. The model's partitions say whether a table
is imported and what M it runs. They do not say how long that M took. A
native SQL string inside the M is a candidate for the warehouse time. Confirm
it against the refresh duration or against the warehouse's history of that
statement before calling it the cause.

## Handing off

If the confirmed time is a Snowflake statement sent by DirectQuery or by
refresh, the rest of the diagnosis is
[snowflake-query-profile-diagnosis](../../SNOWFLAKE-QUERY-PROFILE-DIAGNOSIS/SKILL.md).
Pass the statement and the duration. Do not rewrite the measure in order to
change that statement. If the warehouse is not Snowflake, report that the
time is in the warehouse statement and stop.
