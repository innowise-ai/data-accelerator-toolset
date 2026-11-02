# What a measurement contains

Written for the diagnosis in [`../SKILL.md`](../SKILL.md). This is how to
read a recording someone already has. It is not a path through the product
to capture one.

## A Desktop recording of one interaction

The recording belongs to one interaction: the slicer change, the bookmark,
the page open, the drill that was slow. It lists each visual that did work
and attributes that visual's time to three buckets:

- **The query.** How long that visual waited for a result.
- **The display.** How long that visual spent drawing after the result
  arrived.
- **The remainder.** Time in the interaction that is neither of those.

The query bucket is one duration. It does not split formula-engine time from
storage-engine time, and on DirectQuery it does not split the model's own
work from the warehouse's. Do not read a long query duration as "the DAX is
expensive" or as "the warehouse is slow". It is the wait, and the split is
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
| Formula engine | DAX evaluated outside a storage-engine scan, including a callback that pulls rows back one at a time | That an iterator in the model is this time. The trace has to name the query |
| Storage engine | Scans of imported data | That the model is "too big". A scan of a small table can dominate if the query runs it repeatedly |
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
