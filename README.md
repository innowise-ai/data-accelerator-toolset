# Accelerator Toolset

The artifact catalog. Consumers fetch selected artifacts from this repository using Git partial clone with cone-mode sparse checkout, so a client downloads only the artifacts it needs rather than the whole catalog.

The catalog holds forty-six artifacts in four groups. Twenty-five are data-engineering specific, covering dbt, Snowflake, Spark, Airflow, Python pipeline code, sensitive data handling, and stack-agnostic pipeline quality practice, including data quality controls built into a pipeline. Four cover containers and local environments: Dockerfile build rules, Compose stacks, a first Docker scaffold, and a guardrail for destructive Docker commands. Two cover infrastructure as code: reviewing a Terraform plan, with Terragrunt, Atlantis and AWS access policies, before it is applied, and adding or moving Terragrunt units in bulk across tenants and environments without drift. Fifteen are general skills that apply to any stack: change review, project documentation, code comments, test design, refactoring, error diagnosis, technical writing, the four development-process artifacts covering requirements, planning, execution and verification, project adaptation, which adds repository paths, commands, conventions and examples inside each installed skill's `SKILL.md`, research into what people said about a topic in the last 30 days, a daily standup update written from the engineer's actual activity, and request refinement, which turns a rough request into a complete one before the agent starts work. Every entry has real content; the `AS-SPIKE-*` placeholders that proved the transport design have all been removed.

