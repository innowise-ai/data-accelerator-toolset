"""Regression coverage for the Terraform review script (stdlib only)."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = (Path(__file__).resolve().parents[1] / "artifacts" /
          "TERRAFORM-PLAN-REVIEW" / "scripts" / "plan_summary.py")


def resource(actions, before, after, unknown=None, **extra):
    return {
        "address": "terraform_data.example", "mode": "managed", "type": "terraform_data",
        "change": dict(actions=actions, before=before, after=after,
                       after_unknown=unknown or {}, **extra),
    }


def plan(resources=(), drift=(), **extra):
    return dict(format_version="1.2", terraform_version="1.16.5", planned_values={},
                resource_changes=list(resources), resource_drift=list(drift), **extra)


class PlanSummaryTests(unittest.TestCase):
    def run_plan(self, data):
        with tempfile.TemporaryDirectory(prefix="plan-summary-test-") as directory:
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), str(path)],
                capture_output=True, text=True,
            )
        self.assertNotIn("Traceback", result.stderr)
        return result.returncode, result.stdout + result.stderr

    def test_exit_codes(self):
        cases = [(plan(), 0), ({"format_version": "1.0", "values": {}}, 1),
                 ([], 1), (plan(errored=True), 3), (plan(complete=False), 3)]
        for actions in (["delete"], ["delete", "create"], ["create", "delete"]):
            cases.append((plan([resource(actions, {"input": "old"}, {"input": "new"})]), 2))
        for data, expected in cases:
            with self.subTest(data=data):
                self.assertEqual(self.run_plan(data)[0], expected)

    def test_nested_unknown_in_empty_container(self):
        for before, after, unknown, label in (
            ({}, {}, {"new_key": True}, "input.new_key"),
            (None, {}, {"new_key": True}, "input.new_key"),
            ([], [None], [True], "input[0]"),
        ):
            with self.subTest(before=before, after=after):
                rc = resource(["update"], {"input": before}, {"input": after}, {"input": unknown})
                code, output = self.run_plan(plan([rc]))
                self.assertEqual(code, 0)
                self.assertIn("known after apply: " + label, output)

    def test_nested_unknown_policy(self):
        rc = resource(["update"], {"inline_policy": [{"policy": "old"}]},
                      {"inline_policy": [{}]}, {"inline_policy": [{"policy": True}]})
        rc.update(address="aws_iam_role.runner", type="aws_iam_role")
        _, output = self.run_plan(plan([rc]))
        self.assertIn("inline_policy[0].policy is known only after apply", output)

    def test_null_members_are_changes(self):
        for before, after, label in (
            ({}, {"added": None}, "input.added"),
            ({"removed": None}, {}, "input.removed"),
            ([], [None], "input[0]"),
            ([None], [], "input[0]"),
        ):
            with self.subTest(before=before, after=after):
                _, output = self.run_plan(plan([resource(["update"], {"input": before}, {"input": after})]))
                self.assertIn("changes: " + label, output)

    def test_null_empty_values_remain_visible(self):
        for empty in ("", [], {}):
            for before, after in ((None, empty), (empty, None)):
                with self.subTest(before=before, after=after):
                    _, output = self.run_plan(plan([resource(["update"], {"input": before}, {"input": after})]))
                    self.assertIn("input (null/empty)", output)

    def test_sensitive_keys_are_hidden_in_updates_and_replacement_reasons(self):
        for marker in ("before_sensitive", "after_sensitive"):
            for actions in (["update"], ["delete", "create"]):
                with self.subTest(marker=marker, actions=actions):
                    rc = resource(actions, {"input": {"SYNTHETIC_SECRET_KEY": "SECRET_BEFORE"}},
                                  {"input": {"SYNTHETIC_SECRET_KEY": "SECRET_AFTER"}},
                                  **{marker: {"input": True}})
                    rc["change"]["replace_paths"] = [["input", "SYNTHETIC_SECRET_KEY"]]
                    _, output = self.run_plan(plan([rc]))
                    self.assertNotIn("SYNTHETIC_SECRET_KEY", output)
                    self.assertNotIn("SECRET_BEFORE", output)
                    self.assertNotIn("SECRET_AFTER", output)
                    self.assertIn("input (sensitive)", output)

    def test_sensitive_unknown_paths_and_access_flags_are_hidden(self):
        rc = resource(["update"], {"inline_policy": [{}]}, {"inline_policy": [{}]},
                      {"inline_policy": [{"SYNTHETIC_SECRET_KEY": True}]},
                      after_sensitive={"inline_policy": [True]})
        rc.update(address="aws_iam_role.runner", type="aws_iam_role")
        _, output = self.run_plan(plan([rc]))
        self.assertNotIn("SYNTHETIC_SECRET_KEY", output)
        self.assertIn("inline_policy[0] (sensitive)", output)
        self.assertIn("is known only after apply", output)

    def test_sensitive_drift_paths_are_hidden_in_all_outcomes(self):
        drift = resource(["update"], {"input": {"SYNTHETIC_SECRET_KEY": "old"}},
                         {"input": {"SYNTHETIC_SECRET_KEY": "manual"}})
        for marker_owner in ("drift", "target"):
            for outcome in ("revert", "keep", "unknown", "empty"):
                with self.subTest(marker_owner=marker_owner, outcome=outcome):
                    current = copy.deepcopy(drift)
                    if outcome == "empty":
                        current["change"]["after"]["input"]["SYNTHETIC_SECRET_KEY"] = ""
                    value = {"keep": "manual", "revert": "old", "unknown": None, "empty": None}[outcome]
                    target = resource(["update"], current["change"]["after"],
                                      {"input": {"SYNTHETIC_SECRET_KEY": value}},
                                      {"input": {"SYNTHETIC_SECRET_KEY": True}} if outcome == "unknown" else {})
                    owner = current if marker_owner == "drift" else target
                    owner["change"]["before_sensitive"] = {"input": True}
                    # A no-op target still supplies sensitivity for drift labels.
                    if outcome == "keep":
                        target["change"]["actions"] = ["no-op"]
                    _, output = self.run_plan(plan([target], [current]))
                    self.assertNotIn("SYNTHETIC_SECRET_KEY", output)
                    self.assertIn("input (sensitive)", output)

    def test_prior_drift_regressions(self):
        drift = resource(["update"], {"input": 3600}, {"input": 14400})
        for actions in (["update"], ["delete", "create"], ["create", "delete"], ["delete"]):
            with self.subTest(actions=actions):
                target = resource(actions, {"input": 14400}, None if actions == ["delete"] else {"input": 3600})
                self.assertIn("this plan undoes", self.run_plan(plan([target], [drift]))[1])
        drift = resource(["update"], {"tags": {"incident": "off", "team": "old"}},
                         {"tags": {"incident": "on", "team": "old"}})
        target = resource(["update"], drift["change"]["after"],
                          {"tags": {"incident": "on", "team": "new"}})
        output = self.run_plan(plan([target], [drift]))[1]
        self.assertNotIn("this plan undoes", output)
        self.assertIn("left as it is", output)

    def test_external_deletion_outcomes(self):
        drift = resource(["delete"], {"input": "old"}, None)
        self.assertIn("does not create it again", self.run_plan(plan(drift=[drift]))[1])
        target = resource(["create"], None, {"input": "new"})
        self.assertIn("this plan creates it again", self.run_plan(plan([target], [drift]))[1])

    def test_null_member_drift_is_not_lost(self):
        drift = resource(["update"], {"input": {}}, {"input": {"added": None}})
        target = resource(["update"], drift["change"]["after"], {"input": {}})
        output = self.run_plan(plan([target], [drift]))[1]
        self.assertIn("this plan undoes", output)
        self.assertIn("input.added", output)


if __name__ == "__main__":
    unittest.main()
