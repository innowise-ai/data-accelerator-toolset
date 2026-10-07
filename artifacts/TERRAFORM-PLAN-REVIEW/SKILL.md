---
name: terraform-plan-review
description: Read a Terraform plan before it is applied - what it destroys or replaces, what drifted, what changes access - and restate it per resource in plain language, so a reviewer without deep Terraform knowledge can approve or stop it. Use when an agent has written or proposes a Terraform or Terragrunt change, or when someone has to approve a plan, including in Atlantis.
---

# Review a Terraform plan before it is applied

The code in a Terraform pull request is not the change. The plan is. A one-word
rename in the code can destroy a bucket, and a long diff can change nothing at all.
When an agent writes the Terraform and a person approves it, the person is usually
reviewing "on a logical level": does this look like what we asked for. That works
only if someone has turned the plan into statements a non-specialist can check.
This skill is that step. The agent uses it before proposing a change, and the
reviewer uses it before approving one.

Review the plan first and read the code to explain it, not the other way round. A
finding in the code matters because of what it does to the plan.

## What this skill changes

Nothing, by default. Reading code and plans, and running `terraform fmt -check`,
`terraform validate`, `terraform plan` and `terraform show`, are allowed. Know what
`plan` does even so: it takes the state lock, calls the provider's read APIs with
real credentials, and in Terragrunt a `run --all` plan touches every unit below the
current directory. Plan only the units and the environment the change targets.

Never run `apply`, `destroy`, `import`, `state rm`, `state mv`, `state push`,
`taint`, `untaint`, `force-unlock` or `init -upgrade`, and never comment
`atlantis apply`, without an explicit yes for that command from the person who owns
the environment. Each of these changes real infrastructure, the state file, or the
provider versions the next plan is built with.

**A plan file is a secret.** The saved plan and its JSON form hold sensitive values
in plain text: `sensitive = true` only redacts the console output. Even the console
output is not safe to paste whole, because a value redacted in one attribute can be
printed in another that the provider did not mark sensitive. Do not paste a plan,
`plan.json` or state into chat, a pull request comment or a ticket. Summarise it with
`scripts/plan_summary.py`, which prints attribute names and never values.

## Get the plan in a form you can check

```bash
terraform plan -out=tfplan
terraform show -json tfplan > plan.json
python scripts/plan_summary.py plan.json      # path relative to this skill
```

The script groups every resource by what will happen to it, gives the reason
Terraform recorded, flags destroyed stateful resources and every access-control
change, and lists drift. It exits `0` only when the plan is complete and nothing is
destroyed or replaced: `2` means something is, `3` that the plan errored or is
incomplete and so cannot show it, and `1` that the input is unreadable or is not a
saved plan (state JSON, from `terraform show -json` without a plan file, is
rejected). That lets it gate a pipeline as well as inform a reviewer. Pass `--stateful <type>` (globs allowed) for resource
types the project treats as stateful beyond its built-in list.

Review the plan that will be applied. In Atlantis that is the plan comment for the
latest commit on the pull request; a plan for an earlier commit describes a change
that no longer exists. Locally it is the saved `tfplan`, applied by name, not a new
plan run at apply time.

## Read the plan in this order

### 1. Did it finish, and does the count match the claim

A plan that errored, or one Terraform marks incomplete because some changes were
deferred, is not reviewable as final. Then read the summary line,
`Plan: 3 to add, 3 to change, 4 to destroy`, against what the pull request says it
does. "Add an SQS queue" with four to destroy is the finding, before any detail.
Unexpected resources usually mean someone else's unapplied change is on the base
branch, or a provider upgrade in `.terraform.lock.hcl` changed how existing
resources are read.

### 2. Every destroy and every replacement

| Console marker | JSON `actions` | Meaning |
|---|---|---|
| `+` | `["create"]` | New object |
| `~` | `["update"]` | Changed in place; the object survives |
| `-` | `["delete"]` | Destroyed |
| `-/+` | `["delete","create"]` | Replaced, old one destroyed first: there is a gap with neither |
| `+/-` | `["create","delete"]` | Replaced, new one created first (`create_before_destroy`) |
| `<=` | `["read"]` | Data source read during apply, so its value is not in this plan |

The attribute that forces a replacement carries `# forces replacement` in the
console output and appears in `replace_paths` in the JSON. Each change also carries
an `action_reason`, and the reason is what tells you whether the destroy was meant:

| `action_reason` | What it usually means |
|---|---|
| `delete_because_no_resource_config` | The block was removed, or renamed without a `moved` block |
| `delete_because_no_module` | A module call was removed or renamed |
| `delete_because_count_index` | A `count` list got shorter; see the index shift below |
| `delete_because_each_key` | A `for_each` key disappeared or was renamed |
| `delete_because_wrong_repetition` | The resource switched between `count`, `for_each` and a single instance; any address no `moved` block covers is destroyed |
| `replace_because_cannot_update` | An attribute the cloud cannot change in place was changed (a bucket or queue name, a database identifier) |
| `replace_because_tainted` | A previous apply failed half way; Terraform will rebuild it |
| `replace_by_request` | Someone ran `plan -replace=...` on purpose |
| `replace_by_triggers` | A `replace_triggered_by` dependency changed |

A rename or a move into a module should never destroy anything. The fix is a
`moved` block, after which the plan says `has moved to` and the object survives. To
stop managing an object without deleting it, a `removed` block with
`lifecycle { destroy = false }` shows the action `forget`.

**The index shift.** With `count` over a list, removing the first item does not
destroy the first object. Terraform updates every later object to take its
neighbour's value and destroys the last index. For a list of three names with `a`
removed, the plan shows `[0]` updated `a -> b`, `[1]` updated `b -> c`, and `[2]`
destroyed. Where the name cannot change in place, that is a chain of replacements.
The plan is correct and reads as nonsense; the fix is `for_each` keyed by a stable
name.

### 3. Destroys that lose something

Replacing a stateless object, such as a policy attachment or a Lambda permission, is
a short gap. Replacing a stateful one loses what was in it: the objects in a bucket,
the messages in a queue, the rows in a table, everything encrypted under a key once
the key is gone. A replacement can also lose identity rather than data. A recreated
IAM role gets a new internal ID, and trust and resource policies elsewhere that
named the old role stop matching it, even though the ARN text is the same.

Protection is partly in the code. `lifecycle { prevent_destroy = true }` makes the
plan fail rather than destroy, but only while the block exists: deleting the
resource block deletes its protection with it, which is exactly the case it was
meant for. Provider settings such as `deletion_protection` on a database and
`force_destroy = false` on an S3 bucket make the cloud refuse. A change that turns
any of these off is a destroy being prepared, and deserves the same question as a
destroy.

### 4. Updates in place that are not harmless

`~` means the object survives, not that nothing happens to the systems using it. A
lifecycle rule on a bucket can expire existing objects on its first run. A shorter
message retention drops what is already queued. A policy update changes who can do
what immediately. A cluster or instance size change can mean a restart. For every
update, ask what a running job or user notices.

### 5. What the plan cannot show

`(known after apply)` hides the value, not the risk. Policy documents built from the
ARNs of resources created in the same plan are the common case: the plan says the
policy will change and does not say to what. Read the expression in the code that
builds it, and state in the review that the final document was not seen. A data
source marked `<=` is read during apply for the same reason.

### 6. Drift

Drift is what someone changed by hand since the last apply, usually a fix in the
console during an incident. Where the code still says otherwise, the plan undoes the
fix, and the console output rarely says so. Terraform prints
`Objects have changed outside of Terraform` only for drift that feeds into another
planned change. A manual change that the plan simply reverts appears as an ordinary
update, such as `max_session_duration = 14400 -> 3600`, and reads as if the pull
request made it.

So check every updated attribute against the code diff. An update to an attribute
the diff does not touch is drift being reverted, or an upstream change on the base
branch. The JSON lists drift in `resource_drift`, and the summary script
cross-checks it against the planned changes and flags each revert. Do not approve a
plan that reverts drift until someone decides whether the manual change goes into
the code or is deliberately undone. `terraform plan -refresh-only` shows the drift on
its own.

## Say it in plain language, per resource

Restate every resource that is not a no-op as a sentence a reviewer who knows the
system, but not Terraform, can check against their intent. Name the thing in the
system's terms, not the resource type; say what happens to it, what a running job or
user will notice, and whether it can be undone.

| Resource | What will happen | Who notices | Undo |
|---|---|---|---|
| `aws_s3_bucket.landing` | The landing bucket is deleted and recreated under a new name, because the name changed. Files in it are lost. | Every ingestion job writing to it, until they are repointed | No |
| `aws_iam_role_policy.databricks_jobs` | The role Databricks jobs run as gains write access to the curated bucket | Nobody, until a job writes somewhere it should not | Yes, by reverting |
| `aws_sqs_queue.events_dlq` | A new dead-letter queue is created and attached to the events queue | Nobody; failed messages now land there instead of being dropped | Yes |