`RECENT-DISCUSSION-RESEARCH` is the one [upstream artifact](docs/authoring-artifacts.md#upstream-artifacts): its directory is a third party's skill (`last30days`), unchanged and pinned to a commit of the author's repository, rather than our own text. Every other artifact is written or adapted here.

Every artifact except one is `on-demand`, so a profile receives only what its declared topics select and the user explicitly chooses. The exception is `DOCKER-DATA-LOSS-CONFIRMATION`, which is `always`: it installs into every project that uses Docker, because losing a data volume is not something a team should have to remember to ask protection against. See [`docs/authoring-artifacts.md`](docs/authoring-artifacts.md) for what an `always` artifact has to justify.

Forty-two artifacts are `project` scope. Four are `user` scope, personal tools that do not belong in a shared project plan: `TECHNICAL-PROSE-EDITING`, an editing tool, `DAILY-STANDUP-UPDATE`, which reports one engineer's own work, `RECENT-DISCUSSION-RESEARCH`, which calls third-party APIs with the user's own keys and can read their browser cookies with consent, and `REQUEST-REFINEMENT`, which runs only when a person types its command.

## Layout

```text
index.json                      # catalog root — the only file fetched unconditionally
artifacts/
  AIRFLOW-DAG-STRUCTURE/
    SKILL.md
    metadata.json
  CODE-CHANGE-REVIEW/
  CODE-COMMENT-WRITING/
  COMPLETION-VERIFICATION/
  DAILY-STANDUP-UPDATE/
  DATA-INCIDENT-TRACING/
  DATA-QUALITY-CONTROLS/
  DBT-BUILD-FAILURE-DIAGNOSIS/
  DBT-COLUMN-LINEAGE/
  DBT-INCREMENTAL-STRATEGY/
  DBT-LAYER-BOUNDARIES/
  DBT-LEGACY-SQL-MIGRATION/
  DBT-MODEL-BUILD-VERIFY/
  DBT-MODEL-DESCRIPTIONS/
  DBT-MODEL-REFACTORING/
  DBT-MODEL-TESTING/
  DOCKER-COMPOSE-LOCAL-STACK/
  DOCKER-DATA-LOSS-CONFIRMATION/
  DOCKER-IMAGE-BUILD/
  DOCKER-PROJECT-SETUP/
  ERROR-DIAGNOSIS/
  ETL-DECOMPOSITION/
  IMPLEMENTATION-PLANNING/
  NL2SQL-QUERY-VALIDATION/
  PIPELINE-CHECK-SELECTION/
  PIPELINE-OUTPUT-REVIEW/
  PLAN-EXECUTION/
  PROJECT-ADAPTATION/
  PROJECT-DOCUMENTATION/
  PYTEST-DATA-PIPELINES/
  RECENT-DISCUSSION-RESEARCH/   # upstream: the author's files, plus
    SKILL.md                    #   our UPSTREAM.json and LICENSE
    UPSTREAM.json
    LICENSE
    ...
  REFACTOR-STEP-PLANNING/
  REQUEST-REFINEMENT/           # runs only on the user's command:
    SKILL.md                    #   disable-model-invocation in the frontmatter,
    agents/openai.yaml          #   and the same policy for Codex
    metadata.json
  REQUIREMENTS-BRAINSTORMING/
  SCD2-IMPLEMENTATION/
  SENSITIVE-DATA-HANDLING/
  SNOWFLAKE-COST-HOTSPOTS/
  SNOWFLAKE-GRANT-RESTORE/
  SNOWFLAKE-QUERY-PROFILE-DIAGNOSIS/
  SNOWFLAKE-QUERY-REWRITE/
  SNOWFLAKE-SEMANTIC-VIEW-DRIFT/
  SPARK-JOB-TUNING/
  TECHNICAL-PROSE-EDITING/
  TERRAFORM-PLAN-REVIEW/
  TERRAGRUNT-UNIT-REPLICATION/
  TEST-DESIGN-REVIEW/
```

## `index.json`

```json
{
  "schema_version": "2",
  "toolset_ref": "refs/tags/v0.6.2",
  "vocabulary": {
    "languages": ["typescript", "javascript", "python", "csharp", "go", "sql"],
    "frameworks": ["nestjs", "react", "django", "aspnet", "airflow", "dbt", "duckdb", "spark", "trino", "snowflake", "databricks"],
    "layout": ["monorepo", "single"],
    "agents": ["claude-code", "codex", "cursor"],
    "topics": [
      "code-review", "testing", "documentation", "refactoring",
      "orchestration", "data-modeling", "data-quality", "ingestion", "performance",
      "debugging", "writing", "development-process", "security"
    ]
  },
  "artifacts": [
    {
      "id": "AIRFLOW-DAG-STRUCTURE",
      "version": "0.1.1",
      "source_path": "artifacts/AIRFLOW-DAG-STRUCTURE",
      "applies_to": { "frameworks": ["airflow"] },
      "strength": "on-demand",
      "topics": ["orchestration"],
      "scope": "project",
      "presentation": {
        "name": "Structure Airflow DAGs for safe, cheap imports",
        "summary": "Structures Airflow DAGs so nothing expensive or fragile runs at import time.",
        "benefits": [
          "Keeps connections and queries out of module scope, where the scheduler re-runs them",
          "Applies consistent default_args, retries and scheduling across DAGs",
          "Flags import-time work that makes the scheduler slow or unstable"
        ]
      }
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `schema_version` | Index format version. Currently `"2"` |
| `toolset_ref` | The ref this index describes |
| `vocabulary` | The closed set of legal values per dimension. Dimensions are exactly `languages`, `frameworks`, `layout`, `agents`, `topics` |
| `artifacts[].id` | Unique artifact identifier; matches the directory name. Unique case-insensitively, since ids become directory names |
| `artifacts[].version` | Artifact version |
| `artifacts[].source_path` | Repository-relative path to the artifact directory |
| `artifacts[].applies_to` | Which projects the artifact is applicable to. Required. `{}` means universally applicable and must be written explicitly |
| `artifacts[].strength` | `always` or `on-demand`. Required |
| `artifacts[].topics` | Intents that select an `on-demand` artifact. Must be non-empty when `strength` is `on-demand` |
| `artifacts[].scope` | Schema 2: `project` or `user`. User artifacts are personal and require explicit selection |
| `artifacts[].presentation` | Schema 2 `on-demand`: questionnaire card with non-empty `name`, `summary`, and `benefits` |
| `artifacts[].requires` | Optional: `tools` and `access` a user needs before the artifact runs. Shown on the catalog map, not matched |
| `artifacts[].upstream` | Optional: `repo`, `commit`, `path`, `license` and optionally `exclude`, marking an upstream artifact whose directory is a third party's skill at that commit. Ignored by the installer; see [Upstream artifacts](docs/authoring-artifacts.md#upstream-artifacts) |
| `artifacts[].fixture` | `true` marks transport test data, exempt from all matching validation. Permitted only on `AS-SPIKE-*` ids |

Every value in `applies_to` and `topics` must appear in `vocabulary`. Comparison is case-sensitive: `TypeScript` does not match `typescript`.

`id`, `version`, and `source_path` are the transport inputs. The matching fields live in the index as well — not only inside the artifact — because a consumer doing a partial clone holds `index.json` alone at the moment it decides what to fetch. Reading matching metadata from inside artifact directories would require fetching every candidate's blobs before choosing which to fetch, which is the cost partial clone exists to avoid.

An artifact's `metadata.json` carries the same `applies_to`, `strength`, `topics`, `scope`, and `presentation` as its index entry. The two must agree; the index is authoritative for matching. An upstream artifact has no `metadata.json`: its directory is the author's files plus `UPSTREAM.json` and `LICENSE`, and nothing else of ours.

### Questionnaire-ready schema 2

This catalog is schema 2, the contract for hierarchical general-skill selection.
The validator still accepts schema 1 for previously published tags:

```json
{
  "id": "HUMANIZER",
  "scope": "user",
  "applies_to": {},
  "strength": "on-demand",
  "topics": ["documentation"],
  "presentation": {
    "name": "Humanizer",
    "summary": "Makes generated prose read naturally.",
    "benefits": ["Removes repetitive AI phrasing", "Preserves meaning"]
  }
}
```

Topics are broad discovery categories. The final consent is the exact artifact
id. `project` selections are shared; `user` selections remain a local overlay.
An `always` artifact cannot use user scope.

## The subtree contract

**One artifact is exactly one self-contained directory.** `source_path` must point at that directory, and the artifact must not depend on files outside it.

This is not a style preference. Cone-mode sparse checkout selects whole directories:

```bash
git sparse-checkout set artifacts/DBT-MODEL-BUILD-VERIFY artifacts/DBT-MODEL-TESTING
```

An artifact whose files are scattered across the repository cannot be selected this way. The alternative — non-cone mode with per-file patterns — was rejected as a production default because it forces the installer to enumerate every file of every artifact, coupling transport to internal artifact layout.

Breaking this contract does not fail loudly. The clone succeeds and the artifact arrives incomplete.

## Path rules

Every `source_path` and every path inside an artifact must satisfy all of the following. These were derived from cloning deliberately invalid trees on Windows; see the spike report for the observed failures.

| Rule | Why |
|---|---|
| Repository-relative only, `/` separators | Absolute paths and `\` do not survive the transport boundary |
| No `.` or `..` segments | Path traversal |
| No case-insensitive collisions (`Case.md` vs `case.md`) | On Windows the clone succeeds with a warning and **one file silently disappears** from the worktree |
| No Windows reserved device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9`) | Checkout fails with `invalid path`, exit 128 |
| No trailing dot or trailing space | Checkout fails with `invalid path`, exit 128 |
| Maximum 240 characters | A 244-character path worked on the test machine only because `core.longpaths=true` was set. That must not be assumed of every developer |

