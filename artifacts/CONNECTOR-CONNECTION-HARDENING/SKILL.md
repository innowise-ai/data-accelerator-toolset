---
name: connector-connection-hardening
description: Makes a scheduled connector survive connections that die while it is idle - recovery across runs, explicit connect and operation timeouts, cancellation that reaches the socket, and protocol keepalive where it applies. Use when writing or reviewing a reader, writer or plugin that talks to SFTP, SMB, a database, an API or a broker on a schedule.
---

# Hardening a connector's connections

A connector that runs every ten minutes for months fails differently from code that
runs once. Most of its life is spent idle, and the network it idles on - a NAT
gateway, a firewall, a VPN, a cloud load balancer - forgets idle flows without
telling either end. The next run picks up a connection that looks open and is not.

This artifact is about that failure and the four others that ride along with it. It
applies to any language; the per-library mechanics are in
[references/go.md](references/go.md) and [references/python.md](references/python.md).

## Why the failure is silent

A middlebox that drops an idle flow sends nothing. Both ends still hold a socket in
the established state. On the next run the client writes a request, the kernel
accepts it into the send buffer, and the write *succeeds*. The read then waits for a
reply that will never come, while the kernel retransmits into the void. On Linux,
with default settings, giving up takes around fifteen minutes.

So the symptom is never "connection refused". It is a run that hangs, a schedule
that backs up behind it, and - if the orchestrator does not enforce its own timeout -
a worker that never comes back. The connector's own logs show a request sent and
nothing after it.

The idle limits are short and differ by provider. At the time of writing the defaults
are 350 seconds for an AWS NAT gateway, 4 minutes for an Azure load balancer and 20
minutes for an established TCP flow through Google Cloud NAT. A ten-minute schedule
outlives the first two every time. Check the current figure for the network the
connector actually runs behind rather than trusting these.

## The five properties, in order of consequence

Review them in this order. The first is the only one whose absence turns a network
blip into a permanent failure; the rest turn a hang into a fast, clear error.

### 1. Recovery across runs

A connection held open between scheduled runs must either be checked before each run
or be replaced when it fails. Without one of the two, the first idle drop breaks the
connector until someone restarts it. **Treat a long-lived connection with neither as
a blocking defect.**

There are three workable shapes. Pick by what a connection costs to establish
compared with the schedule interval:

- **Connect per run.** Open at the start, close at the end. Nothing survives the
  idle period, so there is nothing to go stale. When the handshake costs a second and
  the schedule is minutes, this is the simplest correct answer and should be the
  default.
- **Check, then use.** Keep the connection, and before each run send the cheapest
  request the protocol offers (a database ping, an SFTP `stat` of the working
  directory, an HTTP `HEAD`). On failure, close it and reconnect. The check costs one
  round trip per run.
- **Use, then reconnect once.** Keep the connection and try the real operation. On a
  connection-level error, reconnect and retry **once** - but only when the operation
  is idempotent. A list or a read can be retried. A write that timed out may already
  have landed, and retrying it blind is how a file is uploaded twice or a row is
  inserted twice.

For writes, make the operation safe to repeat before making it retry. Upload to a
temporary name and rename on completion, or write with a key the target deduplicates
on. Then the retry question goes away.

A pool (database/sql, SQLAlchemy, an HTTP client's transport) is the same problem
with the bookkeeping done for you, *if* it is configured to discard connections it
has not used for a while or to validate them on checkout. Out of the box, many do
neither.

### 2. An explicit connect timeout

Never rely on the operating system to bound a connect. On Linux the default SYN
retry policy gives up after about two minutes; a container may inherit different
settings, and a TLS or SSH handshake on top of the TCP connect may have no limit at
all. Set a timeout on establishing the connection, and check that it covers the
handshake, not only the TCP connect. Several client libraries time the TCP step and
then wait on the handshake indefinitely.

A sensible value is seconds, not minutes: long enough for a slow VPN, short enough
that a dead host fails the run while the schedule can still absorb it.

### 3. Cancellation that reaches the socket

Orchestrators cancel work: a run times out, a deployment drains a worker, a user
stops a job. That signal - a Go `context.Context`, an asyncio cancellation, a
shutdown event - has to reach the dial and every blocking read and write.

The defect to look for is a function that **accepts** a cancellation token and then
does not pass it on. It reads as correct at the call site, so nobody checks. The
effect is that a cancelled run keeps its connection and its worker until the network
gives up, which is the fifteen-minute hang from above, now outliving the job it
belonged to.

### 4. A timeout on each operation

A connect timeout does not bound a read that stalls halfway. Each read, write, list
and delete needs its own deadline - from the cancellation token, or from a timeout the
library enforces.

Scale the deadline with the work. A fixed thirty seconds is wrong for both a 1 KB
listing and a 2 GB upload. Derive it from the payload size and a conservative
throughput floor, with a minimum, or bound idle time between chunks rather than the
whole transfer.

### 5. Protocol keepalive, where the protocol has one

A keepalive keeps a middlebox's flow entry fresh, so the connection is not dropped in
the first place. Two things decide whether it is needed.

**TCP keepalive may already be on.** Go's dialer enables it by default (every 15
seconds). Python's sockets do not. Do not flag a missing TCP keepalive in Go code
unless the dialer explicitly turns it off.

