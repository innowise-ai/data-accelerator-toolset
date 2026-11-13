---
name: xfuze-integration-design
description: Designing an integration on the xFuze platform - placing each responsibility in a smart connector stage, an event-processing workflow step, an egress or a scheduled task, deciding what belongs on a connection and what in plugin configuration, and settling event granularity, failure handling, replay, sizing, alerting and rollout before anything is configured. Use when designing or reviewing a new xFuze integration, connector, workflow or plugin.
---

# Designing an integration on xFuze

The usual questions of system design still apply to an integration on xFuze: what
the source delivers, what the target accepts, how much data there is, what happens
when something fails. The platform changes how they are answered. Most answers are
a choice among building blocks that already exist, and a handful of platform
properties decide whether the design holds up in production: events are the unit of
failure and replay, plugins run under resource limits, versions are selected by
hand, and only some failures are visible to the people who support the integration.

The output of this skill is a design document, written before anything is
configured or coded. Its outline is at the end.

The platform changes over time. Take the list of available plugins, their
configuration and the current limits from the environment's plugin catalogue and
the platform documentation. This text gives the questions to ask and the reasons
behind them, not an inventory.

## The building blocks

| Block | What it does |
|---|---|
| **Smart connector** | Brings data in. A chain of plugins: a *reader* collects from the source (file share, SFTP, database, REST API, message broker), a *converter* turns the source format into records, a *mapper* turns records into events in the platform's canonical model, a *validator* checks them, and a *writer* publishes them to the platform's event stream |
| **Event-processing workflow** | Acts on each event in steps, each step run by an event processor plugin: schema validation, enrichment by lookup, mapping, matching and stitching, change detection, building a single view of an entity, writing to a warehouse |
| **Egress** | An event processor that delivers to a target system over its API, database or file transfer. Normally the last step of a workflow |
| **Task** | A scheduled job that is not driven by an event, such as a data freshness check or a monitor that turns error patterns into alerts |
| **Connection** | An endpoint and its credentials, stored once in the connection manager and referenced by the plugins that use it |
| **Error Hospital** | Where an event that failed in a workflow is kept, with its payload and error message, to be replayed, acknowledged or ignored |

Connectors, workflows and tasks run under a workflow engine, on a schedule or
continuously, and stay deployed for months. A plugin is a separately versioned
artifact with its own configuration form, which the Portal renders from the
plugin's schema.

## Start from both contracts

Write down what each end actually does before choosing any block. The gaps found
here are cheaper than the same gaps found in the Error Hospital.

**The source:**

- How data arrives: pushed, polled or dropped as files, how often, and at what
  size on a peak day.
- What identifies a record, and what a repeated delivery of the same record looks
  like.
- Whether a delivery is a full snapshot or a set of changes, and how a deletion is
  expressed.
- Whether order matters, and whether the source guarantees it.

**The target:**

- Single records or batches, and the rate and size limits.
- Whether sending the same record twice is harmless. If it is not, find what the
  target offers to make it so, such as an idempotency key or an upsert.
- What its error responses mean. Separate a *rejection of the record* (the data is
  wrong and someone must correct it) from a *failure of the call* (try again
  later). The two are handled differently everywhere downstream.
- How long its slowest operation takes. A write often takes many times longer than
  a read against the same host.

## Decide what one event is

This is the decision the rest of the design depends on, and it is easy to make by
accident, by letting one file become one event.

The platform handles failure, replay and deduplication per event. An event is
retried as a whole, lands in the Error Hospital as a whole and is replayed as a
whole. So an event should be one business thing that can succeed or fail on its
own: an order, a product, a goods receipt. A file of fifty thousand records
carried as a single event fails as one. One bad record blocks the rest, and a
replay resends everything, including what had already been delivered.

Size matters for a second reason. Each plugin runs with a memory and CPU limit, and
a plugin that exceeds its memory is terminated. That looks like a crash, not a data
error, and it recurs on every retry of the same event. Large events are also
offloaded from the event stream above a threshold and passed by reference, which is
transparent but not free. So state the largest event the design can produce, for
example the biggest hierarchy or the longest order, and compare it with the limit
of every plugin it passes through.

Some entities are a whole by nature, such as a full product hierarchy. Keep them as
one event, size the function for the largest case, and say in the design that only
the latest such event is worth replaying, since each one replaces the previous.

## Place each responsibility

Each block has one job. A design that blurs them works, and is then hard to change
and hard to support.

**The reader knows the source system and nothing about meaning.** Protocol, paging,
file patterns, archiving and watermarks belong here. Business rules do not: a reader
that filters by business rules silently drops data that nobody can find later.

**The mapper is the boundary.** After it, nothing should need to know the source's
format or field names. If a workflow step parses a source-specific field, the
mapping is incomplete, and a second source for the same entity will need the
workflow duplicated.

