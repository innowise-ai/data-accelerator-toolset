---
name: terragrunt-unit-replication
description: Adding or moving Terragrunt units in bulk across tenants and environments without drift - choosing the template unit, separating what varies from what must not, checking what a copy silently inherits (state key, dependency paths, parent-folder lookups), verifying the batch with a bundled diff script, and keeping state migration a separate, confirmed step. Use when creating the same unit for many tenants or environments, or consolidating a service's units from several repositories into one.
---

# Replicate Terragrunt units without drift

Terragrunt exists so a module can be reused across tenants and environments. On a
multi-tenant project that reuse often takes the form of one near-identical
`terragrunt.hcl` per tenant per environment, and adding a service means writing
dozens or hundreds of them. The work is mechanical, which is exactly why it goes
wrong quietly: a bucket name copied from the wrong tenant, a unit missed in one
environment, a module `ref` that differs in the one copy nobody looked at. None of
these fail `hcl fmt`, and most of them produce a plan that looks plausible.

This skill covers two jobs: creating the same unit across many tenants or
environments, and moving a service's units from one repository or directory into
another. Both are treated as a batch that is checked as a whole, not as a series of
files that each looked fine.

## What this skill changes

It writes unit files and, where the project already has them, shared config files
(`env.hcl`, `account.hcl` and similar). It reads everything else.

It never runs `apply`, `destroy` or any state-changing command (`state mv`,
`state rm`, `state push`, `import`) on its own initiative. Each of those is shown
with its target directory and the state it touches, and runs only after the user
confirms that specific command. `plan` is read-only against the infrastructure but
still needs credentials for every account it touches; run it only where the user
has said plans may be run, and on Atlantis projects prefer letting the pull
request trigger it.

## Establish the layout before copying anything

Read three things first, because every later step depends on them.

**Where units live and how the path encodes tenant and environment.** Most
projects follow a fixed shape such as `live/<tenant>/<env>/<service>/terragrunt.hcl`
or `<account>/<region>/<env>/<service>/`. Write that shape down as a pattern; the
verification script needs it, and so does your reasoning about what a new path
implies.

**How the state key is derived.** Find the `remote_state` block, normally in the
root config (`root.hcl`, or a `terragrunt.hcl` at the top of the tree in older
projects). The usual form is

```hcl
remote_state {
  backend = "s3"
  config = {
    bucket = "acme-terraform-state"
    key    = "${path_relative_to_include()}/terraform.tfstate"
    region = "eu-west-1"
  }
}
```

With this form the state location is the unit's directory path. That one fact
decides most of what follows: a copied unit gets its own state automatically, and a
moved or renamed unit points at an empty state. If instead a unit declares a
literal `key`, every copy of that unit shares the template's state, and the first
`apply` from a copy will try to reshape the template's resources into the copy's.

**Where per-tenant and per-environment values come from.** Many layouts keep them
in files read from the hierarchy:

```hcl
locals {
  env     = read_terragrunt_config(find_in_parent_folders("env.hcl"))
  account = read_terragrunt_config(find_in_parent_folders("account.hcl"))
}
```

If the project does this, a new unit takes its tenant values from its location,
and the copy itself may need no edits at all. It also means a new tenant directory
needs its own `account.hcl` before any unit in it is correct.
`find_in_parent_folders` searches upward and takes the first match, so a missing
file is not always an error: a file of the same name further up the tree
will be read instead, and the unit quietly gets another level's values.

## Find the template unit

Do not copy the first instance you find. List every existing instance of the
module and compare them:

```bash
python scripts/compare_units.py --root live --layout "{tenant}/{env}/{unit}" --unit s3-landing
```

