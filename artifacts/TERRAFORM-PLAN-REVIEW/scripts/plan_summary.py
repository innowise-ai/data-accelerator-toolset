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
    1  the input could not be read, or is not a saved plan
    2  at least one resource is destroyed or replaced
    3  the plan errored or is incomplete, so it cannot show that nothing is destroyed
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


LIST_LIMIT = 8


def is_empty(value):
    return value is None or value == {} or value == [] or value == ""


def diff_paths(before, after, unknown=None, path=()):
    """Leaf paths where `before` and `after` differ, as (path, kind) pairs.

    kind is "unknown" when the value is known only after apply, "empty" when
    the difference is only null against an empty string, list or map, and
    "changed" otherwise. An "empty" difference is still a difference: it is
    labelled, not dropped, because a provider reading an unset value back as
    empty and a real change to an empty value look the same in the JSON.
    """
    if unknown is True:
        return [(path, "unknown")]
    if before is None and after is None:
        return []
    if all(v is None or isinstance(v, dict) for v in (before, after)):
        if is_empty(before) and is_empty(after):
            return [] if before == after else [(path, "empty")]
        b, a = before or {}, after or {}
        u = unknown if isinstance(unknown, dict) else {}
        found = []
        for key in sorted(set(b) | set(a) | set(u)):
            found += diff_paths(b.get(key), a.get(key), u.get(key), path + (key,))
        return found
    if all(v is None or isinstance(v, list) for v in (before, after)):
        if is_empty(before) and is_empty(after):
            return [] if before == after else [(path, "empty")]
        b, a = before or [], after or []
        u = unknown if isinstance(unknown, list) else []
        found = []
        for i in range(max(len(b), len(a), len(u))):
            found += diff_paths(
                b[i] if i < len(b) else None,
                a[i] if i < len(a) else None,
                u[i] if i < len(u) else None,
                path + (i,),
            )
        return found
    if before == after:
        return []
    if is_empty(before) and is_empty(after):
        return [(path, "empty")]
    return [(path, "changed")]


def value_at(value, path):
    for step in path:
        if isinstance(value, dict) and step in value:
            value = value[step]
        elif isinstance(value, list) and isinstance(step, int) and step < len(value):
            value = value[step]
        else:
            return None
    return value


def unknown_at(marker, path):
    # True when the value at `path`, or anything above or below it, is unknown.
    for step in path:
        if marker is True:
            return True
        if isinstance(marker, dict):
            marker = marker.get(step)
        elif isinstance(marker, list) and isinstance(step, int) and step < len(marker):
            marker = marker[step]
        else:
            return False
    return contains_unknown(marker)


def contains_unknown(marker):
    if marker is True:
        return True
    if isinstance(marker, dict):
        return any(contains_unknown(v) for v in marker.values())
    if isinstance(marker, list):
        return any(contains_unknown(v) for v in marker)
    return False


def format_path(path):
    parts = []
    for step in path:
        parts.append("[%s]" % step if isinstance(step, int) else ".%s" % step)
    return "".join(parts).lstrip(".")


def short_list(items):
    items = list(items)
    shown = ", ".join(items[:LIST_LIMIT])
    if len(items) > LIST_LIMIT:
        shown += ", +%d more" % (len(items) - LIST_LIMIT)
    return shown