**Validate structure early and business rules late.** A record that cannot be
parsed or lacks its key is stopped in the connector. A record that is well formed
and wrong for the business (an unknown product code, a missing mandatory value)
is checked in the workflow, where the failed event is kept with its payload and can
be replayed after the data is corrected upstream.

**Enrichment has an ordering dependency. Design the miss.** A lookup works only if
the data it looks up has already arrived. Decide for each lookup what a miss means:
a transient gap that a later replay resolves, or a real data defect someone must
fix. Decide what the workflow does with it, who is told and with what message. A
lookup miss with no decision behind it is among the most frequent entries in an
Error Hospital.

**Egress comes last, one per target.** It translates the canonical event into the
target's request and reports the target's answer. When the target rejects a record,
keep its message intact: the person who can fix the data works in the target system
and recognises that text.

**A task is for what no event triggers.** A source that stops sending produces no
events and therefore no errors. Only a scheduled check notices silence.

### Reuse before building

Go down this list and stop at the first that fits:

1. An existing core plugin, configured.
2. An existing core plugin with a new, generally useful option.
3. A plugin specific to this client.
4. A new core plugin.

A new plugin is a new versioned artifact with its own form, tests, documentation and
release, so it is the expensive answer. A core plugin is shared by every client. A
client-specific rule added to one changes behaviour for everyone and makes the
plugin harder to reason about. The mapper and the writer that every connector uses
sit on every client's path, so a defect there is a platform incident.

Check the language as well. Connector and event processor plugins can be written in
Go or Python. A task plugin can currently be written only in Go.

## Connection or plugin configuration

The same question comes up with every setting that involves a credential, and there
is a rule for it:

- A setting that decides **which permissions the credentials need** belongs on the
  connection. Whether a stream is read by shared polling or by a dedicated consumer
  is an example: the two need different grants.
- A setting that must **differ between two components sharing one connection**
  belongs in the plugin's configuration.

A plugin's form cannot change shape according to a value held on a connection. So a
field that selects such a mode is always shown, its help text says which kind of
connection it applies to, and the plugin checks the two against each other when it
is configured. A mismatch is reported as an error that names what to fix. It is
never resolved by quietly falling back to the other mode.

Do not copy a connection's credentials into a plugin's or a task's own
configuration. The copy stops matching the connection at the next rotation, and
when a call fails nobody can tell whether the connection or the copy is at fault.
The connection may be tested and working while the component that failed never
used it. Where a component cannot reference a connection yet, record in the design
that it holds a copy, of which connection, and who updates it on rotation.

## Design the failures

For every step, list what can fail and answer four questions: is it retried, where
does it become visible, can it be replayed safely, and who acts on it.

| Kind | Example | Handling |
|---|---|---|
| Technical, transient | Timeout, dropped connection, target unavailable | Retried by the workflow. Bound the retries, and say what happens when they run out |
| Record rejected | Target refuses the record, validation fails, lookup has no result | Not retried. The event is kept for correction and replay |
| Plugin terminated | Memory limit exceeded | Recurs on retry. Needs a sizing change, not a replay |

**Know where each failure shows up.** An event that fails in a workflow reaches the
Error Hospital. A plugin restart, a cancelled context or an exceeded deadline may
appear only in the logs and never there. Alerts are typically raised from
error-level log lines per workflow, so a failure logged as a warning raises no
alert at all. Choose the log level of every expected failure on purpose. An
enrichment miss logged as a warning is invisible to whoever is on call, which is
right only if somebody else is certain to see it another way.

**Make replay safe.** Replay sends the event through the workflow again, so every
step after the failure point runs a second time. An egress therefore has to be safe
to repeat: an upsert, an idempotency key, or a check before writing. Where the
target cannot offer that, say so in the design and describe the manual check that
precedes a replay.

**Decide partial failure in a batch.** When a target accepts ninety-seven records of
a hundred, raise one error that carries the three rejected records and the target's
message for each. Failing the whole batch makes a replay resend the ninety-seven.

**Write error messages for the person who will read them.** That is a support
analyst or the client's data owner, looking at the Error Hospital. The message
names the record, says what was wrong, and where possible who should correct it and
where. "Event processing error" sends them to a developer.

## Connections that last for months

A plugin that talks to an external system runs on a schedule, idle for long
stretches, across VPNs, NAT gateways and firewalls that drop idle connections
without telling either side. A design for a new plugin states how it meets each of
these:

- **Reconnect or validate before each run.** A connection that died between runs
  must not fail the plugin permanently. When connecting takes a second and the
  schedule is minutes, opening a connection per run and closing it at the end is
  the simplest correct answer, because nothing is left to go stale. A retry after
  reconnecting is safe for a read or a listing; a write that timed out may already
  have landed, so make it repeatable before making it retry.
- **An explicit timeout on connecting.** Operating system defaults can hang
  indefinitely in a container.
