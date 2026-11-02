# Authoring artifacts

How to add an artifact to this catalog and get its matching metadata right.

This is the task-shaped companion to [`README.md`](../README.md), which is the reference: the `index.json` field table, the one-artifact-one-subtree contract, the path rules, and how consumers fetch. Read it first. This guide does not repeat it — it covers the decisions you have to make and the ways they go wrong.

For a shipped artifact to copy from, read [`artifacts/ETL-DECOMPOSITION`](../artifacts/ETL-DECOMPOSITION) — one dimension, one topic, `on-demand`, which is the shape most artifacts should have.

## What belongs in the catalog

**Scope is the whole big-data stack**, not only the frameworks and topics the
vocabulary holds today. The vocabulary describes what exists; a value it lacks
is part of the work of adding an artifact (see [The current
vocabulary](#the-current-vocabulary)), not a reason to turn the artifact down.
Power BI is out of scope, which is why `power-bi` is deliberately absent from
`frameworks`.

**The catalog assumes open-source tooling, dbt Core in particular.**
`DBT-COLUMN-LINEAGE` is the single artifact that needs dbt Cloud and an MCP
server. Content that only works on dbt Cloud, Fusion or another paid tier, or
that mostly wraps a vendor CLI, is tooling rather than knowledge and does not
fit.

**An artifact ships no agent hooks or settings.** It is `SKILL.md` plus
metadata, installed into a skills directory for Claude Code, Codex and Cursor
alike. Hooks live in agent settings, which the installer does not write, and
they exist in Claude Code only. A skill that writes to a database instead says
in `SKILL.md` what it changes, reads by default, confirms each write, and
recommends a least-privilege role. The database role is the real boundary.

**Write prose that explains why.** A rule the reader understands survives cases
the author did not foresee; a Do/Don't list does not. "Don't put heavy logic in
the DAG file" is the shape to avoid. Explaining the scheduler's parse loop that
makes it matter is the shape to aim for. This is also why a popular external
skill is often rejected as a duplicate even where our coverage of the topic is
thinner.

### Adopting a third-party skill

Check a candidate in this order, cheapest disqualifier first: licence, its path
in the source repository, the body of its `SKILL.md`, coupling to a CLI or paid
product, and install count last. Install count and vendor reputation predict
neither relevance nor whether the licence lets us use it.

- Read the licence with `gh api repos/OWNER/REPO --jq '.license.spdx_id'`.
  `NOASSERTION` means a non-standard licence, not a missing one; open `LICENSE`.
- GPL-3.0 and licences restricted to a vendor's own services block adoption
  into this MIT catalog. Apache-2.0 is usable but needs its own section in
  [`NOTICE`](../NOTICE) with the full licence text and a note of what was
  modified.
- Defects found in the source are fixed during adaptation, not carried over.

A third-party skill reaches the catalog in one of two ways. **Adapted**: it is
rewritten into a copy we own and recorded in `NOTICE`, as the AltimateAI and
Docker skills were. **Referenced**: the author's files are carried unchanged,
pinned to a commit, as an [upstream artifact](#upstream-artifacts). Which one
fits is the first question in that section.

## The five decisions

Everything else about an artifact is mechanical. These five determine whether anyone ever sees it.

Schema 2 adds two more authoring decisions for questionnaire-ready artifacts:
scope and the presentation card. This catalog is schema 2. Schema 1 remains
valid for previously published tags, and the validator still accepts it.

### 0. `scope` — team or personal

| Value | Stored and reproduced as |
|---|---|
| `project` | Reviewed project selection, shared with the team and CI |
| `user` | Local developer overlay, absent from CI |

Every schema 2 artifact declares one. A user artifact must be `on-demand`:
personal tools require explicit consent and cannot claim baseline installation.

### 1. `strength` — `always` or `on-demand`

| | Installed when |
|---|---|
| `always` | Every project that passes `applies_to`, whether or not anyone asked for it |
| `on-demand` | Only when the artifact's `topics` intersect what the team said they wanted |

**Default to `on-demand`.** `always` is a claim on every matching user's agent context, and the burden of proof is on you.

The test:

> Would a developer who never heard of this artifact be right to have it?

If the honest answer is "only if they're doing X", then X is a topic and this is `on-demand`. `always` is for baseline hygiene — the thing you would be annoyed to find missing on a project you had never seen before.

**Why this matters more than it looks.** The failure mode is ordinary and predictable. Every author believes their artifact is essential. Marking it `always` costs *you* nothing — it costs every downstream user a slice of context they did not ask for. Repeat that across authors and the baseline set grows until it is effectively the whole catalog. At that point nothing breaks: sparse checkout still works, the installer still reports success, and the ~91% transport saving quietly returns to zero. Nobody gets an error. That is exactly the "success with missing value" outcome this system is built to avoid, arriving from the other direction.

There is an agreed ceiling of **≤ 15 `always` artifacts per typical profile**. **Nothing enforces it.** The validator does not count `always` artifacts and will not complain at any number. Review is the only thing standing between the catalog and baseline bloat.

### 2. `applies_to` — which dimensions to declare

Every dimension you declare must intersect the profile. An omitted dimension means *"I do not care about this dimension"*.

So **declaring more dimensions makes your artifact narrower, not better described.** This is the instinct to fight. Writing

```json
"applies_to": {
  "languages": ["typescript"],
  "frameworks": ["nestjs"],
  "layout": ["monorepo"],
  "agents": ["claude-code"]
}
```

feels thorough. What it actually says is: *skip me unless the project is TypeScript **and** NestJS **and** a monorepo **and** using Claude Code.* Drop a dimension unless its absence would make the artifact wrong.

For a genuinely universal artifact, write it explicitly:

```json
"applies_to": {}
```

Absent is not the same as `{}`. Omitting the field is an error, so that "applies to everything" can never be confused with "the author forgot".

### 3. `topics` — which intents select it

Values come from the closed `topics` vocabulary published in `index.json`. An `on-demand` artifact with **no** topics can never be selected by any profile — it is dead content in the catalog. The validator rejects it outright; this is not a subtle bug you have to reason about.

An `always` artifact does not need topics. Write `"topics": []`.

In schema 2, topics are the broad questions used for progressive disclosure.
They decide which cards the user opens, not which complete category is installed.
The final selection stores exact artifact ids.

### 4. `presentation` — the informed-consent card

Every schema 2 `on-demand` artifact declares:

```json
"presentation": {
  "name": "Make generated prose read naturally",
  "summary": "Removes the patterns that make generated text read as machine-written.",
  "benefits": [
    "Removes repetitive AI phrasing",
    "Preserves meaning"
  ]
}
```

Keep the name and summary short, and follow [Naming](#naming) for the name. Benefits must be concrete outcomes the skill
actually provides. The questionnaire uses this object verbatim and never reads
`SKILL.md` to invent benefits. Empty cards, empty benefits, and scalar
`presentation` values fail validation.

### Optional: `requires` — what has to be in place before it runs

Most artifacts are instructions and need nothing beyond the agent. Omit
`requires` for those. Declare it when the artifact's own workflow runs a
command or connects somewhere:

```json
"requires": {
  "tools": ["dbt Core CLI with the project's warehouse adapter"],
  "access": ["Warehouse credentials in profiles.yml for a target the agent may build into"]
}
```

The two kinds are split by what the user has to do. `tools` is something they
install themselves; `access` is credentials, connections or roles, which they
usually have to request from an admin. Declare either or both, each as a
non-empty list of short strings. Write the specific grant when the `SKILL.md`
names one (a role, a privilege, an environment variable) rather than "access to
Snowflake".

Leave out what is only illustrative. A command shown as an optional check is not
a requirement; a command the workflow cannot finish without is.

`requires` is not matched by the installer: it does not narrow where the
artifact installs (that is `applies_to`). The catalog map shows it on the
artifact card, with Russian text under `req` in `catalog-map/ru.json`. The
validator checks its shape, and with `-CatalogRoot` it rejects an artifact that
ships a `scripts/` directory or a `requirements.txt` without declaring
`requires`. It cannot tell whether the list is complete.

### Optional: running only on the user's command

An agent picks most artifacts by itself, from their `description`. A few should
run only when the user types their command, because running unasked would get in
the way: [`REQUEST-REFINEMENT`](../artifacts/REQUEST-REFINEMENT) stops before any
work to show a rewritten request, which is welcome when asked for and an
interruption on every request that was already clear. Such an artifact says so in
two places, because the agents read different files:

- `disable-model-invocation: true` in the `SKILL.md` frontmatter. Claude Code and
  Cursor honour it: the agent does not invoke the skill itself, and the user runs
  it as `/<name>`.
- `agents/openai.yaml` in the artifact directory, setting
  `allow_implicit_invocation: false` under `policy`. Codex ignores the frontmatter
  field and reads this file instead; the user runs the skill as `$<name>`.

Ship both. The installer copies an artifact's directory byte for byte into every
agent's target, so both arrive unchanged, and an artifact with only the
frontmatter field is picked automatically under Codex. The validator reads
neither, so review is what catches a missing one.

The `description` of such an artifact is read by a person choosing a command, not
by an agent deciding when to act. It ends by saying how to run it rather than with
a "Use when ..." sentence.

## Naming

An artifact has three names, and readers meet them in different places: the
**id** (also the directory name and what a profile stores), the **`name`** in the
`SKILL.md` frontmatter (what an agent lists and what a user types in a slash
menu), and **`presentation.name`** (what the setup questionnaire and
[`docs/skill-catalog.md`](skill-catalog.md) show). All three have to tell a reader
what the artifact *does*, without opening it. The catalog was renamed wholesale
for `v1.0.0` because many of them named a subject area instead; these rules are
what keep that from happening again.

**The id is `[PLATFORM-]OBJECT-ACTION`, written as a noun phrase.** Upper case,
hyphen-separated. Lead with the platform when there is one (`DBT-`,
`SNOWFLAKE-`, `DOCKER-`), so related artifacts sort together. Then name the
task: `SNOWFLAKE-QUERY-REWRITE`, `DBT-INCREMENTAL-STRATEGY`,
`PIPELINE-CHECK-SELECTION`.

- **Name the task, not the input.** `SNOWFLAKE-QUERY-BY-ID` described what the
  artifact is given; `SNOWFLAKE-QUERY-PROFILE-DIAGNOSIS` describes what it does
  with it.
- **Name the task, not the subject area.** `AIRFLOW-DAG-CONVENTIONS` could hold
  anything about DAGs; `AIRFLOW-DAG-STRUCTURE` says which part. Words such as
  *conventions*, *patterns*, *strategies*, *foundations*, *safety*,
  *guardrails* and *handling* are a signal to look again. They are not banned:
  `SENSITIVE-DATA-HANDLING` was reviewed and kept, because the object carries
  the meaning.
- **Do not promise what the artifact does not do.** `DBT-MODEL-CREATION` read as
  scaffolding; the artifact is a build-and-verify loop, so it became
  `DBT-MODEL-BUILD-VERIFY`.

**The `SKILL.md` `name` is the id in lower case.** `SNOWFLAKE-QUERY-REWRITE` →
`snowflake-query-rewrite`. The validator enforces this when run with
`-CatalogRoot`. An [upstream artifact](#upstream-artifacts) is the exception: it
keeps its author's name, which must instead be unique across the catalog.

**`presentation.name` is a verb phrase: verb, object, and what sets it apart.**
"Rewrite Snowflake SQL without changing results", not "Snowflake query
rewriting". The distinguishing clause is the part that matters; it is what lets
a user choose between neighbours.

**The `SKILL.md` `description` says what the artifact does, then when to use
it.** End it with a "Use when ..." sentence naming the situation that should
trigger it. An agent picks a skill mostly from this line, so a description that
only summarises the content leaves the agent guessing when it applies. This does
not apply to an upstream artifact, whose `SKILL.md` is its author's, or to one
that [runs only on the user's command](#optional-running-only-on-the-users-command).

**The neighbour test.** Before settling a name, find the artifact closest to
yours in the same area: `ERROR-DIAGNOSIS`, `DBT-BUILD-FAILURE-DIAGNOSIS` and
`DATA-INCIDENT-TRACING` all deal with something going wrong. If a reader cannot
tell from the two names which one fits their situation, the name is not
finished.

**Renaming a published artifact is a breaking change.** The installer keys
installed copies by id, so a new id is a different artifact: the old copy is
removed and the new one installed, an edited copy is kept beside it, and
feedback filed under the old id no longer matches. Get the name right before the
first tag. When a rename is unavoidable, batch it into a major release and say
so in the release notes.

## The current vocabulary

Taken from `index.json` at the time of writing. **`index.json` is the source of truth — check it rather than this table**, which goes stale the moment the vocabulary grows.

| Dimension | Values |
|---|---|
| `languages` | `typescript`, `javascript`, `python`, `csharp`, `go`, `sql` |
| `frameworks` | `nestjs`, `react`, `django`, `aspnet`, `airflow`, `dbt`, `duckdb`, `spark`, `trino`, `snowflake`, `databricks`, `docker`, `terraform`, `terragrunt`, `dataform`, `bigquery` |
| `layout` | `monorepo`, `single` |
| `agents` | `claude-code`, `codex`, `cursor` |
| `topics` | `code-review`, `testing`, `documentation`, `refactoring`, `orchestration`, `data-modeling`, `data-quality`, `ingestion`, `performance`, `debugging`, `writing`, `development-process`, `security`, `containerization`, `infrastructure`, `database-administration`, `research` |

`frameworks` is the loosest of the dimensions: it holds anything that identifies the
stack beyond the language, so orchestrators (`airflow`), transformation tools (`dbt`)
and engines (`duckdb`, `spark`, `trino`) all live there. Calling dbt a "framework" is
a stretch, and the accurate name would be something like `tools`. Renaming a
*dimension* is the installer's half of the contract and moves `schema_version`, so
the loose name is kept deliberately rather than paid for with a schema bump.

A value not in the vocabulary is a CI failure. That is deliberate: the alternative is an artifact that passes review and then matches nothing forever, with no error anywhere.

Adding a value is half of a contract; the installer holds the other half. The
installer reads the vocabulary from the index, but its project scanner detects
only the values it was written for, so a new value reaches a profile through the
questionnaire alone until the scanner learns it. Say in the PR that the
vocabulary changed, so the release notes carry it and an installer issue can be
filed. A new topic is also not applied to existing artifacts by itself: check
which of them, including ones merged in parallel, should declare it.

## Hard rules

- **Comparison is case-sensitive**, for values and for dimension names. `TypeScript` does not match `typescript`, and `Languages` is not a dimension. Both fail CI. The vocabulary is lower-case throughout.
- **`applies_to` and `strength` are required.** `applies_to: {}` must be written explicitly.
- **`applies_to` must be an object.** `"applies_to": "typescript"` is rejected — a scalar has no dimensions to intersect, so the installer would treat the artifact as applying to every profile.
- **Ids must be unique case-insensitively.** They become directory names; on Windows and default macOS `AS-0001` and `as-0001` are one directory, and one artifact silently overwrites the other.
- **The index entry and the artifact's own `metadata.json` must agree.** The index is authoritative for matching — it is the only file a consumer holds when it decides what to fetch. **Nothing checks this agreement.** A `metadata.json` that disagrees with the index passes CI, and the index wins at install time.
- **Never set `fixture: true`.** It is only for the `AS-SPIKE-*` transport fixtures, and it exempts an artifact from *all* matching validation — though not from the [path rules](../README.md#path-rules), which apply to every entry because a broken path breaks the checkout for everyone. On a real artifact it would silently hide it from every install. The validator rejects it on any non-`AS-SPIKE-*` id, which is the only reason a typo here is survivable.
- **The directory is named exactly for the id.** `source_path` must be `artifacts/<id>`, case included, and the `SKILL.md` frontmatter `name` must be the id in lower case. The validator rejects both mismatches (the second only with `-CatalogRoot`). The `AS-SPIKE-*` transport fixtures are exempt from the directory rule, and an [upstream artifact](#upstream-artifacts) from the name rule.
- **One artifact is exactly one self-contained directory.** See [the subtree contract](../README.md#the-subtree-contract). Breaking it does not fail loudly — the clone succeeds and the artifact arrives incomplete.
- **Never edit a file in an upstream artifact.** Its directory is the author's bytes at a pinned commit, and CI fails on any difference. Change the pin, or adapt the skill instead.

## Upstream artifacts

An upstream artifact is a third party's skill carried as the author wrote it:
their files, unchanged, pinned to one commit of their repository. The catalog
adds only an index entry, an `UPSTREAM.json` recording where the files came
from, and a `LICENSE` when the author's directory has none. The author's later
fixes arrive by moving the pin, and nobody here has to maintain the text.

The installer does not know the difference. It reads `source_path` and ignores
`upstream`, so the author's repository is fetched when the catalog is built,
never on a developer's machine. The design is in the installer repository's
spec, `docs/superpowers/specs/2026-10-09-upstream-artifacts.md`.

### Adapt or reference

Reference a skill only when the answer to the first question is yes. Otherwise
adapt it into a copy we own, as described in [Adopting a third-party
skill](#adopting-a-third-party-skill).

- [ ] **Would [`PROJECT-ADAPTATION`](../artifacts/PROJECT-ADAPTATION) be enough
  to make it correct in a typical target repository?** That skill appends a
  `Project context` section with the repository's paths, commands and naming,
  and leaves the rest of `SKILL.md` alone. If the skill's rules, not just its
  examples, assume a structure we do not want to teach, no appended section
  fixes that, and the skill has to be adapted.
- [ ] The licence is `MIT`, `Apache-2.0`, `BSD-2-Clause` or `BSD-3-Clause`. The
  validator rejects anything else.
- [ ] The repository is on GitHub. Other hosts are not supported yet.
- [ ] The skill lives in one directory with `SKILL.md` at its root, and does not
  depend on files outside that directory. Anything outside it is not installed.
- [ ] Nothing in the skill breaks [What belongs in the
  catalog](#what-belongs-in-the-catalog), hooks in particular. Being the
  author's text exempts it from house style, not from scope.

A skill that passes is still checked like any candidate (licence first, install
count last), and its `requires` still has to be complete: read the scripts, not
only the frontmatter.

### Adding one

1. **Write the index entry.** Everything that drives matching and the
   questionnaire is ours, decided exactly as for any artifact: `id`, `version`,
   `applies_to`, `strength`, `topics`, `scope`, `presentation` and `requires`.
   The id and `presentation.name` follow [Naming](#naming); the author's
   frontmatter `name` and `description` are left as they are. Then add the
   `upstream` object:

   ```json
   "upstream": {
     "repo": "https://github.com/<owner>/<repo>",
     "commit": "<full 40-character lower-case SHA>",
     "path": "skills/<name>",
     "license": "MIT",
     "exclude": ["assets/"]
   }
   ```

   `repo` is written exactly in that form: no `.git` suffix and no SSH form, so
   one repository has one spelling in the index and in `NOTICE`. `commit` is a
   full SHA, never a branch or tag, because a SHA is the only reference that
   cannot be moved under us. `path` is the skill's directory in that
   repository. `exclude` is optional; see below.

2. **Run the sync.**

   ```powershell
   ./scripts/sync-upstream.ps1 -Id <ID>
   ```

   It clones the repository without blobs, checks out only `path` at
   `commit`, and replaces `artifacts/<ID>/` with those files minus `exclude`,
   plus `UPSTREAM.json` and, when needed, `LICENSE` copied from the
   repository root. It refuses, and leaves the directory as it was, when the
   result would break a catalog rule: a path rule, no `SKILL.md` at the root,
   a `scripts/` directory or `requirements.txt` with no `requires` on the
   entry, a symbolic link, no licence file anywhere, or an `exclude` item that
   matches nothing. The message names the author's file at fault.

3. **Add a `NOTICE` entry** for the repository if it has none: the URL, the
   licence, the copyright line, which artifact comes from which path, what
   `exclude` leaves out, and the licence text in full. The validator checks
   that `NOTICE` mentions `upstream.repo`.

4. **Add the catalog map entries**, as for any new artifact: the group in
   `catalog-map/groups.json`, Russian text in `catalog-map/ru.json` including
   `req`.

5. **Run the validator, commit the artifact, then verify.**

   ```powershell
   ./scripts/validate-catalog.ps1 -IndexPath ./index.json -CatalogRoot .
   # commit artifacts/<ID>, index.json, NOTICE and catalog-map/, then:
   ./scripts/sync-upstream.ps1 -Verify
   ```

   `-Verify` compares the git blob ids committed in `HEAD` with the author's
   tree at `commit`, so it has to run after the commit. It fetches trees only,
   but it does need network access to GitHub. CI runs it on every push.

No `metadata.json` is added. The directory holds the author's files and our two,
and the index is the only place the matching fields live.

### Leaving files out

`exclude` lists files and directories to leave out, relative to `path`. An item
ending in `/` is a directory; one without names a file, or a directory and
everything under it. It removes whole files and never edits one, so the author's
text stays the author's. `UPSTREAM.json` records the list, and `-Verify`
applies it, so an excluded file that reappears fails CI as surely as an edited
one.

Use it for what a skill ships but does not use, such as the demo media that
make up most of `last30days`. **Never exclude anything `SKILL.md` or the files
it references point at.** The skill would install without error and then fail
when the agent follows the reference. The validator cannot tell what a
`SKILL.md` refers to, so this is review's job: grep `SKILL.md` and its
references for every excluded path before approving.

### Moving the pin

A new commit is a PR that changes `commit` and bumps `version` together, then
re-runs the sync and commits the result. Re-check what the entry claims about
the skill against the new commit, `requires` in particular: an author adding a
dependency does not touch our index.

An installed copy changed by `PROJECT-ADAPTATION` counts as locally edited, so
`accelerator update` keeps it and reports it as retained. `update -Force`
replaces it and drops the `Project context` section; run the adaptation again
afterwards. This holds for every artifact, but upstream artifacts hit it more
often, because moving the pin is how the author's fixes arrive.

### Line endings

If `-Verify` reports a file that differs and nobody edited it, the catalog's
`.gitattributes` normalised its line endings on commit: an author's CRLF file
committed under `* text=auto` is stored as LF, and its blob id is no longer the
author's. Do not edit the file. Add a line to `.gitattributes` for that
artifact and re-add it:

```text
artifacts/<ID>/** -text
```

```powershell
git add --renormalize artifacts/<ID>
```

## Worked example

Adding a TypeScript code-review convention artifact, end to end.

### The decisions, made first

**`strength`.** Apply the test: would a developer who never heard of this be right to have it? No — this is one team's review conventions, useful when someone is reviewing TypeScript and noise otherwise. "Only if they're doing code review" means code review is a topic. → **`on-demand`**.

**`applies_to`.** The conventions are about TypeScript syntax and idiom, so `languages: ["typescript"]` is load-bearing — on a Python project the artifact is wrong, not merely unhelpful. Everything else is not: the conventions hold in React and in NestJS, in a monorepo and in a single repo. Declaring those would narrow the artifact for no gain. → **`{"languages": ["typescript"]}`**, one dimension.

**`topics`.** `code-review`. Not `testing` — the artifact does not talk about tests, and claiming a topic you do not serve is how a team that asked for testing help gets handed something irrelevant. → **`["code-review"]`**.

### 1. The directory

One self-contained directory, named for the id:

```text
artifacts/TS-REVIEW-CHECKS/
  SKILL.md
  metadata.json
```

Nothing outside this directory, no `..` paths, no case-colliding filenames. See [path rules](../README.md#path-rules) — CI enforces them.

### 2. `artifacts/TS-REVIEW-CHECKS/SKILL.md`

The artifact's actual content — what gets loaded into the agent's context.

```markdown
---
name: ts-review-checks
description: TypeScript-specific review checks - what to flag and what to leave alone. Use when reviewing a TypeScript change.
---

# TypeScript review checks

## Flag these

- `any` in a signature. Prefer `unknown` plus a narrowing check at the boundary.
- A non-null assertion (`!`) outside a test. It moves a runtime failure away
  from the code that caused it.
- An exported function with an inferred return type. Inference is fine
  internally; on an export it makes the public shape change silently.

## Leave these alone

- Inferred types on locals and on non-exported helpers.
- `as const` on literal config objects.
```

### 3. `artifacts/TS-REVIEW-CHECKS/metadata.json`

The same matching fields as the index entry. Copy them across exactly — nothing checks that you did.

```json
{
  "id": "TS-REVIEW-CHECKS",
  "version": "0.1.0",
  "source_path": "artifacts/TS-REVIEW-CHECKS",
  "applies_to": {
    "languages": ["typescript"]
  },
  "strength": "on-demand",
  "topics": ["code-review"]
}
```

### 4. The `index.json` entry

Appended to the `artifacts` list:

```json
{
  "id": "TS-REVIEW-CHECKS",
  "version": "0.1.0",
  "source_path": "artifacts/TS-REVIEW-CHECKS",
  "applies_to": {
    "languages": ["typescript"]
  },
  "strength": "on-demand",
  "topics": ["code-review"]
}
```

Who gets this artifact: a TypeScript project whose team asked for code-review help. Not a TypeScript project that asked only for testing help — `on-demand` means the topic has to be wanted. Not a Python project that asked for code-review help — the declared `languages` dimension has to intersect.

### A variant, for contrast

Had this been `always`:

```json
"strength": "always",
"topics": []
```

then every TypeScript project would get it, asked for or not. That is a defensible call for, say, a repository-wide safety convention that a developer would be right to have without knowing it existed. It is not defensible for one team's review taste. When in doubt, `on-demand` — a wrong `on-demand` is invisible, a wrong `always` is on everyone's context budget.

## Check your work before pushing

All three checks below run in CI ([`.github/workflows/validate.yml`](../.github/workflows/validate.yml)). Run them locally first. CI also runs `sync-upstream.ps1 -Verify`, which matters only when you add or change an [upstream artifact](#upstream-artifacts).

### The validator

```powershell
./scripts/validate-catalog.ps1 -IndexPath ./index.json -CatalogRoot .
```

`-CatalogRoot` is what turns on the [path rules](../README.md#path-rules) over the files in your checkout; without it only `index.json` is read. CI passes it, so run it that way locally too.

Passing looks like this — `IsValid: True` and an empty `Errors` list:

```text
IsValid       : True
Errors        : {}
```

`ArtifactCount` and `PathCount` come back alongside those two — how many artifacts the index declared, and how many checkout paths the rules were applied to. `PathCount` is `0` when `-CatalogRoot` was not passed.

Failing prints each fault to the host as it is found *and* returns them in `Errors`. Every fault is collected, so one run shows you everything rather than one typo per push:

```text
ERROR: Artifact TS-REVIEW-CHECKS declares 'TypeScript' in dimension 'languages', which is not in the catalog vocabulary. Allowed: typescript, javascript, python, csharp, go.

IsValid       : False
Errors        : {Artifact TS-REVIEW-CHECKS declares 'TypeScript' in dimension 'languages', which is not in the catalog vocabulary. Allowed: typescript, javascript, python, csharp, go.}
```

The script returns an object; it does not set a non-zero exit code by itself. Check `IsValid`, as CI does.

### The validator test suite

Pester 5.6.1, matching CI:

```powershell
Import-Module Pester -RequiredVersion 5.6.1

$configuration = New-PesterConfiguration
$configuration.Run.Path = './tests'
$configuration.Run.PassThru = $true
$configuration.Output.Verbosity = 'Detailed'

Invoke-Pester -Configuration $configuration
```

Passing:

```text
Tests Passed: <all of them>, Failed: 0, Skipped: 0, Inconclusive: 0, NotRun: 0
```

The run prints a wall of `ERROR:` lines. That is expected — the suite feeds deliberately broken indexes to the validator and asserts it complains. Read the final tally, not the noise.

You only need this suite if you changed the validator. Adding an artifact does not require it, but it is cheap and it is what CI runs.

### Script tests

Some artifacts ship scripts (`TERRAFORM-PLAN-REVIEW/scripts/plan_summary.py`). Their tests live in `tests/test_*.py`, use only the Python standard library, and need no external tools or credentials:

```powershell
python -B -m unittest discover -s tests -p 'test_*.py' -v
```

Run them when you change an artifact's script, and add a test for every bug you fix in one. CI runs them on Python 3.9, the oldest version the scripts support, and on 3.12. If your script needs a newer Python, say so in its docstring and raise the CI version with it.

## Troubleshooting

Every message below is produced by [`scripts/validate-catalog.ps1`](../scripts/validate-catalog.ps1), prefixed `ERROR: ` on the host.

| Message | What it means |
|---|---|
| `Artifact <id> declares '<value>' in dimension '<dim>', which is not in the catalog vocabulary. Allowed: ...` | The value is not in `vocabulary.<dim>`. Usually wrong case (`TypeScript` for `typescript`) or a value that needs adding to the vocabulary first. |
| `Artifact <id> declares unknown dimension '<dim>'. Known dimensions: languages, frameworks, layout, agents, topics.` | The dimension *name* is wrong — often case (`Languages`) or an invented dimension (`databases`). Names are case-sensitive too. |
| `Artifact <id> declares dimension '<dim>', which the catalog vocabulary does not publish.` | A known dimension that this index's `vocabulary` block omits. The vocabulary is at fault, not your artifact. |
| `Artifact <id> declares topic '<topic>', which is not in the catalog vocabulary. Allowed: ...` | Topic not in `vocabulary.topics`. Case-sensitive: `Code-Review` fails. |
| `Artifact <id> declares topics, which the catalog vocabulary does not publish.` | The index has no `topics` in its `vocabulary` block at all. |
| `Artifact <id> is missing required field 'applies_to'. Write applies_to as {} for a universally applicable artifact.` | You omitted `applies_to`. Write `{}` if it really is universal. |
| `Artifact <id> declares applies_to as the scalar '<value>' rather than an object. Write applies_to as {} for a universally applicable artifact.` | `applies_to` is a string, number, or array. It must be a JSON object. |
| `Artifact <id> is missing required field 'strength'. Expected 'always' or 'on-demand'.` | You omitted `strength`. There is no default. |
| `Artifact <id> has unknown strength '<value>'. Expected 'always' or 'on-demand'.` | Typo, or an invented level. Only two exist, both lower-case. |
| `Artifact <id> is on-demand but declares no topics, so no profile could ever select it.` | `on-demand` with `topics: []`. Give it topics, or make it `always` if it truly is baseline. |
| `Artifact <id> declares fixture: true, but only AS-SPIKE-* artifacts may. ...` | You set `fixture: true`. Remove it — it is transport test data only. |
| `Catalog index declares '<a>' and '<b>', which collide on a case-insensitive filesystem. Artifact ids must be unique.` | Two ids differ only in case. They would become one directory. |
| `Catalog index at <path> contains an artifact with no id (at index <n>).` | An entry has no `id`, a blank `id`, or is a bare string. Counted from 0. |
| `Catalog artifact at index <n> is not an object. ...` | An entry is a number or other non-object. |
| `Catalog index schema_version '<v>' is not covered by this validator (supports '1, 2').` | The index declares a schema version this validator does not cover. |
| `Catalog index at <path> has no vocabulary block. ...` | The `vocabulary` block is missing. Nothing can be validated without it. |
| `Catalog index at <path> has no artifacts list. Write an empty list for a catalog with no artifacts.` | The `artifacts` key is absent. |
| `Artifact <id> path '<path>' uses the Windows reserved device name '<name>' in component '<component>'. ...` | A path component resolves to a Windows device (`CON`, `NUL`, `COM1`…). Checkout fails with `invalid path`. |
| `Artifact <id> path '<path>' ends component '<component>' with a dot or a space. ...` | A trailing `.` or space. Checkout fails with `invalid path`. |
| `Artifact <id> path '<path>' is <n> characters long, over the 240-character maximum. ...` | Over the conservative limit; longer needs `core.longpaths=true`. |
| `Artifact <id> path '<a>' collides with '<b>' on a case-insensitive filesystem. ...` | Two paths differ only in case. The clone succeeds and one file disappears. |
| `Catalog directories '<a>' and '<b>' differ only in case, so they are one directory on Windows and default macOS. ...` | Two directory spellings, even with no two files colliding. Windows merges them and a sparse checkout pulls the wrong files. |
| `Artifact <id> declares source_path '<path>', which uses '\' separators / is absolute / contains a '.' or '..' segment.` | `source_path` is not a repository-relative `/`-separated path inside the catalog. The same messages name `upstream.path` or an `upstream.exclude item` when the fault is there. |
| `Artifact <id> declares upstream.repo '<url>'. Write it as https://github.com/<owner>/<repo>: ...` | A `.git` suffix, the SSH form, `http`, another host, or a deeper URL such as `/tree/main`. |
| `Artifact <id> declares upstream.commit '<value>', which is not a full 40-character lower-case commit SHA. ...` | A branch, a tag, a short SHA or upper-case hex. Pin the full SHA. |
| `Artifact <id> declares upstream.license '<value>', which is not on the allowlist: ...` | Only `MIT`, `Apache-2.0`, `BSD-2-Clause` and `BSD-3-Clause`, spelled exactly so. |
| `Artifact <id> upstream is missing required field '<field>' ...` / `declares unknown upstream field '<field>'` | `repo`, `commit`, `path` and `license` are required; `exclude` is the only optional field. |
| `Artifact <id> upstream.exclude must be a non-empty list of paths. ...` | `exclude` is empty or not a list of strings. Omit it when nothing is left out. |
| `Artifact <id> is an upstream artifact with no UPSTREAM.json / no LICENSE file. ...` | The directory was not produced by `sync-upstream.ps1 -Id <id>`, or a file was deleted. Run the sync. |
| `Artifact <id> UPSTREAM.json has <field> '<a>', but the index says '<b>'. ...` | The index entry changed after the last sync. Run the sync again. |
| `Artifact <id> takes its content from <repo>, which NOTICE does not mention. ...` | Add a `NOTICE` entry for the repository. |
| `Artifacts <a> ('<name>'), <b> ('<name>') have SKILL.md names that are the same case-insensitively. ...` | An upstream skill's own name clashes with another skill. Pick a different skill or adapt it; the author's file is not edited. |

`sync-upstream.ps1 -Verify` prints its faults the same way, prefixed `ERROR: `.
Each names the artifact and the file: one that differs from the pinned commit,
one missing from the catalog, or one present that the commit does not have or
`exclude` leaves out. A difference nobody made is usually line endings; see
[Line endings](#line-endings).

These three are thrown, not collected — they mean a broken invocation rather than bad catalog content, and there is nothing in the catalog to fix:

| Message | What it means |
|---|---|
| `Catalog index not found: <path>` | Wrong `-IndexPath`. |
| `Catalog index at <path> is not valid JSON: ...` | Malformed JSON — usually a trailing comma after the last artifact. |
| `Catalog index at <path> is empty.` | The file parsed to nothing. |

## What is not checked

Green CI does not mean a correct artifact. These are enforced by review alone.

| Not checked | What slips through |
|---|---|
| **Whether a name says what the artifact does** | The validator checks that the id, directory and `SKILL.md` name agree, not that they are any good. [Naming](#naming) is a review judgement. |
| **The `always` ceiling** | The validator never counts `always` artifacts. An index with 20 extra universal `always` artifacts validates clean. The ≤ 15 per profile ceiling is a review judgement with no gate behind it. |
| **Index ↔ `metadata.json` agreement** | The validator never compares `metadata.json` with the index. A `metadata.json` saying `strength: always` under an index entry saying `on-demand` passes CI. The index wins at install time, so the artifact behaves as the index says and the file in the directory lies. |
| **`source_path` points at anything** | Its spelling is checked (`artifacts/<id>`), but it is never resolved against the filesystem. An entry whose directory does not exist validates clean; the failure surfaces at install as an empty checkout. |
| **The subtree contract** | Nothing verifies an artifact is self-contained. An artifact depending on a file outside its directory clones successfully and arrives incomplete. |
| **`SKILL.md` content** | Only the frontmatter `name` is read, and only with `-CatalogRoot`. The body and the `description` are not linted, and the file is not required to exist. |
| **`requires` is complete** | Only an artifact that ships scripts or a `requirements.txt` is made to declare it. One whose `SKILL.md` runs `dbt build` or queries Snowflake can omit it and validate clean; the catalog map then tells users it needs nothing. |
| **What an upstream `exclude` removes** | `-Verify` checks that exactly the listed files are missing, not that the skill still works without them. Excluding a file `SKILL.md` refers to installs cleanly and fails when the agent follows the reference. |

The pattern across all eight: the failure is silent. Nothing errors, the install reports success, and the content is wrong or missing. That is why review is the gate here and why this list is worth re-reading before you approve someone else's artifact.

## Checklist

- [ ] Directory under `artifacts/`, named for the id, self-contained
- [ ] Id, `SKILL.md` `name` and `presentation.name` follow [Naming](#naming), and pass the neighbour test (upstream: id and `presentation.name` only)
- [ ] `SKILL.md` `description` ends with a "Use when ..." sentence (not for an upstream artifact; a command-only artifact says how to run it instead)
- [ ] Command-only: `disable-model-invocation: true` in the frontmatter and `agents/openai.yaml` with `allow_implicit_invocation: false`, both
- [ ] Upstream: passes [Adapt or reference](#adapt-or-reference), synced with `sync-upstream.ps1 -Id`, nothing excluded that `SKILL.md` or its references point at, `NOTICE` entry added, `-Verify` passes after commit
- [ ] Schema 2: `scope` is `project` or `user`; user scope is never `always`
- [ ] `strength` defaulted to `on-demand` unless you can defend `always` against the test
- [ ] `applies_to` declares only the dimensions that would make the artifact *wrong* if absent; `{}` written explicitly if universal
- [ ] `topics` non-empty if `on-demand`, all values from the vocabulary, all lower-case
- [ ] Schema 2 `on-demand`: presentation card has a short name, truthful summary and concrete benefits
- [ ] `requires` declared if the workflow runs a command or connects somewhere, with Russian text under `req` in `catalog-map/ru.json`
- [ ] `metadata.json` matches the index entry field for field (an upstream artifact has none)
- [ ] No `fixture: true`
- [ ] `./scripts/validate-catalog.ps1 -IndexPath ./index.json -CatalogRoot .` reports `IsValid: True`