def change_paths(change):
    return diff_paths(change.get("before"), change.get("after"), change.get("after_unknown"))


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
    # Every plan, including one with no changes, has planned_values. State JSON
    # (`terraform show -json` without a plan file) shares format_version but has
    # none, and summarising it would report "nothing destroyed".
    if not isinstance(plan, dict) or "planned_values" not in plan:
        print(
            "Not `terraform show -json <planfile>` output: no planned_values. "
            "State JSON, from `terraform show -json` without a plan file, is not a plan.",
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
        if category == "update" or category.startswith("replace"):
            paths = change_paths(change)
            changed = [
                format_path(p) + (" (null/empty)" if kind == "empty" else "")
                for p, kind in paths
                if kind != "unknown"
            ]
            pending = [format_path(p) for p, kind in paths if kind == "unknown"]
            if changed:
                detail.append("changes: %s" % short_list(changed))
            # On a replacement every computed attribute is unknown, so listing
            # them says nothing. On an update an unknown value is worth a look.
            if pending and category == "update":
                detail.append("known after apply: %s" % short_list(pending))
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
            policy_unknown = sorted(
                {
                    format_path(p)
                    for p, kind in change_paths(change)
                    if kind == "unknown" and any("policy" in str(step) for step in p)
                }
            )
            if policy_unknown:
                flags.append(
                    "ACCESS    %s: %s is known only after apply, so this plan does not show it"
                    % (address, short_list(policy_unknown))
                )

    # Terraform prints its "changed outside of Terraform" note only for drift
    # that feeds into another planned change, so a manual fix that this plan
    # reverts usually shows as an ordinary update. Cross-check drift against
    # the plan instead of relying on the note.
    # Each drifted value is compared, path by path, with the value the plan
    # will leave there. A replacement leaves its planned `after`; a destroy
    # leaves nothing.
    planned = {rc.get("address"): rc for rc in plan.get("resource_changes", [])}
    reverted = []
    deleted = []
    kept = []
    for rc in plan.get("resource_drift") or []:
        address = rc.get("address", "?")
        drift = rc.get("change", {})
        target = planned.get(address, {}).get("change", {})
        planned_category = classify(target.get("actions", ["no-op"]))

        if classify(drift.get("actions", [])) == "destroy":
            if planned_category == "create" or planned_category.startswith("replace"):
                outcome = "this plan creates it again"
            else:
                outcome = "this plan does not create it again"
            deleted.append("%s  [%s]" % (address, outcome))
            flags.append("DRIFT     %s was deleted outside Terraform; %s" % (address, outcome))
            continue

        undone, maybe, same = [], [], []
        for path, kind in diff_paths(drift.get("before"), drift.get("after")):
            label = format_path(path) + (" (null/empty)" if kind == "empty" else "")
            manual = value_at(drift.get("after"), path)
            if planned_category == "destroy":
                undone.append(label)
            elif planned_category == "update" or planned_category.startswith("replace"):
                if unknown_at(target.get("after_unknown"), path):
                    maybe.append(label)
                    continue
                result = value_at(target.get("after"), path)
                if result == manual:
                    same.append(label)
                elif is_empty(result) and is_empty(manual):
                    # Kept visible, not flagged: often a provider reading an
                    # unset value back as empty, but not provably so.
                    same.append(format_path(path) + " (null/empty differs)")
                else:
                    undone.append(label)
            else:
                same.append(label)

        if undone:
            reverted.append("%s  [%s; %s]" % (address, planned_category, short_list(undone)))
            flags.append(
                "DRIFT     %s (%s): this plan undoes a change made outside Terraform to %s"
                % (address, planned_category, short_list(undone))
            )
        if maybe:
            reverted.append("%s  [%s; may undo, known after apply: %s]"
                            % (address, planned_category, short_list(maybe)))
            flags.append(
                "DRIFT     %s (%s): may undo a change made outside Terraform to %s; "
                "the planned value is known only after apply" % (address, planned_category, short_list(maybe))
            )
        if same:
            kept.append("%s  [%s]" % (address, short_list(same)))

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

    if deleted:
        lines.append("")
        lines.append("Deleted outside Terraform (%d):" % len(deleted))
        lines.extend("  " + item for item in deleted)
    if reverted:
        lines.append("")
        lines.append("Changed outside Terraform and undone, or possibly undone, by this plan:")
        lines.extend("  " + item for item in reverted)
    if kept:
        lines.append("")
        lines.append(
            "Changed outside Terraform and left as it is by this plan (%d); often values "
            "the provider reads back, check if unexpected:" % len(kept)
        )
        lines.extend("  " + item for item in kept)

    print("\n".join(lines))
    if warnings:
        return 3
    return 2 if destroyed else 0


if __name__ == "__main__":
    sys.exit(main())
