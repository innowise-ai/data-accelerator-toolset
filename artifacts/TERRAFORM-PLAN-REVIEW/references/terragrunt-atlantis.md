# Terragrunt and Atlantis

Read this when the project keeps its Terraform in modules and its per-environment
configuration in Terragrunt unit files, or applies through Atlantis. Both add a
layer between the code a reviewer reads and the plan that gets applied, and each
layer has its own way of making the plan differ from what the code appears to say.

Project-specific rules, such as which repository holds what and who may apply, come
from the project; see "What the project supplies" in the skill. What follows is the
generic flow.

## Terragrunt

### How a module is referenced

A unit file (`terragrunt.hcl` in each environment directory) points at a module
through `terraform { source = ... }`:

```hcl
terraform {
  source = "git::https://github.com/my-org/infra-modules.git//modules/sqs-queue?ref=v1.4.0"
}
```

The double slash separates the repository from the path inside it, and `ref` picks
the version. Check that `ref` is a tag or a commit SHA. A branch name such as `main`
is a moving target: the same unit file plans different code on different days, and
the plan the reviewer approved is not reproducible. A missing `ref` is the same
problem. Registry modules use `tfr:///` sources with a version, which is pinned in
the same sense.

When a pull request changes a module and the units that use it, check which units
actually moved to the new `ref`. A module change that no unit references yet has no
plan; a unit that moved to a new `ref` picks up every module change between the two
versions, not only the one the pull request describes. Compare the module diff
between the old and new refs.

### What belongs in the unit file and what in the module

The unit file says which module, which version, which inputs, and which other units
it depends on, and includes the shared root configuration for state and providers.
The module holds the resources. Resource logic in a unit file, typically through
`generate` blocks that write `.tf` files beyond the provider and backend, makes the
environment differ from the module everyone else reviewed. Environment-specific
values in a module, such as an account ID or a bucket name, make the module wrong
for every other environment.

### Inputs that are silently ignored

Terragrunt passes `inputs = { ... }` to Terraform as `TF_VAR_<name>` environment
variables, and Terraform does not complain about an environment variable for a
variable the module does not declare. A misspelled input key, or a key for a
variable that was renamed in a new module version, is dropped without an error, and
the module uses its default. Compare the input keys in the unit file with the
`variable` blocks of the module version it references. This is the main reason
environment-specific variables should have no default: then a dropped input fails
the plan instead of passing it.

### Plans built on mock outputs

A `dependency` block reads another unit's outputs. When that unit has not been
applied yet, `mock_outputs` provide placeholder values so the plan can run:

```hcl
dependency "queue" {
  config_path = "../sqs-queue"
  mock_outputs = {
    queue_arn = "arn:aws:sqs:eu-west-1:000000000000:mock"
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}
```

A plan built on mock outputs shows the mock values, and a saved plan keeps them: the
placeholders are written into the plan file, and applying that file applies them,
whatever happened to the dependency since. A policy granting access to `...:mock`
tells the reviewer nothing about the real ARN, and applied from a saved plan it
grants access to `...:mock`. Excluding `apply` from
`mock_outputs_allowed_terraform_commands` stops a fresh `terragrunt apply` from
using mocks; it does not reach into a plan file that already holds them.

So check whether each dependency was already applied. Where it was not, the plan is
not reviewable as final: apply the dependency first, then re-plan the consumer with
the real outputs and review that plan. Never approve or apply a saved plan that
contains mock values. The Terragrunt documentation warns about exactly this for
saved plans and has no built-in safeguard against it.

### Running across units

`terragrunt run-all plan`, written `terragrunt run --all plan` in newer releases,
plans every unit below the current directory in dependency order. The output is one
plan per unit, interleaved. Review each unit's plan on its own, with its own
summary, and confirm the set of units with changes is the set the pull request meant
to touch. To use the summary script, save and convert each unit's plan:
`terragrunt plan -out=tfplan`, then `terragrunt show -json tfplan > plan.json` in
that unit's directory.

## Atlantis

### The flow

1. A pull request that changes planned paths triggers `plan` automatically, or on an
   `atlantis plan` comment. Atlantis posts the plan as a comment and locks those
   projects so no other pull request can plan them.
2. Every new commit invalidates the plan. With autoplan, Atlantis re-plans and posts
   a new comment; without it, someone has to comment `atlantis plan` again.
3. Someone comments `atlantis apply`. Atlantis applies the saved plan for the current
   commit, if the apply requirements pass.
4. The pull request is merged after the apply, and the lock is released.

Applying before merging is the defining property. The base branch reflects what was
applied only if every applied pull request is merged, so an applied but abandoned
pull request leaves the infrastructure ahead of the code, and the next plan on any
other pull request shows it as a change to revert.

### What an approval covers

`apply_requirements` (commonly `approved`, `mergeable`, `undiverged`), configured in
the server-side repository configuration, decide when `atlantis apply` is allowed. A
repository's own `atlantis.yaml` can change them only where the server allows the
override. Three gaps to check:

- **Approval is on the pull request, not on the plan.** A reviewer who approved
  before the last commit approved a plan that no longer exists. Unless branch
  protection dismisses stale approvals, the old approval still satisfies `approved`.
  Re-read the latest plan comment before approving or applying.
- **`undiverged`** blocks apply when the base branch has changed since the most recent
  plan. It works only with `--checkout-strategy merge`, where Atlantis plans a
  temporary merge of the pull request into the base. It does not require the pull
  request branch itself to be up to date. With the default `branch` strategy,
  Atlantis plans the pull request branch as it is, and `undiverged` gives no
  protection: a plan can be built against code that is missing a change already
  merged and applied, and apply then reverts that change. Check the server's
  checkout strategy before relying on the requirement. Under `branch`, ask for the
  pull request to be rebased onto the base and re-planned before apply.
- **Who may comment `atlantis apply`.** By default anyone who can comment and passes
  the requirements. Team allowlists and policy checks narrow it. This is a project
  fact, not something to assume.

### Terragrunt under Atlantis

Atlantis runs Terraform by default. A Terragrunt repository needs a custom workflow
that runs `terragrunt plan` and `terragrunt apply`, and a list of projects, often
generated into `atlantis.yaml` by a tool such as `terragrunt-atlantis-config`. Check
that a unit changed by the pull request appears as an Atlantis project. A unit
missing from the list is never planned, and its change is silently not applied.
Check too that a module change triggers a plan for the units that depend on it,
since Atlantis decides what to plan from the files changed.
