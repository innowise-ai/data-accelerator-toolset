#!/usr/bin/env python3
"""
Summarise a Terraform plan for review, from the JSON form of a saved plan.

Prints what will be destroyed, replaced, changed, created, moved, imported and
forgotten, which resources drifted outside Terraform, and which changes touch
stateful or access-control resources. Prints attribute names only, never values:
the JSON plan holds sensitive values in plain text.

Standard library only. Python 3.8+.

Usage:
    terraform plan -out=tfplan
    terraform show -json tfplan > plan.json
    python plan_summary.py plan.json
    python plan_summary.py plan.json --stateful 'snowflake_*' --stateful databricks_catalog

Exit codes:
    0  nothing is destroyed or replaced
    1  the input could not be read
    2  at least one resource is destroyed or replaced
"""

import argparse
import fnmatch
import json
import sys

# Resources whose destruction loses data or identity that a re-create does not
# bring back. Extend per project with --stateful.
DEFAULT_STATEFUL = [
    "aws_s3_bucket",
    "aws_db_instance",
    "aws_rds_cluster",
    "aws_dynamodb_table",
    "aws_sqs_queue",
    "aws_sns_topic",
    "aws_kinesis_stream",
    "aws_msk_cluster",
    "aws_kms_key",
    "aws_secretsmanager_secret",
    "aws_efs_file_system",
    "aws_ebs_volume",
    "aws_redshift_cluster",
    "aws_opensearch_domain",
    "aws_elasticache_*",
    "aws_glue_catalog_database",
    "aws_glue_catalog_table",
    "aws_ecr_repository",
    "aws_cloudwatch_log_group",
    "aws_iam_role",
    "aws_iam_user",
    "google_storage_bucket",
    "google_bigquery_dataset",
    "google_bigquery_table",
    "google_sql_database_instance",
    "azurerm_storage_account",
    "azurerm_mssql_database",
]

# Resources that decide who can do what. A change here needs the policy read,
# not only the plan line.
ACCESS_PATTERNS = [
    "*_iam_*",
    "*_policy",
    "*_policy_attachment",
    "*_acl",
    "*public_access_block*",
    "aws_lambda_permission",
    "aws_kms_grant",
]

DESTRUCTIVE = {"delete"}


def matches(resource_type, patterns):
    return any(fnmatch.fnmatchcase(resource_type, p) for p in patterns)


def classify(actions):
    """Map Terraform's action list to one review category."""
    actions = list(actions)
    if actions == ["delete", "create"]:
        return "replace (destroy first)"
    if actions == ["create", "delete"]:
        return "replace (create first)"
    if len(actions) == 1:
        return {
            "create": "create",
            "update": "update",
            "delete": "destroy",
            "read": "read",
            "no-op": "no-op",
            "forget": "forget",
        }.get(actions[0], actions[0])
    return "+".join(actions)


def changed_attributes(change):
    """Top-level attribute names whose value changes or becomes unknown."""
    before = change.get("before") or {}
    after = change.get("after") or {}
    unknown = change.get("after_unknown") or {}
    if not isinstance(before, dict) or not isinstance(after, dict):
        return [], []
    changed = []
    pending = []
    for key in sorted(set(before) | set(after) | set(unknown)):
        if unknown.get(key) is True:
            pending.append(key)
        elif before.get(key) != after.get(key):
            changed.append(key)
    return changed, pending


def format_path(path):
    parts = []
    for step in path:
        parts.append("[%s]" % step if isinstance(step, int) else ".%s" % step)
    return "".join(parts).lstrip(".")