- **A timeout per operation, chosen from the target's real behaviour.** A client
  timeout of ten seconds against an endpoint whose writes take longer fails every
  write with a deadline error, while reads to the same host succeed, which looks
  like a network fault and is not. Make the timeout configurable where the target's
  latency varies.
- **Cancellation passed down.** When the platform cancels a run, the call in
  progress stops with it.
- **A protocol-level keepalive where the protocol has one,** such as SSH. A
  middlebox can end a protocol session while the TCP connection underneath looks
  healthy.

The design only has to state the answers. How to implement and review each one,
with the Go and Python specifics and the tests that prove it, is in
[connector-connection-hardening](../CONNECTOR-CONNECTION-HARDENING/SKILL.md).

## Network and environment

Every external host in the design has to be reachable from the specific worker that
will call it, in each environment. Test and production are separate: different
hosts on the target's side, different network rules on the platform's side, often a
different credential. List every host and port per environment in the design, and
raise the request for network access with the platform's DevOps team at design time.
It has the longest lead time of anything in the integration and is the item most
often discovered on the day of go-live. What such a request has to contain is in
[devops-ticket-drafting](../DEVOPS-TICKET-DRAFTING/SKILL.md).

When checking reachability, test from the worker that will make the call, with the
same kind of request. A successful call from another component or another pod shows
that the target is up. It does not show that this worker can reach it.

Plugins run inside a sandbox that denies a set of system calls. A plugin that works
locally and will not start once deployed may be hitting that restriction, not a
fault in its own logic. A plugin that needs something unusual from the operating
system is a conversation with the platform team before it is built.

## Versions and rollout

Each plugin version is an immutable artifact. A connector or workflow configuration
names the plugin and its version, so a new release reaches an environment only when
someone selects it there, and a rollback means selecting the previous version
again. Nothing is redeployed.

The design can rely on that property and has to respect its consequences:

- **The rollout plan is a list of configuration changes,** per environment, in
  order, with the check made after each one. Test comes before production, and the
  design says who approves the production step.
- **Configuration must survive a rollback.** After rolling back, the older version
  reads the configuration saved by the newer one. A new required field, or a new
  meaning for an old one, breaks that. Add fields as optional with a default that
  keeps the old behaviour. Saved configurations also outlive the code that wrote
  them, so a renamed field reads as empty in every stored configuration. Rename
  across releases: add the new name, read both, migrate, then remove the old one.
- **The form is part of the version.** The configuration schema and its UI schema
  ship inside the artifact and must agree with what the code reads. A wrong form is
  corrected by releasing a new version; a published version cannot be changed.
  Checking the three against each other is covered by
  [config-form-schema-alignment](../CONFIG-FORM-SCHEMA-ALIGNMENT/SKILL.md).
- **Do not resolve "latest" implicitly** anywhere in the design. That removes the
  property that makes releases cheap.
- **Development builds are not candidates for production.** They are published on a
  separate channel with relaxed checks.

## Sizing

State, with the numbers the contract step produced: events per run and per day at
peak, the largest single event, and the memory and CPU each plugin needs for that
largest event. Compare them with the current limits per function. If the default
is not enough, the design says so and the request to raise it goes to DevOps before
go-live. Otherwise the limit is found when the largest entity arrives in production
and the plugin is terminated on every attempt.

## The design document

```text
1. Purpose and scope       what moves from where to where, and what is excluded
2. Contracts               source and target, as established above
3. Flow                    source -> reader -> converter -> mapper -> validator -> writer
                           -> workflow steps -> egress -> target
4. Components              one row each: name, block type, plugin and version,
                           existing / new option / new plugin, connection used,
                           notable configuration
5. Events                  what one event is, its key, largest expected size
6. Failures                one row each: failure, where detected, where visible,
                           retried or kept, replay safe or not, who acts
7. Monitoring              alerts, log levels of expected failures, freshness check
8. Sizing                  volumes, largest event, limits needed
9. Network and access      hosts and ports per environment, connections,
                           requests to DevOps
10. Rollout and rollback   configuration changes in order, per environment
11. Open questions         each with an owner
```

Name connectors and workflows by the pattern the environment already uses. Support
filters and alerts by workflow name, and one name that breaks the pattern is the one
left out of a filter.

## Before handing it over

- Both contracts are written down, including repeated delivery, deletions and the
  target's two kinds of error.
- One event is one business thing, and its largest size is stated against the
  limits.
- Every responsibility sits in one block, and nothing after the mapper reads a
  source-specific field.
- Each new plugin is justified against configuring an existing one.
- No credential is copied outside a connection without being recorded.
- Every failure has a row saying where it is visible and whether replay is safe.
- Every expected failure has a deliberate log level, and silence from the source
  is detected by a scheduled check.
- Hosts and ports are listed per environment and the DevOps requests are raised.
- The rollout is a sequence of version selections with a rollback for each, and
  the configuration works with both the old and the new version.
