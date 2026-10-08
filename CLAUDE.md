# CLAUDE.md

Guidance for coding agents working in this repository. The rules themselves live
in the documents below; this file says where, and lists the ones an agent is
most likely to break.

- Catalog schema, subtree contract, path rules, transport, tags: [README.md](README.md)
- What belongs in the catalog, adopting external skills, naming, vocabulary,
  the five matching decisions: [docs/authoring-artifacts.md](docs/authoring-artifacts.md)
- Dev setup and the gate, commits, branches, PRs, releasing: [CONTRIBUTING.md](CONTRIBUTING.md)
- Catalog map build and deploy: [catalog-map/README.md](catalog-map/README.md)

## What this repository is

The artifact catalog consumed by the Accelerator installer. Each artifact is one
self-contained directory under `artifacts/<ID>/`; `index.json` is the catalog
root and decides what gets selected. There is no application to run. The work is
writing artifact content and keeping the index, the docs and the catalog map
consistent with it.

## Before you start and before you push

- `git fetch`, then branch from `origin/main`, never from a local `main`.
- Run the gate from [CONTRIBUTING.md § Dev setup](CONTRIBUTING.md#dev-setup).

## Easy to break

Each item links to the place that explains it.

- Renaming an artifact id breaks installs: [Naming](docs/authoring-artifacts.md#naming).
- A new vocabulary value needs release notes and possibly an installer change:
  [The current vocabulary](docs/authoring-artifacts.md#the-current-vocabulary).
- Do not bump the catalog version in a feature PR; releases are batched:
  [Releasing](CONTRIBUTING.md#releasing).
- dbt Core is assumed, artifacts ship no hooks, and text explains why rather
  than listing Do/Don't: [What belongs in the catalog](docs/authoring-artifacts.md#what-belongs-in-the-catalog).
- The index entry and `metadata.json` must agree, and nothing checks it:
  [Hard rules](docs/authoring-artifacts.md#hard-rules).
