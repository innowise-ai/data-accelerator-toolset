---
name: jira-ticket-status-update
description: Bringing a Jira ticket in line with the real state of the work - finding the ticket from the branch, reading what commits, pull requests and deployments show, proposing the workflow transition that matches, and writing a comment that says what changed, where it is and what is left, applied only after the engineer confirms. Use when asked to update a ticket, move it to review or done, or post progress on a Jira issue.
---

# Updating a Jira ticket from the state of the work

A ticket drifts from the work in two directions. It runs behind: the pull request
merged last week and the ticket still says In Progress, so the person planning the
sprint counts work as open that is finished. Or it runs ahead: the ticket says Done
because the code merged, while nothing has been released, so the reporter tests
production and finds the old behaviour.

Both come from updating the ticket from memory, at the moment the engineer happens
to think of it. The repository and the pull request already record how far the work
got, so the update is built from them. Two rules follow:

- **The status follows evidence.** A ticket moves to the status that matches what the
  work shows, not the one the engineer hopes to reach today.
- **The comment says what the status cannot.** A status has five or six values. Where
  the change is deployed, which version carries it, how to check it and what is
  still missing fit only in words.

## What this changes, and when

Reading a ticket changes nothing. Three actions do: a transition, a comment and a
field edit. Each is visible to everyone watching the ticket, usually by email, and a
transition can start automation such as a deployment, a notification to a client or
a move to another board. None of them can be taken back unseen.

So the order is fixed: read, draft, show the engineer the transition, the comment
and any field change together, and apply only what they confirm. An update goes out
under the engineer's name.

If the agent has no access to Jira, everything below still applies; the result is a
comment to paste and the name of the status to select.

## Find the ticket

The key (`PROJ-1234`) is nearly always in the work already, because teams put it
there so the tracker can link back:

```bash
git branch --show-current                       # feature/PROJ-1234, fix/PROJ-1234-timeout
git log origin/main..HEAD --format=%s           # commit subjects
gh pr view --json number,title,url,state,isDraft,mergedAt,baseRefName
```

A key matches `[A-Z][A-Z0-9]+-[0-9]+`. Take it when the branch, the commits and the
pull request agree. When they name different tickets, or none, ask. Do not search
Jira by a guessed title: a ticket with similar wording in another project is easy to
find and wrong to update.

## Read the ticket before drafting

Four things on the ticket shape the update:

- **Current status and assignee.** The update starts from where the ticket is, and
  a ticket assigned to someone else is not the engineer's to move without asking.
- **The description and its acceptance criteria.** These are what Done will be
  judged against.
- **The last few comments.** An update that repeats the previous comment tells the
  reader nothing, and an unanswered question in the thread is something the update
  should answer.
- **The transitions available now.** See below; this is the part most often
  assumed and most often wrong.

### Transitions belong to the project

A Jira workflow is defined per project and issue type. The status after In Progress
may be called In Review, In Peer Review, Code Review or Ready for QA, and the same
name can mean different things in two projects. From any status only some moves are
allowed, and a move can require a field such as a resolution or a fix version.

So list the transitions the ticket offers and choose from that list; do not send a
status name that seems likely. Through an MCP server this is its get-transitions
tool. Through the REST API:

```text
GET  /rest/api/3/issue/PROJ-1234/transitions?expand=transitions.fields
POST /rest/api/3/issue/PROJ-1234/transitions     {"transition": {"id": "<id>"}}
```

The `fields` in the response show what a transition requires. If the status the
evidence points to is not offered, say so and stop there. Walking the ticket through
two or three statuses to reach it fires every notification and automation on the
way, so do that only when the engineer asks for it.

## How far the work actually got

Gather this for the ticket's key, across the repositories the work touched:

```bash
git log --all --grep='PROJ-1234' --date=short --format='%h %ad %D %s'
gh pr list --search 'PROJ-1234' --state all \
  --json number,title,state,isDraft,reviewDecision,mergedAt,baseRefName,url
git tag --contains <merge commit>               # which release carries it
```

Each state of the work means something different to a reader:

| What the evidence shows | What it means |
|---|---|
| Commits on a branch, no pull request | Work in progress |
| Draft pull request | In progress, visible for early comments |
| Pull request open, review requested | Waiting for review |
| Changes requested | Back with the engineer |
| Merged to the main branch | Code complete, not necessarily released |
| A release tag or version contains the merge | Released, in a named version |
| That version is deployed to an environment | Available there, and only there |