def load(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as error:
        print("Cannot read plan JSON %s: %s" % (path, error), file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("plan_json", help="output of `terraform show -json <planfile>`")
    parser.add_argument(
        "--stateful",
        action="append",
        default=[],
        metavar="TYPE",
        help="extra resource type (glob allowed) to treat as stateful; repeatable",
    )
    args = parser.parse_args()

    plan = load(args.plan_json)
    if "resource_changes" not in plan and "format_version" not in plan:
        print(
            "This does not look like `terraform show -json` output for a saved plan.",
            file=sys.stderr,
        )
        sys.exit(1)

    stateful = DEFAULT_STATEFUL + args.stateful
    lines = []
    warnings = []

    if plan.get("errored"):
        warnings.append("The plan errored. Terraform cannot apply it; do not review it as final.")
    if plan.get("complete") is False:
        warnings.append(
            "The plan is incomplete: some changes are deferred to a later plan and are not shown."
        )

    groups = {}
    flags = []
    for rc in plan.get("resource_changes", []):
        change = rc.get("change", {})
        actions = change.get("actions", [])
        category = classify(actions)
        address = rc.get("address", "?")
        rtype = rc.get("type", "")
        detail = []

        if rc.get("previous_address") and rc["previous_address"] != address:
            groups.setdefault("moved", []).append(
                "%s  (was %s)" % (address, rc["previous_address"])
            )
        if change.get("importing"):
            groups.setdefault("import", []).append(address)
        if category in ("no-op",):
            continue

        if rc.get("action_reason"):
            detail.append("reason: %s" % rc["action_reason"])
        if change.get("replace_paths"):
            detail.append(
                "forced by: %s" % ", ".join(format_path(p) for p in change["replace_paths"])
            )
        if category in ("update",) or category.startswith("replace"):
            changed, pending = changed_attributes(change)
            if changed:
                detail.append("changes: %s" % ", ".join(changed))
            if pending:
                detail.append("known after apply: %s" % ", ".join(pending))
        if rc.get("deposed"):
            detail.append("deposed object %s" % rc["deposed"])

        line = address + ("  [%s]" % "; ".join(detail) if detail else "")
        groups.setdefault(category, []).append(line)

        if DESTRUCTIVE & set(actions) and rc.get("mode") == "managed":
            if matches(rtype, stateful):
                flags.append(
                    "STATEFUL  %s (%s): its data or identity does not come back with a re-create"
                    % (address, category)
                )
        if rc.get("mode") == "managed" and matches(rtype, ACCESS_PATTERNS):
            flags.append("ACCESS    %s (%s): read the policy itself" % (address, category))
            _, pending = changed_attributes(change)
            policy_unknown = [k for k in pending if "policy" in k]
            if policy_unknown:
                flags.append(
                    "ACCESS    %s: %s is known only after apply, so this plan does not show it"
                    % (address, ", ".join(policy_unknown))
                )

    order = [
        "destroy",
        "replace (destroy first)",
        "replace (create first)",
        "forget",
        "update",
        "create",
        "read",
        "moved",
        "import",
    ]
    counts = {key: len(groups.get(key, [])) for key in order}
    destroyed = counts["destroy"] + counts["replace (destroy first)"] + counts[
        "replace (create first)"
    ]

    lines.append(
        "Terraform %s plan: %d destroy, %d replace, %d update, %d create, %d forget, "
        "%d moved, %d import"
        % (
            plan.get("terraform_version", "?"),
            counts["destroy"],
            counts["replace (destroy first)"] + counts["replace (create first)"],
            counts["update"],
            counts["create"],
            counts["forget"],
            counts["moved"],
            counts["import"],
        )
    )
    for warning in warnings:
        lines.append("WARNING   " + warning)

    if flags:
        lines.append("")
        lines.append("Needs a human decision:")
        lines.extend("  " + flag for flag in flags)

    for key in order + sorted(k for k in groups if k not in order):
        if not groups.get(key):
            continue
        lines.append("")
        lines.append("%s (%d):" % (key, len(groups[key])))
        lines.extend("  " + item for item in groups[key])

    drift = plan.get("resource_drift") or []
    if drift:
        lines.append("")
        lines.append(
            "Changed outside Terraform since the last apply (%d). Where the code still "
            "says otherwise, the changes above revert them:" % len(drift)
        )
        for rc in drift:
            change = rc.get("change", {})
            changed, _ = changed_attributes(change)
            what = classify(change.get("actions", []))
            lines.append(
                "  %s  [%s%s]"
                % (rc.get("address", "?"), what, "; " + ", ".join(changed) if changed else "")
            )

    print("\n".join(lines))
    return 2 if destroyed else 0


if __name__ == "__main__":
    sys.exit(main())