The case-collision rule is the dangerous one: it is the only violation that produces a successful clone with missing content.

**Catalog CI enforces this table.** `validate-catalog.ps1 -CatalogRoot .` checks every file in the checkout and every declared `source_path`, and names the artifact, the exact path and the rule it broke. Run it locally before pushing:

```powershell
./scripts/validate-catalog.ps1 -IndexPath ./index.json -CatalogRoot .
```

Without `-CatalogRoot` the validator checks `index.json` alone and reports `PathCount: 0` — which is how you tell a checkout that passed from one that was never scanned. With it, a root holding no files is an error rather than a silent pass.

To check a specific set of paths instead of walking a directory — tracked files only, say — pass them with `-PathList` (the two are mutually exclusive):

```powershell
./scripts/validate-catalog.ps1 -IndexPath ./index.json -PathList (git ls-files)
```

Two details the table above leaves implicit: the rules apply to `AS-SPIKE-*` fixtures too — `fixture: true` exempts an artifact from matching validation, not from a path that breaks everyone's checkout — and two directories differing only in case are reported even when no two *files* collide, because on Windows they are one directory.

## Fetching artifacts

```bash
# 1. Partial clone, no blobs, pinned to an immutable ref
git clone --depth 1 --branch <tag> --filter=blob:none --sparse -- <toolset-url> <dst>

# 2. Read index.json — it materializes with the initial checkout

# 3. Select the artifacts you need, by directory
git -C <dst> sparse-checkout set artifacts/DBT-MODEL-BUILD-VERIFY artifacts/DBT-MODEL-TESTING
```

Pin to a tag or commit SHA, never a moving branch. Unselected artifacts are absent from the local object store, not merely from the worktree — verified under `GIT_NO_LAZY_FETCH=1`. Reading a missing blob triggers a lazy fetch from the promisor remote.

