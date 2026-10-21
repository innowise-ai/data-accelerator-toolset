---
name: daily-standup-update
description: Preparing a daily standup or async daily update from the engineer's actual activity - commits, pull requests, reviews and issues since the last working day - in three fixed sections, Done, Next and Blockers, with every item traced to evidence or confirmed by the engineer. Use when asked for a standup, a daily update or a daily status message.
---

# Writing a daily update from evidence

A daily update written from memory has predictable faults. Recent work crowds out
the start of the period, finished work and work in progress blur together, and the
format drifts from one day to the next. The section that suffers most is Blockers:
it is the one that takes effort to word and can feel like complaining, so it is the
one left out, and it is the only section the rest of the team can act on.

The fix is to write the update from what the engineer actually did, which the
repository and GitHub already record, and to ask about the rest instead of filling
it in. The rule this comes down to: **every line in Done traces to evidence or to
something the engineer said.** A short true update is worth more than a full one
with a guessed line in it, because a reader cannot tell which line was guessed.

## One draft, then one round of questions

The update has to be quicker to get than to write from memory, or the engineer goes
back to memory. A question before every step defeats that, so start from defaults,
build the draft, and put every question in one message under it.

The defaults:

- **Window:** from the start of the previous working day.
- **Repositories:** the current one, plus any the engineer named in the request or
  keeps in their personal agent instructions.
- **Format:** a chat message.

The message under the draft says which window and repositories were used, then asks
together:

- what else belongs in Done that left no trace in git;
- which Next candidates to keep, drop or add;
- for each blocker candidate, whether it blocks, on whom and since when, or whether
  there are no blockers;
- whether the window, the repositories or the format should change.

If an answer changes the window or the repositories, gather again and redraft.
Otherwise apply the answers and hand over the final text. Ask before drafting only
when there is nothing to draft from, such as no repository in the current directory
and none named.

## The period: since the last working day

"Since the last update" means since the previous working day began, not the last 24
hours. On a Monday a 24-hour window covers Sunday and misses Friday, which is the day
that matters. After a day off it misses the last day actually worked.

Take the start of the previous working day as the default: Friday for a Monday
update, otherwise yesterday. It is wrong after a public holiday or leave the agent
cannot see, or when the engineer's last update went out at another time. Stating the
window in the message under the draft is what catches that, at the cost of one
redraft rather than a question every day.

Git's `--since` reads local time. GitHub search dates are in UTC, so search from one
day earlier and drop what falls outside the window afterwards rather than miss the
evening before.

## Gathering the evidence

### Which repositories

A project split across several repositories, such as a service, its pipelines and
its infrastructure, leaves its trace in all of them, and an update built from the
current one alone undercounts the day. The engineer names the others, in the
request, in their personal agent instructions, or in answer to the questions under
the draft, as a list of paths or as a folder that holds their clones.

Only repositories named this way are searched, in git and on GitHub alike.
Engineers keep personal and unrelated work alongside, often under a second GitHub
account on the same machine, and an update that names a private repository in a
team channel is a leak the engineer did not choose.

Given a folder, find the repositories under it and keep only the ones with the
engineer's commits in the window, so a folder of forty clones yields the three that
matter:

```bash
find <folder> -maxdepth 3 -name .git -prune | sed 's#/\.git$##'
```

`.git` is a file rather than a directory in a worktree, and `-name` matches both.
Worktrees of one repository share its history, so their commits come back
identical; drop repeated hashes, and use the repository name, not the folder name,
when labelling items.

### Git history

Bring remote branches up to date first, so work pushed from another machine shows
up. A fetch changes no branch and no working tree:

```bash
for repo in <path> <path>; do
  git -C "$repo" fetch --all --prune --quiet
  git -C "$repo" log --all --author="<email or name>" --since="<window start>" \
    --date=iso-local --format="$(basename "$repo") %h %ad %D %s"
done
```

`--all` covers every local and remote-tracking branch, which is what makes a branch
the engineer has not merged yet visible. `--author` is a pattern matched against
name and email. An engineer who commits from two machines or two identities needs
both, and the identities present are easy to list:

```bash
git log --all --since="<window start>" --format='%an <%ae>' | sort -u
```

Two things in this output mislead. `--since` filters on the committer date, so a
rebase or cherry-pick done yesterday brings in work authored last week. Judge each
commit by its author date (`%ad`), and treat a rebase as yesterday's work only if
the engineer says it was. And a rebased branch can leave the same change twice under
different hashes, so group by subject before counting.

### GitHub

When the `gh` CLI is installed and signed in, it adds what git cannot show: pull
requests opened, merged and reviewed, and issues touched. Every search carries
`--repo` for each repository being searched. Without it `@me` matches across every
organisation and personal repository the account can see, which is the scan the
section above rules out. A local clone's `owner/repo` is in
`git -C <path> remote get-url origin`.