The script (described under [Verify the batch](#verify-the-batch)) groups the
instances by content after each one's own tenant and environment names are
replaced with placeholders, so the variants that remain are real differences. If
there is one variant, any instance is a fine template. If there are several, find
out why before choosing: some differences are intended (a larger instance size in
production), some are drift (one copy left on an old module `ref`), and some are
mistakes (a value from another tenant). The most common variant is not
automatically the right one; a mistake that was copied twenty times is still a
mistake. When the reason for a difference is not evident from the code or its
history, ask.

Prefer a template from the same environment tier as the targets. A production unit
copied into development usually carries production sizing, and the reverse is worse.

## Separate what varies from what must not

Go through the template line by line and put each value in one of three groups:

- **Varies by location and is already derived.** Values computed from
  `path_relative_to_include()`, `basename(get_terragrunt_dir())` or the
  `env.hcl`/`account.hcl` locals. Leave them alone; that is the shared config doing
  its job.
- **Varies and is written literally.** Names, ARNs, account ids, CIDR ranges,
  sizes. Each one has to change in every copy, which is where wrong-tenant values
  come from. If the project already derives similar values from locals or shared
  files, derive this one the same way. If it does not, change the literal and
  report it as a candidate for the team to parameterise later.
- **Must be identical everywhere.** The module `source` and its `ref`, `include`
  blocks, feature flags that are not tenant decisions. A difference here is drift by
  definition, and a copy that differs from the template should not ship.

A module `source` pinned to a branch (`?ref=main`) rather than a tag or commit is
worth flagging even when every copy agrees: the units will not stay identical in
behaviour, because what `main` means changes underneath them.

Use the indirection the project already uses (`include`, `locals`, `dependency`,
`generate` blocks, `read_terragrunt_config`) and no other. Introducing a new shared
file, a new include layer or Terragrunt stacks (`terragrunt.stack.hcl`) in the
middle of a bulk change makes every unit depend on a design decision nobody
reviewed. If the duplication is bad enough to want one of these, say so, and
propose it as its own change.

## Check what a copy inherits silently

These pass every formatter and validator and still produce a wrong unit.

- **State key.** Covered above. Search the template for `remote_state` or a
  `backend` block of its own; a literal `key` means the copy needs its own key
  before it is ever planned.
- **Dependency paths.** `dependency "vpc" { config_path = "../vpc" }` is resolved
  from the unit's own directory. A copy at the same depth points at its own
  tenant's VPC, which is what you want. A copy at a different depth, or a template
  that uses a path climbing into another tenant's tree (`../../acme/prod/vpc`), now
  depends on the wrong unit, and `mock_outputs` can hide that until apply.
- **Parent-folder lookups.** `find_in_parent_folders` resolves from the new
  location. Confirm the file it is meant to find exists at the right level for every
  target, not only for the first one you checked.
- **Generated provider and role.** A `generate "provider"` block, or an
  `iam_role` attribute, may hardcode an account id or role ARN. A copy that keeps
  the template's role will plan and apply against the template's account.
- **Comments and descriptions.** Tags, descriptions and comments that name the
  template tenant are harmless to the infrastructure but tell the next reader the
  wrong thing, and they are how a wrong-tenant value hides in plain sight.

## Create the batch mechanically

Generate the files from the chosen template with a script or a loop that
substitutes the values identified above, not by editing copies one by one. A
generator applies the same substitution to every target; hand edits apply it to
most of them. Keep the generator out of the repository unless the team wants it
there.

Create one unit first, verify it fully (including its plan, where plans may be
run), then generate the rest. A mistake in the template or the substitution then
costs one unit, not five hundred.

On Atlantis, check how projects are discovered. If `atlantis.yaml` lists projects
explicitly, or is generated by a tool such as `terragrunt-atlantis-config`, new
units that are not added or regenerated are never planned. They merge, they look
deployed, and nothing has been created.

## Verify the batch

**Coverage and drift, from the files.** `scripts/compare_units.py`, in this
skill's directory (not the project's), reads only.
It finds every unit file under `--root` whose directory matches `--layout`, groups
them by unit name, and for each group reports:

- `MISSING`: a tenant/environment combination that should have the unit and does
  not;
- `UNEXPECTED`: a unit for a tenant or environment outside the expected set;
- `FOREIGN`: a line that names another tenant's or environment's value, the
  signature of a copy-paste from the wrong place;
- `VARIANT`: units whose content differs from the baseline once their own names are
  replaced with `{tenant}`, `{env}` and so on, with the diff;
- `SHARED STATE KEY` and `LITERAL STATE KEY`: literal state keys, and any shared by
  two units.

```bash
python scripts/compare_units.py --root live --layout "{tenant}/{env}/{unit}" \
  --expect tenant=acme,globex,initech --expect env=dev,stage,prod \
  --unit s3-landing --baseline live/acme/dev/s3-landing/terragrunt.hcl
```

`--layout` takes one entry per directory level below `--root`: a literal, `*` to
ignore that level, or `{name}` to capture it. `{unit}` is required. Pass
`--expect` for every captured dimension to check coverage against the intended
list; without it, coverage is compared against the combinations that exist
anywhere in the tree, which finds holes but cannot tell an intended absence from a
missing unit. `--baseline` names the template, so variants are measured against
the unit you chose rather than against the most common one. It exits 1 when there is
anything to review, 0 when the batch is clean, and `--json` gives the same report
for further processing. It needs Python 3.8 or later and nothing else.

The goal is an exact match between intent and report: every `VARIANT` is a
difference you meant, and there is no `MISSING`, `UNEXPECTED` or `FOREIGN` you
cannot explain. A variant whose only difference is an intended one (a size per
environment) is fine. Say so in the summary rather than leaving the reader to
rediscover it.

**Resolved configuration.** The script compares files. Includes and locals
can still resolve differently, for example when a parent `env.hcl` is missing.
Where the Terragrunt CLI is available, render two units and compare the
resolved inputs:

```bash
terragrunt render --json --working-dir live/acme/prod/s3-landing
```

Older Terragrunt releases call this `render-json`. Rendering evaluates
`dependency` blocks, which may read other units' state and need credentials. If
it cannot run, say that the resolved values were not checked.

**Syntax.** `terragrunt hcl fmt --check` and `terragrunt hcl validate` over the
changed directories (`hclfmt` and `hclvalidate` on older releases). These catch
broken files and nothing else.

**Plans.** When plans may be run, read them against what the change should do:

- A new unit for a new tenant shows only creates.
- A new unit that shows **no changes** is reading an existing state, almost always
  a shared or copied state key. Stop.
- A new unit that shows updates or destroys is reading someone else's state. Stop.
- Existing units outside the batch show no changes.

## Moving a service between repositories

Consolidating a service whose units are spread across several repositories is a
different risk from copying. The resources already exist, and the state recording
them is the thing being moved. Moving the files is the easy half.

**Inventory first.** Before moving anything, list for each unit: its current
path, its state location (bucket and key as resolved, not as written), the
resources in that state (`terragrunt state list`, read-only), what depends on it
(`dependency` blocks elsewhere that point at it, and remote-state data sources in
other repositories that read its outputs), and which pipeline or Atlantis project
applies it. Units that read this one's outputs will break when its state location
changes, and they are often in a repository nobody opened.

**Moving files and moving state are separate steps.** Moving a unit directory with
a path-derived key does not move its state; it points the unit at a new, empty
key. The next plan offers to create every resource again, and on resources with
fixed names that apply fails halfway with half-created duplicates. Do the move in
this order:

1. Stop applies for the affected units in both places (an Atlantis lock, a
   pipeline freeze, or the team's agreement).
2. Back up the current state: `terragrunt state pull > <unit>.tfstate.backup`
   from the old location.
3. Move or copy the unit files to the new location, with the edits the new
   location needs.
4. Establish the state at the new location. For a whole unit moving intact, push
   the backup into the new, empty key (`terragrunt state push`), or copy the state
   object in the backend if the team prefers that. For resources being split or
   merged between units, use `import` blocks at the destination and `removed`
   blocks with `lifecycle { destroy = false }` at the source (Terraform 1.7 or
   later; check the release notes for OpenTofu), rather than `state mv` across
   backends.
5. Plan at the new location. It must show no changes, or only the edits you
   intended. Anything that wants to create or destroy means the state did not land
   where the unit reads it.
6. Remove the unit from the old location, and remove its state from the old key
   only after step 5 is clean. Never run `destroy` at the old location to clean it
   up: it destroys the real resources the new location now manages.
7. Update every consumer found in the inventory, then lift the freeze.

Each state-changing command in steps 2 to 6 is shown and confirmed individually,
per [What this skill changes](#what-this-skill-changes). Do one service end to end
before starting the next. The second service will reuse the sequence, not the
specific commands.

Which backend and key scheme the project uses, who may apply, and how locks are
taken all vary by project. When they are not in this skill's project context
section, ask rather than infer them from one example.

## What the project has to supply

This skill is generic. On a real project it needs facts that only the repository
or the team can give, and `PROJECT-ADAPTATION` records them in a project context
section at the end of this file:

- the repository and root directory that hold units, and the layout pattern for
  `--layout`;
- the list of tenants and environments, or where that list is kept;
- the shared config files in use (`root.hcl`, `env.hcl`, `account.hcl`, others)
  and what each provides;
- the state backend and how the key is derived;
- how Atlantis or CI discovers projects, and who may plan and apply;
- the Terragrunt and Terraform or OpenTofu versions, which decide the command
  names above.

## Anti-patterns

- Copying the first instance found instead of comparing all of them
- Treating the majority variant as correct without knowing why the others differ
- Editing hundreds of copies by hand instead of generating them from one template
- A literal state key in a unit that is about to be copied
- A new include layer or shared file introduced as part of a bulk change
- Declaring the batch done because `hcl fmt` and `validate` passed
- Moving a unit directory and treating the resulting plan, which recreates
  everything, as expected
- Running `destroy` at the old location after a move
