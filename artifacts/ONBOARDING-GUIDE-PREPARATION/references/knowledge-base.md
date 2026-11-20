# Building the project knowledge base

Read this before drafting the first part of the guide, and before refreshing a
knowledge base that already exists. It covers how each section is built, the
template, and how the knowledge base is kept current. "Who to ask about what" has
its own reference, [who-to-ask.md](who-to-ask.md), because a raw count of commits
misleads in ways that take a page to correct.

## What the project is for

State the goal in two or three sentences: what the system does, for whom, and how
success is judged if a source says so. Take it from what was written for that
purpose: the opening of the README, a project charter or vision page, the
description of the tracker project or its top-level epics, the wiki space's home
page. Paraphrase closely and cite. Do not derive the goal from the code. Code
shows what the system does, not what it is for: a pipeline that loads twelve
sources does not say which of them the business depends on. Where sources
disagree, such as a README that still describes the pilot's scope, give both with
their dates.

## How it is built

List the main modules: the repositories, and inside each the components a change
would be made in, such as a dbt project's layers, the DAG folder, a service or a
shared library. For each, give its path, one sentence on what it does, and what it
connects to and how, as found in [How the repositories fit
together](../SKILL.md#how-the-repositories-fit-together). A text diagram helps once there are
more than four or five.

The build and dependency files are the most reliable source here: workspace and
package manifests, `dbt_project.yml` and `packages.yml`, Compose services,
infrastructure code, CI jobs. They say what is actually built and wired together.
Architecture documents and diagrams say why, and are more often out of date. The
layout and the import graph fill in the rest. Mark each statement as documented,
with the document, or inferred from code, with the paths it was inferred from. The
reader needs the difference: a documented boundary is one the team agreed to,
while an inferred one may be an accident the team is about to fix. Where a diagram
and the build files disagree, give both and add the conflict to the gaps.


## Who to ask about what

Built as described in [who-to-ask.md](who-to-ask.md).

## Decisions and where they landed

A newcomer's most expensive mistake is undoing a decision they did not know about.
List the decisions that shaped the current system, each with its date, where it is
recorded and where it landed in the code, so the reader sees both the reason and
the result. Look for them in:

- decision records and design documents in the repositories (`docs/adr/`,
  `docs/decisions/`, `rfcs/` and the like) and on the wiki pages in the plan;
- merged pull requests whose descriptions argue for an approach, when the code
  host is in the plan;
- tickets and epics that record a choice, from the tracker project in the plan;
- commits whose message records one:

```bash
git log --no-merges -i -E --grep='decid|instead of|switch(ed)? to|replac|migrat|deprecat' \
  --format='%ad %h %s' --date=short | head -40
```

For each, link where it landed: the commit or pull request that carried it out and
the path where it lives now. A record whose implementation cannot be found, or that
the code now contradicts, stays in the list with that finding. Either the decision
was reversed without a new record or it was never carried out, and only the team
knows which. Give the status the record itself states, such as accepted or
superseded, and do not judge whether the decision still holds.

Keep each to one line and a link. The record holds the reasoning, and a summary
that drops its rejected alternatives is how a rejected option gets proposed again.
Where an important part of the design has no record at all, say so in the gaps.
Writing that record is work for project-documentation, not something to
reconstruct here.

## Business rules, where documented

How the project computes what the business cares about, such as what counts as an
active customer, when revenue is recognised or how late-arriving data is treated,
is what newcomers most need and most often get wrong. Include it only where it is
written down: model and column descriptions, metric or semantic-layer definitions,
a glossary, wiki pages, the acceptance criteria of tickets in the plan. Link each
with a one-line summary.

Do not read a business rule out of the code and present it as the rule. The code
shows what is computed; it cannot show whether that is what was intended. A
newcomer told that "active means a login in the last 30 days" will defend it in
review, even where that line is the bug. Where a rule exists only in code, write
"only in code: `<path>`; the intended rule is not documented" and add it to the
gaps. Where nothing is documented, one line says so.

## How it got here

A newcomer also needs to know what was done before. Much of a project that looks
odd on first reading is the remainder of an earlier decision: a second ingestion
path left over from a migration, a directory kept for one client, a retry limit
set after an incident. Without that history the reader either "fixes" something
that was deliberate or proposes an approach the team already tried and reverted.

Write a short history from the sources in the agreed plan only: the repositories'
history, past epics and tickets, release notes and changelogs, decision records and
docs, and chat history only for channels the person named. The repositories give
the skeleton:

```bash
git tag --sort=creatordate --format='%(creatordate:short) %(refname:short)'
git log --reverse --format='%ad %h %s' --date=short | head -5
git log --diff-filter=D --name-only --format= | cut -d/ -f1-2 | sort | uniq -c | sort -rn | head -15
git log -i --grep='^revert' --format='%ad %h %s' --date=short | head -20
```

These show the releases, when the project started, which areas were removed and
what was tried and undone. Closed epics, release notes, changelogs and decision
records then say what each step was for. Keep it to the five to ten milestones that
explain the current state, each dated and with its source, and link to the longer
records instead of retelling them.

Where the reason for a change is not recorded in any of these, write that it is not
recorded and add it to the gaps. Where no history source was available
at all, for example a shallow clone and no tracker access, say so in one line
instead of reconstructing a history from the code's current shape. A plausible
story about why the project was split in two is exactly what a newcomer repeats as
fact.

## The template

```markdown
# <project>: project knowledge base
Built on <date> from <repository>@<sha> (one per repository).
Who-to-ask window: <since> to <date>.
Sources read: <the part of the agreed plan the whole team can see>.
Regenerate: on each newcomer's run, and after <structural changes>; see the
dates above.

## What the project is for
Two or three sentences, each with its source, or one line saying no source
states it.

## How it is built
Modules with their paths, what each does and how they connect (a text diagram
if it helps). Each marked documented (<document>) or inferred (<paths>).

## Who to ask about what
Window, and what was left out (merges, bots, named mass changes).
| Module | Path | Ask about | Who (latest change) | CODEOWNERS | Reviewers |

## Decisions and where they landed
| Decision | Date | Record | Landed in | Status |

## Business rules
Documented rules, each linked with a one-line summary; rules found only in code
marked as such; or one line saying none are documented.

## How it got here
Five to ten dated milestones that explain the current state, each with its
source, or one line saying no history source was available.

## Shared code to reuse
| Name | Path | Use it for | Example call |

## Working here
Setup, run, test: exact commands, working directory, source of each
(CI file, Makefile), and whether it was run or only read.
How work moves: ticket, branch name, pull request, review, release.

## Where knowledge lives
| Source | What it holds | Seen in |

## Gaps
What the sources do not say or contradict, each with what was found.
```

## Keeping it current

The header records the date, the commit of each repository and the who-to-ask
window, so a reader can see how old the knowledge base is before trusting it. On
each newcomer's run, compare it with the repositories as they are now and propose
changes to the sections that drifted, leaving the rest alone. Most of it still
holds, which is what makes the second run cheap. "Who to ask about what" is the
exception: it is relative to its window, so rebuild it every run with the window
ending that day, and have the lead check it again.

Between newcomers, regenerate "How it is built" and the decisions after a
structural change: a module added or removed, a new decision record, a migration
finished. Decisions are appended and marked superseded, never rewritten, for the
same reason decision records are immutable.