The last three are where tickets run ahead. Merged is not released, and released is
not deployed to the environment the reporter looks at. Git shows the first two.
Deployment usually has to come from the pipeline or from the engineer, so ask
rather than infer it from a merge.

### From evidence to status

Which status each row maps to is the team's decision. Some close a ticket on merge;
others keep it open until it is in production or until QA has passed it. Look for
the rule in the project's contributing guide or agent instructions. If it is not
written down, ask once what Done means here, and suggest recording the answer so
the next update does not ask again.

Before proposing a closing status, compare the acceptance criteria with the
evidence. List any criterion the change does not cover. A ticket closed with a
criterion unmet is reopened later by someone who has lost the context, which costs
more than leaving it open with a clear note.

## The comment

The readers are the reporter, a tester, a project manager, and the engineer who
opens the ticket in six months. Most of them will not open the pull request. Write
for them:

1. **What changed, as an outcome.** What the system does now that it did not before.
   Not the list of commits and not the names of functions.
2. **Where it is.** The pull request, the version, and the environment it has
   reached, each stated only if the evidence shows it.
3. **What is left, or what the reader has to do.** How to check it, what is still
   open, what was deliberately left out of scope.
4. **Blockers,** each with who or what it waits on and since when.

Leave out any part with nothing to say, and keep it short enough to read in the
notification email.

```text
Orders with an empty delivery reference are now rejected at validation with a
message naming the order, instead of failing later at export.

Merged in PR #418, included in version 2.7.0. Deployed to test; not yet in
production (planned with Thursday's release).

To check on test: resend order 100234 from the sample file. It should appear in the
error list with "delivery reference is empty".

Not covered: orders already stuck in export before this change. Tracked in
PROJ-1301.
```

Write only what changed since the last comment. If nothing did, the honest update is
one line saying what the ticket is waiting for.

### When the work is blocked

Say what is blocked, on whom or what, and since when, as in the last part of the
comment. Then make it visible outside the comment, because boards and filters do
not read prose: link the blocking ticket with the project's "is blocked by" link
type, and use the Blocked status or flag if the workflow has one. A comment alone is
found only by someone who opens the ticket.

### Formatting that survives

A comment reaches Jira by paste or through the API, and the two treat markup
differently. The Cloud REST API version 3 takes Atlassian Document Format, version 2
takes wiki markup, an MCP server converts in its own way, and the editor converts
some pasted Markdown and leaves the rest as literal characters. Short paragraphs and
simple lists come through all of these unchanged. Tables, nested lists and headings
often do not, and a status comment rarely needs them.

Give links in full. An `@` mention notifies that person, so add one only when the
engineer asks for it.

Do not put credentials, tokens, connection strings or customer records in a comment.
Tickets are readable far more widely than the repository, are copied into email,
and keep their history after an edit.

## Other fields

Change a field only when the engineer asked for it or the chosen transition requires
it. Reassigning to a reviewer or tester on a transition is a team convention; follow
it if it is written down, otherwise ask. Leave estimates, time tracking, sprint,
priority and fix version alone unless asked: other people plan from them.

## Show the draft, then apply

Put everything in one message:

```text
PROJ-1234  Reject orders with an empty delivery reference
Status:   In Progress -> In Review   (transition "Submit for review")
Assignee: unchanged
Comment:
  <the comment text>
Based on: PR #418 open, review requested from two people; 6 commits since Monday
```

Ask the open questions in the same message: deployment state if it could not be
seen, any acceptance criterion not covered, anything the evidence left unclear.

After confirmation, apply the transition first and the comment second. If the
transition fails, because a required field is missing or the workflow refuses it,
the comment has not yet told anyone that the ticket moved. Report what was applied
and what was not.

For several tickets, show one summary first, then confirm and apply them one at a
time. A batch that fails halfway leaves some tickets updated and the engineer unsure
which.

## Before handing it over

- The key was taken from the work or given by the engineer, not guessed.
- The proposed status is one the ticket offers from where it is now.
- Every statement about merge, release and deployment traces to evidence or to
  something the engineer said.
- Acceptance criteria were compared before a closing status was proposed.
- The comment says what changed since the last one and contains no secrets.
- Nothing was written to Jira before the engineer confirmed it.
