# Contributing

This covers how changes get made here: commit and branch conventions, the PR
process, and where to find everything else. It does not repeat what other
documents already own — follow the links instead of expecting a second copy.

- **Adding or changing an artifact** —
  [docs/authoring-artifacts.md](docs/authoring-artifacts.md).
- **Catalog schema, subtree contract, path rules, transport model** — the
  [README](README.md).

## Dev setup

This repository contains catalog content, PowerShell validation and Python
helper scripts bundled with some artifacts. Clone it, install Python 3.9 or later
and Pester, and run the gate:

```powershell
Install-Module Pester -RequiredVersion 5.6.1 -Force -Scope CurrentUser

$result = ./scripts/validate-catalog.ps1 -IndexPath ./index.json -CatalogRoot .
if (-not $result.IsValid) { throw "Catalog validation failed." }
Invoke-Pester -Path ./tests
python -B -m unittest discover -s tests -p 'test_*.py' -v
```

The Terraform plan summary and Terragrunt unit comparison tests use Python 3.9+
and its standard library; they need no Terraform or Terragrunt installation and
no cloud credentials.

Line endings are pinned by [`.gitattributes`](.gitattributes): Markdown, JSON
and YAML check out as LF everywhere, Windows included. Leave `core.autocrlf`
alone rather than working around it.

## Commit messages

`type: lowercase description`, imperative mood, no trailing period. Types in
active use: `feat`, `docs`, `test`, `chore`, `ci`, `release`. Pick the one that
matches the change's actual nature.

## Branches

`type/slug`, e.g. `feat/dbt-snowflake-skills`. Use the same `type` values as
commits.

## Pull requests

- Work on a branch off `main`; never commit directly to `main`. Run
  `git fetch` and branch from `origin/main`: a local `main` goes stale between
  releases, and work based on it silently drops what was merged since.
- Open a PR for review — don't push straight to `main` unless a maintainer
  explicitly asks for it.
- The gate above (catalog validation, Pester and Python tests) must pass before
  merge. CI (`.github/workflows/validate.yml`) runs the same checks.
- For a new or changed artifact, manually verify the profile combinations that
  should select and exclude it — see the
  [checklist](docs/authoring-artifacts.md#checklist) in the authoring guide.
- Update the docs a change actually affects (README, authoring guide) in the
  same PR — don't leave them to drift.
- Commits are authored under your own git identity, with clear human-style
  messages.

## Releasing

Releases are batched. A merged artifact reaches nobody until a tag carries it,
but a string of single-artifact tags is noise for every consumer pinning one,
so several merges go out together and a PR does not bump the catalog version by
itself. A release is one `release: cut vX.Y.Z` commit on `main` that updates
`toolset_ref` in `index.json`, the README Tags table and
[`docs/skill-catalog.md`](docs/skill-catalog.md). Wait for CI on that commit to
pass, then tag it. The release notes name every vocabulary change, because each
one may need an installer change (see
[the authoring guide](docs/authoring-artifacts.md#the-current-vocabulary)).

Before announcing a new tag, tick each item:

- [ ] Validation, `Invoke-Pester -Path ./tests` and the Python script tests pass on the tagged commit
- [ ] New row in the README [Tags](README.md#tags) table
- [ ] Refresh the shared catalog map so its version and skill list match the tag. Every artifact added in the release needs an entry in `catalog-map/groups.json` and Russian text in `catalog-map/ru.json` first (`build.js` warns about missing ones, and about Russian text written for an older artifact version). The command is in [`catalog-map/README.md`](catalog-map/README.md#update-after-a-catalog-release); only the owner of the Apps Script project can run it. Build it from the tagged commit, not from a local branch, and check that the skill count on the deployed page matches `index.json`
