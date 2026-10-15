# Record validation and quarantine

Validation runs at the boundary into the next stage, after the structural check
has passed. Each record is checked against the rules for its entity type. Records
that fail are not written to the next stage; they are written to a quarantine
table with a reason. Every record that passes carries on in the same batch.

## Fail the smallest entity possible

A rule belongs to one entity type, and a failure removes exactly the entity it
belongs to. An order with three lines, one of which has no product, loses that
line; the order and its other two lines go through. Rejecting the whole order for
one bad line would turn a small, fixable problem into a missing order, and the
source owner would be told about a failure that is not where the problem is.

Failures travel down the hierarchy and never up:

- **A failed parent takes its children with it.** A line cannot be published
  without its order. The children are not separate quarantine entries; the
  parent's entry is the reason, and listing every child would bury it.
- **A failed child never removes its parent.** Unless the project decided a
  parent needs a minimum number of valid children. In that case the rule is a
  rule on the parent ("has at least one valid line") and fails the parent, with
  its own message, so the reason is visible rather than implied.

## What a failure does to published data

A record that is **already published** and fails in a new batch keeps its last
valid version in published data, and its quarantine entry says why the update was
refused. Withdrawing it instead would turn one bad delivery into a deletion that
users see. Some projects do want withdrawal, for instance when a failed check
means the record is no longer allowed to be shown; that is a decision for the
project, not a default.

A record that is **new** and fails is not created.

## References are checked twice

A reference, such as a line's order or an address's customer, is valid if the
referenced record is in the same batch **or** already published. Checking only
the batch rejects every line whose order arrived in an earlier delivery.
Checking only published data rejects every new order's lines, because the order
is not published yet. And a reference to a record that failed in this batch
fails too: the parent's failure removes its children, as above.

## The quarantine table

| Column | Why it is there |
|---|---|
| `segment`, `batch_id` | Filter and trace by segment and batch |
| `entity_type`, `entity_key`, `parent_key` | Which record failed, and what it belongs to |
| `rule_id`, `field`, `offending_value` | Exactly what failed |
| `message` | The reason, in words the segment's owner can act on |
| `first_seen_batch`, `last_seen_batch`, `first_seen_at`, `last_seen_at`, `occurrences` | How long the problem has been open, and how many deliveries have repeated it |
| `status` | `open` or `resolved`, with `resolved_batch` and `resolved_at` |

One row stands for one problem: one record failing one rule. Its identity is
`(segment, entity_type, entity_key, rule_id)`, plus `field` if one rule checks
several fields. When the same problem appears in the next batch, that row is
updated (`last_seen_*`, `occurrences`); a new row is not added. A queue that adds
a row per batch shows one unfixed problem as twenty problems after twenty
deliveries, and the owner cannot tell what is new.

**Count batches, not runs.** `occurrences` goes up only when `batch_id` is new.
Rerunning the same batch must leave the quarantine exactly as it was, or every
retry inflates the counts.

**Resolve on evidence of a fix, not on absence.** An open row is resolved when its
record appears in a later batch and passes that rule. A record that is missing
from the batch has not been fixed; it has not been sent. Resolving on absence
would close the problem silently and lose it.

**Write the message for the source.** "Order 4711, line 3: unit price is
1,000,000; allowed range is 0.01 to 10,000" can be acted on. "CHK_042 failed on
fct_lines.unit_price" cannot. Build the message from a template in the rule
configuration, with the field and the value filled in, and keep internal table and
rule names out of it.

## Checks that call something external

Some checks leave the pipeline: does this URL answer, does this file exist, does
this id exist in another system. Run inside the validation loop, they make
validation as slow as the slowest server, and a few thousand records against one
host looks like an attack to that host.

Run them apart from the record loop, and write their results back as attributes
that an ordinary rule then checks. Cache each result by the reference itself, so
a URL checked yesterday is not checked again until the cache entry expires. Limit
the request rate per host. Decide what a timeout means: treating it as a failure
quarantines records because a server was slow for a minute, so a timeout is
usually recorded as "not yet checked" and checked again next time.

## Sharing the queue with a segment

The segment's owner is the person who can fix most of what is in the quarantine,
so an export or view filtered to one segment is part of the design, not an
afterthought. Filter by `segment` in the query that produces the export. A filter
applied afterwards, in a spreadsheet or a dashboard, is one wrong click away from
sending one segment's problems to another.