Then give a verdict: approve, approve with a stated risk, or stop, followed by the
questions the author must answer. Keep what the plan shows separate from what you
inferred from the code. If the restatement needs Terraform knowledge to follow, it is
not finished.

## Module and variable hygiene

When the change touches modules, not only their inputs:

- **Required versus defaulted.** A default that is right for one environment, such
  as an account ID, a bucket name or production sizing, means that forgetting the
  input silently uses it everywhere else. Make environment-specific variables
  required, and keep defaults for values that are safe in every environment.
- **Hardcoded identifiers.** Account IDs, ARNs, regions and bucket names written into
  resources belong in variables or lookups (`data.aws_caller_identity`,
  `data.aws_region`). A hardcoded account ID in a module applied to development and
  production points production at development.
- **Outputs.** What a module outputs becomes another module's input through remote
  state or a Terragrunt `dependency`. Mark secret outputs `sensitive = true`, knowing
  the value is still plain text in state. Output the attributes consumers need, not
  whole objects, so internal changes do not ripple.
- **`count` over a list of names.** See the index shift. Moving an existing resource
  from `count` to `for_each` needs `moved` blocks, or it is a mass replacement.
- **Versions.** `required_version` and `required_providers` constrained, the lock
  file `.terraform.lock.hcl` committed, module sources pinned to a tag or registry
  version rather than a branch.
- **`lifecycle { ignore_changes }`** hides drift permanently. It is acceptable with a
  comment naming who owns the ignored attribute, and a finding without one.

## Access and policies on AWS

When the plan touches IAM roles, policies, trust relationships, or bucket, queue or
key policies, read [references/aws-iam-review.md](references/aws-iam-review.md). It
covers wildcard actions and principals, cross-account and CI trust, attaching a
policy to the right ARN, and the specific trap in data platforms where write access
to a code bucket means running code as the job's role.

## Terragrunt and Atlantis

When the project wraps Terraform in Terragrunt or applies through Atlantis, read
[references/terragrunt-atlantis.md](references/terragrunt-atlantis.md). It covers
module references and pinning, what belongs in a unit file, inputs that are silently
ignored, plans built on mock outputs, and what an Atlantis approval does and does not
cover.

## Checks you can run, not only read

| Check | Command or pattern | Finding when |
|---|---|---|
| Anything destroyed or replaced | `python scripts/plan_summary.py plan.json` | Exit code `2`; read every line it lists. Exit `3`: the plan is not final, re-plan |
| Plan has changes at all | `terraform plan -detailed-exitcode` | Exit `2` on a change described as a no-op refactor |
| Formatting and syntax | `terraform fmt -check -recursive`, `terraform validate` | Non-zero exit |
| Replacements in console output | search for `must be replaced` and `forces replacement` | Any hit not explained in the pull request |
| Drift being reverted | `DRIFT` lines from the summary script, or `terraform plan -refresh-only` | Any hit; see Drift. The console note alone misses most of them |
| Policy wildcards | see the AWS reference | `"*"` in an action, principal or resource without a condition that narrows it |
| Module pinning | see the Terragrunt reference | A `ref=` that is a branch, or no `ref` |

If the project already runs a policy scanner such as tflint, Checkov or Trivy, its
findings are input to the review. This skill does not require one.

## What the project supplies

A generic review cannot know a project's layout. These are the facts to bind with
`PROJECT-ADAPTATION`, and to ask for when they are missing rather than guess:

- **Repository roles:** where modules live, where the per-environment configuration
  lives, and which paths Atlantis or CI plans.
- **Environments:** which directory, workspace or account is which environment, and
  which one is production.
- **Who may apply:** the approval rule (Atlantis `apply_requirements` and the server's
  `--checkout-strategy`, `CODEOWNERS`, branch protection) and who can run apply.
- **Where plans and logs live:** pull request comments, CI artifacts, the Atlantis UI;
  and where state lives, which is not to be read casually.
- **Project stateful types:** resource types to pass as `--stateful`, such as warehouse
  or catalog objects managed by another provider.
- **Commands:** Terraform and Terragrunt versions and any wrapper scripts or make
  targets the team uses instead of the raw commands.

## Scope

The plan-reading parts are cloud-neutral. The AWS reference is AWS only.
`databricks_*` resources go through the same plan reading, but what replacing a
Databricks object means (a cluster restart, lost job run history, catalog grants) is
not covered here. Writing Terraform is not covered either: the agent already does
that, and this skill is the check after it.

## Related

- `CODE-CHANGE-REVIEW` for the code in the same pull request.
- `PROJECT-ADAPTATION` to bind the facts listed above.
