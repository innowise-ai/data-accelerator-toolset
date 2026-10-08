# CLAUDE.md

Guidance for coding agents working in this repository. It covers what the code
and the other documents do not make obvious; for everything else it points at
the document that owns the topic instead of keeping a second copy.

- Catalog schema, subtree contract, path rules, transport, tags: [README.md](README.md)
- Adding or changing an artifact: [docs/authoring-artifacts.md](docs/authoring-artifacts.md)
- Commits, branches, PRs, releasing: [CONTRIBUTING.md](CONTRIBUTING.md)
- Catalog map deploy: [catalog-map/README.md](catalog-map/README.md)

## What this repository is

The artifact catalog consumed by the Accelerator installer. Each artifact is one
self-contained directory under `artifacts/<ID>/` holding `SKILL.md`,
`metadata.json` and, for some, `scripts/` and `references/`. `index.json` is the
catalog root and the only file a consumer fetches unconditionally; it decides
what gets selected, so its entry and the artifact's `metadata.json` must agree.

There is no application to run. The work is writing artifact content and keeping
the index, the docs and the catalog map consistent with it.

## The gate

Run before every push; CI (`.github/workflows/validate.yml`) runs the same:

```powershell
$result = ./scripts/validate-catalog.ps1 -IndexPath ./index.json -CatalogRoot .
if (-not $result.IsValid) { $result.Errors }
Invoke-Pester -Path ./tests
python -B -m unittest discover -s tests -p 'test_*.py' -v
```

Without `-CatalogRoot` the validator checks the index alone and reports
`PathCount: 0`, which looks like a pass but scanned nothing.

## Rules that are easy to break

- **Start from fresh `main`.** `git fetch` and branch from `origin/main`. Local
  `main` goes stale between releases, and the catalog map was once redeployed
  from a stale base and lost two skills.
- **Ids are stable since `v1.0.0`.** The installer keys installed copies by id,
  so renaming an artifact is a breaking change, not a cleanup.
- **Changing the vocabulary is half of a contract.** A new value in
  `frameworks`, `topics` or another dimension needs a line in the release notes
  and a check of whether the installer's scanner detects it. An artifact merged
  before a topic existed does not pick that topic up by itself.
- **Tags are immutable.** Corrections ship as a new tag. Merged artifacts reach
  nobody until a release is cut, and releases are batched, so do not propose a
  version bump per PR.
- **dbt Core is assumed.** `DBT-COLUMN-LINEAGE` is the single artifact that
  needs dbt Cloud and an MCP server. Content that gates on dbt Cloud, Fusion or
  another paid tier does not fit the catalog.
- **No agent hooks or settings in artifacts.** An artifact is `SKILL.md` plus
  metadata, and it targets Claude Code, Codex and Cursor. A skill that writes to
  a database describes what it changes in `SKILL.md`, confirms each write, and
  recommends a least-privilege role; the database role is the real boundary.
- **Line endings are pinned** by `.gitattributes`: Markdown, JSON and YAML are
  LF everywhere, including Windows checkouts.

## Writing style

Artifact text explains *why* a rule exists rather than listing Do/Don't items.
"Don't put heavy logic in the DAG file" is the shape to avoid; explaining the
scheduler's parse loop that makes it matter is the shape to aim for. This is
also why a popular external skill is often rejected as a duplicate even when
our coverage of the topic is thinner.

## Scope

The catalog covers the whole big-data stack, not only the frameworks and topics
currently in the vocabulary. A missing vocabulary value is part of the work of
adding an artifact, not a reason to reject it. Power BI is out of scope.

## Adopting external skills

Vet a third-party skill in this order: licence, path in the repository tree,
body of `SKILL.md`, coupling to a CLI or paid product, install count last.

- `gh api repos/OWNER/REPO --jq '.license.spdx_id'` first. `NOASSERTION` means a
  non-standard licence, not a missing one; read `LICENSE`.
- GPL-3.0 and vendor-restricted licences block adoption into this MIT catalog.
  Apache-2.0 is usable but needs its own section in [NOTICE](NOTICE) with the
  full licence text and a note of modifications.
- Known defects in a source are fixed during migration, not copied over.