```bash
gh search prs --author=@me --updated=">=<date>" --repo <owner/repo> \
  --json repository,number,title,state,isDraft,closedAt,url
gh search prs --reviewed-by=@me --updated=">=<date>" --repo <owner/repo> \
  --json repository,number,title,state,url
gh search prs --review-requested=@me --state=open --repo <owner/repo> \
  --json repository,number,title,url
gh search issues --assignee=@me --updated=">=<date>" --repo <owner/repo> \
  --json repository,number,title,state,url
```

Repeat `--repo` for each repository. Use `--owner` in its place only when the
engineer names a whole organisation as theirs to report on.

`--updated` means anything happened to the item, including a bot adding a label, so
read the state rather than trusting the match. A pull request merged in the window
has a `closedAt` inside it; for an open one, `closedAt` is a placeholder year. A
review search returns pull requests updated in the window, not only ones reviewed in
it; `gh pr view <number> --repo <owner/repo> --json reviews` shows when each review
was submitted.

`@me` is the active `gh` account. On a machine with several accounts the wrong one
returns empty results without an error, so check `gh auth status` when GitHub shows
nothing the git history says should be there.

If `gh` is missing or not signed in, continue with git alone and say in the draft
that pull request and review status were not checked. Do not sign in on the
engineer's behalf.

## Asking for what leaves no trace

Meetings, reviews in another tool, an investigation that ended without a commit,
helping a colleague, an incident: none of these reach git. That is why the
question about them comes under the draft rather than before it: a list to react to
gets a better answer than an open question, because it reminds the engineer what
the day looked like.

A quiet git log is not a quiet day. It is usually a day of investigation, review or
meetings, and only the engineer knows which. Never fill the gap with "worked on X"
because X has a branch; that is the invented line this skill exists to keep out.

## Done

One line per item, the outcome first, then the reference.

Several commits toward one change are one item. Commit subjects are written for the
log, and "fix tests", "wip" and "address review" tell the reader nothing; the line
says what the commits achieved together. Leave out merge commits and pure formatting
unless they were the work.

Say how far each item got, because "done" here means what the engineer did, not
that it is finished. A merged pull request, a pull request opened for review, and
commits pushed to a branch are three different states, and a reader planning around
the update needs to know which one it is:

```text
Merged: retry on Snowflake timeouts in the orders loader (#212)
Opened for review: SCD2 merge for customers, idempotent on re-run (#215)
Pushed, not yet in review: backfill script for 2024 invoices, tests next
```

A bare `#215` means nothing to someone who has not opened it. Give the reference
with enough of the title to stand on its own, and a full link when the readers do
not all work in the repository.

## Next

Next is what the engineer commits to, and the team plans around it, so it contains
only work the engineer agreed to. Propose candidates from the evidence: own pull
requests with changes requested, open review requests, assigned issues, branches
with recent commits and no pull request yet. Mark them as proposed in the draft, and
let the engineer keep, drop or add to them in the one round of questions. Two or three items is normal for a day. A long Next list reads as a backlog
and makes the real priority harder to see.

## Blockers

Each blocker says what is blocked, on whom or what, and since when:

```text
Prod deploy of #212 blocked on prod DB credentials from the platform team (request open since Mon)
```

All three parts matter. Without an owner nobody knows who can unblock it; without a
date nobody can tell a new blocker from one that needs escalating.

The evidence suggests candidates without settling them: a pull request waiting for
review for more than a day, a failing check, an unanswered question on an issue.
List them together in the questions under the draft, not one question each. A pull
request waiting for review is a blocker only if the engineer cannot move on without
it, and only the engineer knows that.

When there are none, write `Blockers: none`. An empty section and a missing section
look the same to a reader, and only one of them means there is nothing to help with.

## Format and target

The three sections always appear, in the same order, under the same names. Readers
scan for Blockers, and a format that moves it around makes them read everything.

The update fits on one screen, about fifteen lines. When Done runs longer, merge
related items rather than cut the period short; an update that needs scrolling is
skimmed, and the part that gets skipped is the end, which is Blockers.

The target changes the markup, not the sections:

| Target | Markup |
|---|---|
| Chat (Slack, Teams) | Bold labels instead of headings, plain list lines, links only where readers lack the repository context |
| Ticket or issue comment | A heading per section, full links, since the comment outlives the conversation |

Draft for chat unless the engineer asked for a ticket comment; switching later is a
change of markup only. A chat draft for Slack:

```text
*Done*
- Merged: retry on Snowflake timeouts in the orders loader (#212)
- Opened for review: SCD2 merge for customers, idempotent on re-run (#215)
- Paired with Ana on the late-arriving events investigation (no code yet)
*Next*
- Address review on #215
- Start the 2024 invoice backfill
*Blockers*
- Prod deploy of #212 blocked on prod DB credentials from the platform team (request open since Mon)
```

## Before handing it over

Check the draft against what it claims:

- Every Done line traces to a commit, a pull request, an issue, or something the
  engineer said in this conversation.
- Every Next line was agreed by the engineer.
- Blockers is present, and each blocker has an owner and a date, or it says none.
- It fits on one screen.

Then give the engineer the text to paste. Do not post it to a channel, ticket or
tracker yourself: an update goes out under the engineer's name, and once posted it
cannot be taken back.
