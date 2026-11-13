---
name: devops-ticket-drafting
description: Writing a ticket for the DevOps or platform team - a change that needs their approval or work, an access request, or an infrastructure fault - so that it can be acted on without a call. States the exact workload, environment and target, the evidence, what was ruled out, the ask and how the result will be verified. Use when a change touches networking, permissions, secrets, resources or deployment and has to go through DevOps, or when asked to raise a DevOps ticket.
---

# Drafting a ticket for the DevOps team

The engineer who picks up a DevOps ticket has not read the code, was not in the
conversation that led to it, and has a queue. Each fact the ticket lacks is a
question in a comment and usually a day's wait for the answer. A vague ticket costs
more than time, though: it gets tested against the wrong thing, and the answer that
comes back is confident and useless.

A typical case. A scheduled job starts timing out on calls to a third-party API. The
ticket asks whether the worker has outbound HTTPS to that host. The DevOps engineer
tests from a general-purpose troubleshooting pod, where the request fails for an
unrelated reason, a missing CA bundle. They test again from the right pod with a
quick read request, which succeeds, and conclude the network is fine and the fault
is in configuration. The failing call was a write, timing out after ten seconds
while waiting for response headers. Every step was reasonable, and three days went
by, because the ticket named a host and asked a general question. It did not say
which request fails, from where, and how to repeat it.

So the standard for the ticket is this: **someone with no context can repeat the
observation, or perform the change, from the ticket alone.**

## When a change needs a ticket

A code change stays inside the repository. Some changes also need something outside
it to exist or be allowed, and a pull request that merges without that fails at
deploy time or, worse, at run time in production. Check the change for:

- a new outbound destination: a host and port the workload did not call before;
- a new inbound route, port or public endpoint;
- a new secret, credential, certificate or key, or the rotation of one;
- a new or wider permission: a role, a service account, a grant on a bucket,
  queue, topic or database;
- different resource limits: memory, CPU, storage, replicas, timeouts;
- a new deployable thing: a service, a scheduled job, a queue, a database, an
  environment, a tenant;
- a change to the build or deploy pipeline itself.

Which of these need approval, and from whom, is the project's rule. Look in its
contributing guide and agent instructions before deciding. Raise the ticket while
the pull request is still in review, not after it merges, and link each from the
other. The reviewer of the code then sees that the infrastructure half is in hand,
and the DevOps engineer can read the diff.

## Decide which kind it is

The three kinds need different content, and a ticket that mixes them tends to get
one part done and the rest forgotten. Split a mixed request into separate linked
tickets.

| Kind | The DevOps engineer needs to know |
|---|---|
| **Change** | What to change or approve, where, when, what could go wrong and how to undo it |
| **Access** | Who needs what, at which level, why and for how long |
| **Fault** | What was observed, where, how to repeat it, and what has been ruled out |

## Name things exactly

Most round trips are about identity. "The worker in test" is clear to the author and
ambiguous to anyone running a cluster with forty workloads.

- **Environment:** its name and its identifier, and the tenant or client when the
  platform has several. Test and production are separate facts. If the ticket
  covers both, say so and give each one's details.
- **Workload:** the service, the namespace, and the pod, worker or job that makes
  the call or needs the change. Take it from the log line or run record, not from
  memory.
- **Target:** for network matters the full URL or `host:port`, and the HTTP method.
  For access, the tool and the exact resource in it.
- **Time:** with a time zone, UTC where possible. Logs, dashboards and the user
  interface often show different zones, and an hour's offset sends the reader to
  the wrong log lines.
- **Run:** a run, workflow, trace or request identifier that the DevOps engineer
  can paste into the log search.

## The tracker's own fields

Projects add required fields to DevOps tickets: an issue type, a request type, a
client or tenant, a priority. Their values are a closed list that belongs to the
team. Read them from the team's guide for raising DevOps requests, or from the
tracker's create screen. If a value is not obvious, ask. A wrong request type routes
the ticket to the wrong queue, where it waits unseen.

Teams usually have a pattern for the summary too. Follow it if one exists; if none
does, lead with the kind and include the tool or component, the tenant and the
environment, so the ticket can be found from a list:

```text
Access Request: BigQuery, internal analytics, UAT
Change: raise memory limit for product-hierarchy function, acme, PROD
Fault: orders worker cannot reach service desk API, acme, TEST
```

## A change ticket

```text
What changes
  <one or two sentences: the thing, its current value, its new value>
Why
  <the reason, and the link to the pull request or design>
What is needed from DevOps
  <approve / apply / both, and the exact items>
Where and in what order
  <environments, and whether production waits for a result in test>
When
  <deadline or dependency: a release, a client's approval, a maintenance window>
Risk
  <what this can affect besides its target, and the worst plausible outcome>
Rollback
  <how to return to the current state, and how long that takes>
Verification
  <what will be checked afterwards, and by whom>
```

