---
name: data-quality-controls
description: Building data quality controls into a pipeline - a structural check that stops a batch, record-level validation that quarantines failing records with a readable reason and resolves them on a passing rerun, a comparison of the next publish against the last published state, and quality scores per source and per processing stage. Use when designing, building or changing validation rules, a quarantine or failure queue, a pre-publish change report, release thresholds or an approval gate, or quality KPIs compared across sources. Not for reviewing one run's output or choosing tests for a single change.
---

# Building data quality controls

A pipeline that only has tests can answer one question: did this run pass? The
controls described here answer the three questions that matter once data comes
from sources you do not control:

1. **Which records are wrong, and why?** Failing records are stopped at the
   boundary into the next stage and kept, with a readable reason, in a quarantine
   that the source can act on. Everything valid carries on.
2. **What is about to change?** Before data is published, the next state is
   compared with the last published one, so a mass deletion or an implausible
   jump is seen before users see it.
3. **How good is each source?** Quality measures computed the same way for every
   source and every stage, so sources can be compared with each other and the
   effect of each processing stage can be measured.

They are worth building in that order. Quarantine protects published data from
the first day. The change comparison needs a history of published states, and the
scores need both that history and settled definitions of what is measured.

This skill covers designing and building these controls. Its neighbours:

- Reviewing what one run produced, once, is
  [pipeline-output-review](../PIPELINE-OUTPUT-REVIEW/SKILL.md). The comparison
  built here runs on every publish; that review is a judgement made once.
- Choosing which tests a change needs is
  [pipeline-check-selection](../PIPELINE-CHECK-SELECTION/SKILL.md).
- Column tests on dbt models are
  [dbt-model-testing](../DBT-MODEL-TESTING/SKILL.md). A failing dbt test fails the
  model, not one record; see [references/dbt.md](references/dbt.md) for building
  record-level quarantine in dbt.
- Keeping versioned history of a table, which the published snapshots here rely
  on, is [scd2-implementation](../SCD2-IMPLEMENTATION/SKILL.md).

## Read the reference for the part you are building

| Building | Read |
|---|---|
| Structural checks, record validation, the quarantine table, reruns | [references/quarantine.md](references/quarantine.md) |
| The comparison before publish, thresholds, bundled releases, an approval gate | [references/release-diff.md](references/release-diff.md) |
| Quality measures per source and stage, comparison across sources, sharing them | [references/scorecard.md](references/scorecard.md) |
| Any of these on a dbt project | [references/dbt.md](references/dbt.md) as well |
| Any of these in Python pipeline code | [references/python.md](references/python.md) as well |

The rest of this file is what all three parts share. Settle it before building
any of them, because changing it afterwards means rebuilding all three.

## One set of keys for everything

Every table these controls write carries the same keys:

| Key | What it is | Examples |
|---|---|---|
| `segment` | The unit you report, compare and share by | A supplier, an upstream system, a tenant, a region |
| `batch_id` | One delivery or run from one segment | A file drop, an API pull, a CDC window, a scheduled run |
| `stage` | Which layer the data was in when it was measured | Raw, validated, published, after enrichment |
| `entity_type` | The kind of record | Order, order line, customer, address |
| `entity_key` | The record's business key within its segment | Order number |
| `parent_key` | The key of the record it belongs to, if any | The order an order line belongs to |

The keys are what connect the three parts. A quarantined record, the change that
its absence caused in the next publish, and the drop in its segment's score all
share a segment, a batch and an entity key, so a reader can move from one to the
other. They are also what make per-segment sharing possible: a segment's data can
only be filtered out cleanly if every row says which segment it belongs to.

Use the project's own words for these in its tables and reports. The names above
are for this skill; the shape is what matters.

Entities usually form a hierarchy: an order owns its lines, a customer owns its
addresses. Write the hierarchy down before writing any rule, because it decides
what happens when a record fails (see
[references/quarantine.md](references/quarantine.md)).

## Two kinds of failure, kept apart

**A structural failure** is a problem with the delivery itself: a column that was
there last time is missing, a column is renamed, a type or date format changes,
the encoding or delimiter changes. **A content failure** is a problem with a
record: a required value is empty, a number is out of range, a reference points
at nothing.

They need different handling, and mixing them causes the worst false alarm these
controls can raise. If a source drops a column and the pipeline carries on, every
record fails the rule on that field, the quarantine fills with thousands of
identical entries, and the change comparison reports the field removed from every
record. All of it is true and none of it is useful: the problem is one missing
column, and it is an engineering problem, not a data problem the source owner can
fix record by record.

So the structural check runs first, against an expected schema per segment (kept
from the last successful batch, or agreed as a contract), and a structural failure
stops that segment's batch before any record is validated. A column that is
present but empty for 40% of records is not structural; that is content, and the
record rules handle it. When a structural change is expected, such as a newly
agreed column, the expected schema is updated and the batch is run again.

## Rules, thresholds and measures are configuration

Rules, thresholds and quality measures change far more often than the pipeline
does. Keep them as data: a rule table or file with the rule id, the entity type,
the field, the check and its parameters, a severity, a scope (all segments or one)
and a message template. The same goes for change thresholds and measure
definitions.

Be honest about the limit of this. A new rule *of an existing kind* (another
required field, another range) is a new row. A new *kind* of check (the first
cross-record check, the first lookup against an external system) is code, written
once, after which its instances are rows again. Design the set of check kinds so
that the common rules are rows.

## Decisions to make with the project

Several questions have no right answer in general, and a wrong guess is
expensive to undo once sources and users rely on the behaviour. Ask about each
one, explain the trade-off, and record the answer next to the configuration:

| Decision | Options |
|---|---|
| An unexpected extra column in a delivery | Stop the batch, or warn and continue |
| A parent whose children all fail | Publish the parent anyway, or require a minimum number of valid children |
| A published record that fails in a later batch | Keep its last valid version published, or withdraw it |
| A record missing from a batch | Deleted at once, after N batches without it, or only through an explicit deletion |
| Range checks | Fixed bounds, change against the record's previous value, or deviation from the segment's or category's median |
| Publishing | Automatic, an approval per segment, or releasing several batches together |
| Sharing results with one segment | An export, or a filtered view; and how many segments must exist before cross-segment figures are shown |
| Retention | How long quarantine records, batch results and published snapshots are kept |

If the project has not decided, build the observable version first: quarantine
records and compute comparisons, but publish as before. That keeps an approval
gate possible later without blocking anything now.

## Before calling it done

Run the same batch twice. The second run must produce the same published state,
the same quarantine (with no duplicated records and no doubled counts), and the
same comparison. A control that changes its answer on a rerun cannot be trusted
on the first run either.

Fix one quarantined record at the source and run again. Its quarantine entry must
be marked resolved and the record must reach the published data, with nobody
editing the quarantine by hand.

Produce one segment's export and confirm that it contains only that segment's
records, by querying for any other segment's key in it, not by reading it.