Measured against a full shallow clone of the 50-artifact fixture set this catalog carried at the time: selecting 5 of 50 artifacts transferred ~91% less compressed pack payload. That measurement is historical — the 42 pure transport fixtures have since been removed — and it is kept because it is the number the transport design was justified on, not a description of the catalog's current size. Sparse selection is *slower* than a full clone at this scale because of the extra round trip — the benefit is disk and context, not speed.

## Licence

This catalog is MIT licensed — see [`LICENSE`](LICENSE). Artifacts adapted from
third-party sources carry their own upstream attribution in [`NOTICE`](NOTICE);
that file travels with any copy of this repository, as the upstream licences
require. An upstream artifact is its author's work under its author's licence,
which it carries as `LICENSE` in its own directory, so the licence is installed
with every copy.

## Related

- Contributing — commit and branch conventions, the PR process, dev setup: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Third-party attribution for artifacts derived from external sources: [`NOTICE`](NOTICE)
- Adding an artifact — the `strength`, `applies_to`, and `topics` decisions, a worked example, and how to validate before pushing: [`docs/authoring-artifacts.md`](docs/authoring-artifacts.md)
- Using this catalog without the installer: see [Fetching artifacts](#fetching-artifacts) above. The transport is plain Git against a public repository, so no credentials and no additional tooling are required

The installer that consumes this catalog is distributed inside Innowise, and its
repository is not public. The following references resolve for internal readers
only:

- Transport evidence, measurements, and the GO verdict: `spikes/infra-transport/coder-infra-spike-report.md` in `accelerator-installation`
- Installer delivery and installation instructions: same repository

## Tags

| Tag | Contents |
|---|---|
| `v0.0.0-spike` | Initial fixture |
| `v0.0.1-spike` | Representative deterministic payloads — the ref all published measurements were taken against |
| `v0.1.0` | Matching vocabulary published; `AS-SPIKE-001`–`008` promoted to real catalog metadata |
| `v0.2.0` | First artifacts with real content (five, data-engineering); vocabulary gains `sql`, the tool frameworks and the data topics; transport fixtures `AS-SPIKE-009`–`050` removed |
| `v0.3.0` | Ten dbt and Snowflake artifacts adapted from a third-party MIT source (see [`NOTICE`](NOTICE)); vocabulary gains the `snowflake` and `databricks` frameworks and the `debugging` topic; line endings pinned by `.gitattributes` |
| `v0.4.0` | Remaining `AS-SPIKE-001`–`008` matching examples removed; the catalog is fifteen real artifacts, all `on-demand`. The `fixture` field and its validation are retained for future transport work |
| `v0.5.0` | Three stack-agnostic pipeline quality artifacts, adapted from internal team practice; the first artifacts declaring `applies_to: {}`, and the first content under the `code-review` topic |
| `v0.5.1` | No catalog content change. Adds `LICENSE` (MIT) and marks the internal-only references in `Related`, so the catalog can be published as a public repository |
| `v0.6.0` | `schema_version` moves to `2`: every artifact declares `scope`, and every `on-demand` artifact carries a questionnaire `presentation` card. The eighteen existing artifacts are migrated additively, with no `SKILL.md` changed. Ten general skills added — six stack-independent engineering skills and four covering the development process — taking the catalog to twenty-eight. `TECHNICAL-WRITING` is the first `user`-scope artifact. Vocabulary gains the `writing` and `development-process` topics |
| `v0.6.1` | No catalog content change. Vocabulary gains `codex` as an `agents` value, so an artifact can declare `applies_to.agents: ["codex"]` and a profile naming `codex` validates. Companion to the installer's multi-agent install targets; no artifact currently declares `applies_to.agents`, so nothing selected changes |
| `v0.6.2` | No catalog content change. Vocabulary gains `cursor` as an `agents` value, so an artifact can declare `applies_to.agents: ["cursor"]` and a profile naming `cursor` validates. Companion to the installer's Cursor install target, which writes artifacts into `.cursor/skills`; no artifact currently declares `applies_to.agents`, so nothing selected changes |
| `v0.6.3` | Two artifacts added, taking the catalog to thirty: `SAFE-NL2SQL-GUARDRAILS` (`languages: ["sql"]`, topic `data-quality`) and `DBT-COLUMN-LINEAGE` (`frameworks: ["dbt"]`, topic `data-modeling`). Both `on-demand` and `project` scope; the vocabulary is unchanged, so no installer companion is needed. `DBT-COLUMN-LINEAGE` is the first artifact requiring dbt **Cloud** and an MCP server to run its scripts — the rest of the catalog assumes dbt Core alone. Unlike the two preceding patch releases this one does change catalog content; the earlier convention of reserving minors for new artifacts was not followed here. Also carries the path-rule validator from the previous tag's outstanding work: `validate-catalog.ps1` now machine-checks the Windows path rules that were review-enforced through `v0.6.2` |
| `v0.7.0` | Eight artifacts added, taking the catalog to thirty-eight: `PROJECT-ADAPTATION` and `SENSITIVE-DATA-HANDLING` (general, no `applies_to` restriction), `SNOWFLAKE-SEMANTIC-VIEW-DRIFT` and `SNOWFLAKE-GRANTS-AFTER-RECREATE` (`frameworks: ["snowflake"]`), and four Docker artifacts: `DOCKER-BUILD-STRATEGIES`, `DOCKER-COMPOSE-PATTERNS`, `DOCKER-DESTRUCTIVE-GUARDRAILS` (`frameworks: ["docker"]`) and `DOCKER-PROJECT-FOUNDATIONS` (`languages: ["python"]`). `DOCKER-DESTRUCTIVE-GUARDRAILS` is the catalog's first `always` artifact: every profile that declares `docker` gets it without choosing it. `CHANGE-REVIEW` moves to `0.2.0` (file coverage accounting, explicit non-findings, finding verification) with selection unchanged. Vocabulary gains `docker` in `frameworks` and the `containerization` and `security` topics. The installer reads the vocabulary from the index, so no installer release is required, but its scanner does not yet detect Docker projects, so `docker` reaches a profile only through the questionnaire until that lands |
| `v1.0.0` | **Breaking: artifact ids renamed.** Twenty-two artifacts get ids, directories and `SKILL.md` names that say what they do rather than which area they cover (for example `SNOWFLAKE-QUERY-BY-ID` → `SNOWFLAKE-QUERY-PROFILE-DIAGNOSIS`, `DBT-MODEL-CREATION` → `DBT-MODEL-BUILD-VERIFY`, `TECHNICAL-WRITING` → `TECHNICAL-PROSE-EDITING`); the full table is in issue #34. Every artifact gets a verb-phrase `presentation.name` and a `description` ending in "Use when ...", and moves up one patch version. No artifact added or removed; vocabulary unchanged. The installer keys copies by id, so a profile moving to this tag has the renamed artifacts removed under their old ids and installed under the new ones. `validate-catalog.ps1` now requires `source_path` = `artifacts/<id>` and, with `-CatalogRoot`, a `SKILL.md` `name` equal to the lower-case id. From this tag, ids are treated as stable |
| `v1.1.0` | First infrastructure-as-code artifacts, taking the catalog to forty: `TERRAFORM-PLAN-REVIEW` (`frameworks: ["terraform"]`, topics `code-review` and `security`) reviews a Terraform plan in plain language before apply, with Terragrunt, Atlantis and AWS access-policy checks and a `plan_summary.py` script; `TERRAGRUNT-UNIT-REPLICATION` (`frameworks: ["terragrunt"]`, topics `infrastructure` and `refactoring`) adds or moves Terragrunt units in bulk across tenants and environments, with a read-only `compare_units.py` script. Both `on-demand` and `project` scope; their scripts need Python 3.9+ and the standard library only. `SCD2-IMPLEMENTATION` moves to `0.1.2` (the merge is idempotent on re-run) with selection unchanged. Vocabulary gains `terraform` and `terragrunt` in `frameworks` and the `infrastructure` topic. The installer reads the vocabulary from the index, so no installer release is required, but its scanner does not yet detect Terraform or Terragrunt projects (installation #66), so these values reach a profile only through the questionnaire until that lands. CI now also runs the artifact scripts' Python tests on 3.9 and 3.12 |
| `v1.1.1` | Selection fix. `TERRAFORM-PLAN-REVIEW` moves to `0.1.2` and gains the `infrastructure` topic, which it missed because it was merged before the topic existed; a profile that asks for `infrastructure` is now offered it alongside `TERRAGRUNT-UNIT-REPLICATION`. Its `SKILL.md` and presentation card are unchanged. No artifact added or removed; vocabulary unchanged |
| `v1.2.0` | One artifact added, taking the catalog to forty-one: `CODE-COMMENT-WRITING` (`applies_to: {}`, topic `documentation`, `on-demand`, `project` scope) decides what a code comment says and where it goes and keeps comments true as code changes, with dbt and Dataform references. `PROJECT-DOCUMENTATION` and `DBT-MODEL-DESCRIPTIONS` move to `0.1.2` and link to it; selection and cards unchanged. New optional `requires` field (`tools`, `access`) declaring what an artifact needs to run, set on sixteen artifacts (the dbt artifacts that build or show models, the Snowflake artifacts that query the account, three Docker artifacts, and the Terraform and Terragrunt artifacts); `validate-catalog.ps1` checks its shape and, with `-CatalogRoot`, rejects an artifact that ships scripts or a `requirements.txt` without it, and the catalog map shows it on each card. Vocabulary gains `dataform` and `bigquery` in `frameworks`. The installer reads the vocabulary from the index, so no installer release is required, but its scanner does not yet detect Dataform or BigQuery projects (installation branch `feat/scan-detect-dataform-bigquery`), so these values reach a profile only through the questionnaire until that lands |
| `v1.3.0` | Vocabulary gains the `database-administration` topic, which the DBA team's read-only database audit artifacts (#65) build on. `SNOWFLAKE-COST-HOTSPOTS` and `SNOWFLAKE-QUERY-PROFILE-DIAGNOSIS` gain the topic and move to `0.1.2`, so the questionnaire asks it in Snowflake projects; their `SKILL.md` and cards are unchanged, and a profile asking for `performance` selects the same artifacts as before. `SNOWFLAKE-QUERY-REWRITE` is not tagged, since rewriting a query is development work. No artifact added or removed. The installer reads the vocabulary from the index, so no installer release is required, but its scanner does not detect the topic, so it reaches a profile only through the questionnaire (questionnaire work in installation #72). The catalog map gains a "Database administration" group, lets a skill sit in several groups, marks skills added since the previous release as "new" and adds a "new" filter chip |
| `v1.4.0` | Three artifacts added, taking the catalog to forty-four: `DATA-QUALITY-CONTROLS` (`applies_to: {}`, topics `data-quality` and `ingestion`, `project` scope) builds quarantine, release diff and per-source scorecards into a pipeline; `RECENT-DISCUSSION-RESEARCH` (topic `research`, `user` scope) researches what people said about a topic in the last 30 days; `DAILY-STANDUP-UPDATE` (topics `writing` and `development-process`, `user` scope) drafts a daily standup update from the engineer's commits, pull requests and reviews since the last working day. All `on-demand`. `RECENT-DISCUSSION-RESEARCH` is the first [upstream artifact](docs/authoring-artifacts.md#upstream-artifacts): the author's `last30days` skill, unchanged and pinned to a commit, with its licence in its directory and an entry in `NOTICE`. The index gains an optional `upstream` field, which the installer ignores; `scripts/sync-upstream.ps1` fetches and verifies those files, the validator checks the entry, its provenance, licence and notice, and CI verifies upstream artifacts against their pinned commits. Vocabulary gains the `research` topic. The installer reads the vocabulary from the index, so no installer release is required; its scanner does not detect the topic, so it reaches a profile only through the questionnaire, which phrases an unfamiliar topic as a neutral question. `CONTRIBUTING.md` now says which part of the version a release moves; this tag takes a minor for the vocabulary change |
| `v1.4.1` | Two artifacts added, taking the catalog to forty-six: `SPARK-JOB-TUNING` (`frameworks: ["spark", "databricks"]`, topics `performance` and `debugging`, `project` scope) finds the stage and cause that dominate a slow or memory-failing Spark job from its Spark UI evidence, fixes that cause and measures the result, adapted from a third-party Apache 2.0 source (see [`NOTICE`](NOTICE)); `REQUEST-REFINEMENT` (`applies_to: {}`, topic `development-process`, `user` scope) rewrites a rough request with what the project already answers, asks only what it cannot infer and starts once the user confirms. Both `on-demand`. `REQUEST-REFINEMENT` is the first artifact that runs only on the user's command: `disable-model-invocation: true` in its frontmatter for Claude Code and Cursor (`/request-refinement`) and `agents/openai.yaml` for Codex (`$request-refinement`); the installer copies both unchanged, so it needs no change, and the authoring guide documents the pattern. `AIRFLOW-DAG-STRUCTURE` moves to `0.1.2` (`schedule=` instead of `schedule_interval=`, `catchup` set on the DAG) with selection unchanged. Vocabulary unchanged. CI pins the validate runner to `ubuntu-24.04` |

Tags are immutable. A published tag is never moved to a different commit: a consumer profile pins one of these, and repointing it would hand the same profile different artifacts with nothing anywhere reporting a change. Corrections ship as a new tag.
