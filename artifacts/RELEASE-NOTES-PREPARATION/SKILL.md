---
name: release-notes-preparation
description: Preparing release notes for a version from what actually shipped - the commits, merged pull requests and tickets between the previous release and this one - rewritten for the people who use the product, with required actions first and internal changes left out, and every line traced to a change in the release. Use when asked for release notes, a changelog entry or a release announcement.
---

# Preparing release notes from what shipped

Release notes go wrong in two ways. Written from memory or from the sprint board,
they announce things that are not in the release: a change that was reverted, one
merged after the cut, one that shipped switched off. Written from the commit log,
they are accurate and unreadable: "replace defaults with validation tags" is true
and tells the person who configures the product nothing.

Both are avoided by doing the work in two separate steps. First establish exactly
what the release contains, from the repository. Then rewrite that list for its
reader. Two rules hold the result together:

- **Every line traces to a change inside the release range.**
- **Every line says what the reader gets, or what the reader must do.**

## Establish the release

Three facts, all from the repository:

**The version.** Read it from the file that defines it: the package manifest, the
version file, the chart. A branch name or a ticket title is somebody's intention.

**The previous release.** Usually the latest tag reachable from the release commit:

```bash
git describe --tags --abbrev=0 <release commit>^
```

**The unit being released.** In a repository that releases several components
independently, each with its own version file and changelog, the range is the
component's, not the repository's. Scope every command to its path, or the notes
pick up a neighbour's changes:

```bash
git log <previous>..<release> --first-parent --date=short --format='%h %ad %s' -- <path>
```

State the range you used at the top of the draft. If no previous tag exists, ask
what the last release was instead of taking the whole history.

## Gather what is in the range

Commits give the list; pull requests and tickets give the meaning.

```bash
git log <previous>..<release> --format='%h %s' -- <path>
gh pr list --state merged --base <release branch> --search 'merged:>=<date of previous release>' \
  --json number,title,body,labels,mergedAt,url
```

With squash merges the pull request title is the commit subject and its number is in
parentheses at the end. Read the pull request body and the linked ticket for each
change that a user could notice: the commit subject says what was done to the code,
the ticket says what was wrong for the user.

If `gh` is missing or not signed in, work from the commit log and say in the draft
that pull request descriptions were not read. Do not sign in on the engineer's
behalf.

Four things in a range mislead, and each puts a false line in the notes:

- **Reverts.** A change and its revert inside the same range cancel out. Search the
  subjects for `Revert` and drop both. A revert of something released earlier is a
  real entry: the behaviour went back.
- **Backports.** A fix cherry-picked into an earlier patch release has already been
  announced. Check the previous notes before announcing it again.
- **Changes that shipped switched off.** Code behind a flag that is off by default
  is in the release, and the feature is not. Leave it out, or say how to enable it
  if that is intended for users.
- **Merged after the cut.** A date search can return pull requests merged after the
  release commit. The commit range is the authority; drop anything not in it.

## Decide who reads them

The same release reads differently to different people, and notes written for
everyone serve nobody.

| Reader | Wants to know |
|---|---|
| People who use or configure the product | What is new, what behaves differently, what they must change |
| Developers who integrate with it | Changed interfaces, deprecations, upgrade steps |
| Stakeholders following delivery | What was delivered, in plain words |

When the request does not say, write for the people who use and configure the
product. They are the usual audience and the one that commit-style notes fail. Ask
only if the repository gives no hint, such as an existing changelog whose earlier
entries show the register.

## Sort the changes

Use the headings of Keep a Changelog, and only those that have entries:

- **Added**: new capabilities.
- **Changed**: existing behaviour that is now different.
- **Deprecated**: still works, will be removed.
- **Removed**: no longer available.
- **Fixed**: defects corrected.
- **Security**: vulnerabilities addressed.

Anything the reader has to act on goes above all of these, under its own heading,
with the action stated: a setting to change, a migration to run, an interface to
stop using. A reader who stops after three lines must have seen it.

Then compare the entries with the version number. A removal or an incompatible
change under a patch version is a finding to raise with the engineer. It is not
something to smooth over in the wording, and not a reason to change the version
yourself. Whether the version was bumped at all, and whether tests, coverage and
lint pass, is a separate check made before the notes are written; for a Go module
see [go-module-release-gates](../GO-MODULE-RELEASE-GATES/SKILL.md).

## Write each line for the reader

**Say what changed for the user, in their words.**

```text
No:   Replaced SetDefaults() with validate:"min=1,max=10" struct tags
Yes:  Retry count is now checked when the configuration is saved, so an invalid
      value is rejected in the form instead of failing at run time
```