Give the current value next to the new one ("memory limit 1 GB to 4 GB, CPU request
200m to 1000m"). A reviewer judges a change by its size, and "increase the limit"
has none. Give the evidence for the number as well: the size of the input that hit
the limit, or the log line where the process was terminated.

Say plainly what is being asked for. "Please review" leaves it open whether the
DevOps engineer is expected to apply something or only to agree. If approval from
someone else is also needed, such as a client or a security reviewer, name them and
say whether it has been given.

## An access ticket

```text
Who
  <named person or service account>
What
  <tool, and the resource in it: project, dataset, workspace, environment>
Level
  <read / write / admin: the least that does the job>
Why
  <the task that needs it, with a link>
Until
  <end date, or "permanent" with the reason>
```

One ticket per person and tool keeps the audit trail readable. Ask for the level
the task needs. A request for admin "to be safe" is the one that gets questioned
and delayed, and it is also the one that should be.

## A fault ticket

Keep three things apart, in this order, because the reader weighs them differently:

**What was observed.** The exact error text, copied, not paraphrased. "Timeout" and
`context deadline exceeded (Client.Timeout exceeded while awaiting headers)` after
about ten seconds are different findings: the second says the connection opened and
the server did not answer in time. Add when it happened, how often, and since when.

**What works, and what was ruled out.** Comparisons narrow a fault faster than
anything else, so state each one with its source:

- the same URL, called from another component, returns 201;
- the same URL from a laptop returns 200;
- the same run reaches a different external host without error.

Each line removes a class of causes. Say also what could not be checked.

**What you think, and what you ask.** A hypothesis is welcome when it is labelled as
one. The ask is separate, and specific enough to be answered: "Does the
`orders-worker` deployment in namespace `acme-test` have an egress rule allowing
`servicedesk.example.com:443`?" can be answered yes or no. "Can you check
connectivity?" cannot.

### Make it repeatable

Give a command that repeats the failing request, and say where to run it:

```bash
# from a pod of deployment orders-worker, namespace acme-test
curl -sS -m 10 -X POST "https://servicedesk.example.com/api/incidents" \
  -H "Authorization: $API_KEY" -H "Content-Type: application/json" \
  -d '{"summary":"connectivity test"}' -o /dev/null -w '%{http_code} %{time_total}s\n'
```

A reproduction proves something only if it matches the failure in the ways that
matter: the same source workload, the same method and path, the same timeout. A
read that succeeds says little about a write that times out, and a test from another
pod says nothing about this pod's network rules or installed certificates. If the
test would create real data on the target, say so and offer a harmless variant.

State what each result would mean: "a 2xx within ten seconds means the network path
is fine and the fault is in the job's own configuration; a timeout means it is not."
Then the answer settles something whichever way it comes out.

## Priority

Describe the impact and let the priority follow from it: who is blocked, which data
is late or wrong and for whom, whether it is production, whether there is a
workaround, and any date that matters. "Very high" without that is an adjective, and
a queue full of adjectives is sorted by who asks loudest.

## Evidence without secrets

Paste errors and commands as text. Text can be searched and copied; a screenshot
cannot, so it is a useful addition and a poor substitute.

Keep credentials out: no API keys, tokens, passwords or connection strings, in the
text or in a screenshot. Write a variable name where the value would go, as in the
command above. Remove personal and customer data from payloads, leaving the field
names and the shape. A ticket is read by more people than the repository, is copied
into email, and keeps its history after an edit.

## After it is raised

When a reply reports a test that differs from the failing case, answer with the
specific difference ("that request was a GET from the troubleshooting pod; the
failure is a POST from the worker") and the command again. When a missing fact turns
up, put it in the description as well as the comment thread. The next person to
pick the ticket up reads the description first.

## Draft, then one round of questions

Draft from what the conversation, the diff and the logs already hold. Under the
draft, list together what could not be determined: an environment identifier, a
tracker field value, whether production is in scope, the deadline. A line marked as
unknown is better than a plausible guess, because the reader cannot tell a guess
from a fact.

Then hand the text over. Create the ticket in the tracker only when the engineer
asks for that and has seen the final text: it goes out under their name and
notifies another team.

## Before handing it over

- The ticket is one kind: change, access or fault.
- Environment, workload and target are named exactly, with identifiers.
- A change states the current value, the new value, the risk and the rollback.
- An access request names the person, the least sufficient level and an end date.
- A fault separates observation, what was ruled out, hypothesis and ask, and
  carries a reproduction that matches the failing request.
- Times carry a time zone, and errors are quoted, not paraphrased.
- There are no credentials or personal data in the text or the attachments.
- The related pull request and tickets are linked.