**Protocols on top of TCP often need their own.** An SSH session, a WebSocket, an
AMQP channel or a database session can be torn down by a proxy or by the server's own
idle timeout while the TCP connection underneath is alive. SSH has a keepalive
request, WebSocket has ping frames, AMQP has heartbeats, and database pools have
validation queries. Add the protocol's own mechanism when the connection is held
across idle periods.

**Keepalive does not replace recovery.** It keeps a NAT entry alive; it does nothing
when the server restarts, the VPN reconnects or a failover moves the endpoint.
Property 1 is still required.

## Put the fix in the shared layer

When several connectors use one connection library - an internal package wrapping
SFTP, SMB, a database driver - the timeouts and keepalive belong there, so every
connector gets them. Fixing it in one connector leaves the others with the defect and
a reviewer who thinks it was fixed.

The cost of that choice is version pinning. If each connector pins its own version
of the shared library, a fix there reaches a connector only when that connector is
bumped. When someone says "fixed in the shared library", the follow-up question is
*which connectors have taken that version*. List them, and treat the rest as still
affected.

## Reviewing a connector

1. Find every place a connection is created: dial, client constructor, pool, session.
   Note for each whether it lives for one run or across runs.
2. For each long-lived connection, find the recovery path (property 1). If there is
   none, stop: that is the headline finding.
3. Check the connect timeout, and whether it covers the handshake (property 2).
4. Follow the cancellation token from the entry point to the network calls. Note each
   call that does not receive it (property 3).
5. Check each blocking operation for a deadline, and whether it scales with the
   payload (property 4).
6. For each protocol layered on TCP that is held across idle periods, check for its
   keepalive (property 5). Skip bare TCP in Go.
7. Check whether the connector is the right place for the fix, or whether it belongs
   in a shared connection layer.

Rank findings by consequence, not by count. A missing recovery path is blocking. A
missing timeout or an ignored cancellation token is a defect to fix in this change.
A missing protocol keepalive on a connection that is already recovered is an
improvement.

Report it as a table, one row per property, with the evidence beside it:

| Property | State | Evidence |
|---|---|---|
| Recovery across runs | Present / Missing / N/A | where the check or reconnect is, or which connection lacks it |
| Connect timeout | Set / Missing / TCP only | the value and where it is set |
| Cancellation | Propagated / Dropped at ... | the first call that does not receive it |
| Operation timeouts | Enforced / Missing / Fixed size | which operations, and how the deadline is derived |
| Protocol keepalive | Set / Missing / N/A | the protocol, and the interval |

If the connector manages no connection of its own, say so and stop. Do not fill the
table with "N/A" to look thorough.

## Proving it works

A review that reads the code can say a recovery path exists. Only a test can say it
runs. Three cheap ones cover most of it:

- **Kill the connection between runs.** In an integration test, run the connector
  once, close the server side of the connection (or stop and restart the test
  server), then run it again. The second run must succeed without a restart. A
  fault-injecting proxy such as Toxiproxy can also drop traffic silently, which is the
  more realistic failure.
- **Dial a black hole.** Point the connector at an address that never answers, such
  as `192.0.2.1` (reserved for documentation), and assert the run fails within the
  configured connect timeout rather than minutes later. Some networks reject that
  address at once instead of dropping it, which proves nothing; check the test
  actually waits.
- **Accept and stay silent.** Start a local listener that accepts the TCP connection
  and never sends a byte, then point the connector at it. This is the handshake hang
  that a TCP-only connect timeout misses, and the run must still fail within its
  limit.

If neither test exists and the change touches connection handling, say so in the
review. The behaviour the change exists for is the behaviour nothing exercises.