| Instead of | Write |
|---|---|
| Fixed nil pointer in `archive.go` when `ArchivePath` is empty | Runs no longer fail when no archive folder is configured |
| Added context propagation to SFTP dial | Cancelling a run now stops it promptly instead of waiting for the server |

Function names, types, file names, error codes and library names mean nothing to
someone who does not read the code. If a line cannot be written without them, it is
probably an internal change. The name of a setting as the user sees it in the
product is fine: that is their vocabulary.

**Leave internal changes out.** Refactoring, test changes, dependency bumps with no
visible effect, dead code removed: a reader cannot act on any of it, and each such
line makes the real ones harder to find. Do not add a heading just to hold cleanup.

**One improvement, one line.** Three commits that each fixed part of empty-response
handling are one line about empty responses. The reader experiences the improvement
once.

**One sentence per line, about thirty words at most.** A line that needs more is
describing how it works, or is two lines. The reference documentation explains; the
release note announces.

**Describe a fix by its symptom.** "Files larger than 2 GB no longer fail on upload"
is recognisable to the person who hit it. The cause is in the pull request.

**Keep raw performance figures out.** Benchmark numbers depend on the machine that
produced them and a reader cannot use them. When speed was the point of the release,
give the effect a user sees: "large exports import in about a third of the time".

**A first release describes capability, not change.** There is no earlier version
to compare with, so "now", "no longer", "instead of" and "previously" refer to
drafts the reader never saw. They leak in from review rounds. State what the product
does. A contrast between two present behaviours is fine: "skips files it cannot read
and lists them in the run summary" describes what happens, not what used to.

**Security entries say what to do.** Name the affected versions and the action,
upgrade or reconfigure. Public advisory identifiers are fine, for readers who look
them up; module paths and dependency version numbers are not the reader's concern.
Leave out the detail that would help someone exploit an installation that has not
upgraded yet.

## Heading, date and length

The heading carries the exact version and the release date in ISO form:

```text
### [2.7.0] - 2026-11-13
```

It has to match the released version character for character. Release pipelines
commonly look for a heading with that exact version and stop the release when it is
missing; where nothing checks it, the notes end up published under the wrong
version. Follow the existing entries for anything else the heading carries, such as
a runtime version, and for the heading level: Keep a Changelog puts versions at `##`
and change types at `###`, and a changelog kept as a section of a README sits one
level lower.

Find out where the notes are published before finishing. An entry that is also
posted to a chat channel is bound by that channel's message limit. A Slack text
block holds 3,000 characters, and a longer message may be cut or not delivered at
all, so the release goes out with no notes. Count the entry from its heading to the
next one and stay under the limit with a margin. When it is too long, merge lines
and move detail to the documentation, which has no limit.

## Where the entry goes

Read the existing changelog first. It settles the heading level, the order and the
register. Then:

- put the entry directly under the changelog's header and any preamble, above the
  previous version, newest first;
- if the file keeps an `[Unreleased]` section, move its items into the new entry,
  after checking each against the range, and leave `[Unreleased]` empty above it;
  do not write a second list beside it;
- if an entry for this version already exists, show it and ask whether to replace
  it or leave it; do not merge the two silently;
- leave earlier entries as they are. They record what was said at the time, and
  people have already read them.

A changelog entry, a chat announcement and customer-facing notes may all be wanted
for one release. Build them from the same sorted list so the facts match, and vary
only the length and the markup.

## Show what was left out

Under the draft, list the changes in the range that did not become a line, each with
the reason:

```text
Left out as internal: #412 refactor of the retry helper, #415 test fixtures
Left out as reverted in range: #409 and its revert #414
Unsure: #417 changes the default page size from 100 to 200 - is this visible to users?
```

Leaving something out is a judgement, and this makes it reviewable. The engineer
knows that the "internal" refactor changed an error message users see. Without the
list, nobody finds out until a user does.

Ask in the same message for what the repository cannot show: known issues worth
stating, anything that shipped through configuration and not code, and the
publication channel if it is not evident.

## Before handing it over

- The version comes from the version file, and the heading matches it exactly.
- The range is stated and scoped to the unit being released.
- Every line traces to a commit or pull request in the range; nothing reverted,
  already announced or switched off is presented as new.
- Required actions come first, each with the action spelled out.
- No line names a function, type, file or internal error code.
- Only headings with entries appear, and each line is a single sentence.
- The entry is within the length limit of the channel it is posted to.
- The left-out list is under the draft.

Hand over the text, or write it into the changelog file when asked. Tagging,
publishing and posting the announcement stay with the engineer: a release note goes
out under the team's name and cannot be recalled once people have read it.
