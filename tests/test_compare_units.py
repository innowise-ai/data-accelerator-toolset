"""CLI regression tests; fixtures never need Terragrunt or cloud credentials."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = (Path(__file__).resolve().parents[1] / "artifacts" /
          "TERRAGRUNT-UNIT-REPLICATION" / "scripts" / "compare_units.py")
CLEAN = 'inputs = { enabled = true }\n'


def state_config(comment="", key="shared/terraform.tfstate"):
    return ('remote_state {\n'
            '  backend = "s3"\n'
            '  config = {\n'
            '    bucket = "central-state"\n'
            '    key = "' + key + '"' + comment + '\n'
            '  }\n'
            '}\n')


class CompareUnitsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="compare-units-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_unit(self, path, text=CLEAN):
        target = self.root / path / "terragrunt.hcl"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return str(target)

    def run_cli(self, *args, json_output=True):
        command = [sys.executable, "-B", str(SCRIPT), "--root", str(self.root),
                   "--layout", "{tenant}/{env}/{unit}"] + list(args)
        if json_output:
            command.append("--json")
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.stderr, "", result.stderr)
        return result.returncode, json.loads(result.stdout) if json_output else result.stdout

    def test_clean_batch_normalizes_inputs_but_preserves_common_source(self):
        for tenant in ("acme", "globex"):
            self.write_unit(tenant + "/dev/s3",
                            'terraform { source = "git::https://example.com/modules.git//s3?ref=v1" }\n'
                            'inputs = { name = "' + tenant + '-dev-bucket" }\n')
        code, report = self.run_cli("--expect", "tenant=acme,globex", "--expect", "env=dev")
        self.assertEqual(code, 0)
        self.assertEqual(report["unit_count"], 2)
        self.assertEqual(report["units"]["s3"]["variants"], [])

    def test_requested_unit_absent_everywhere_reports_expected_combinations(self):
        self.write_unit("acme/dev/vpc")
        code, report = self.run_cli("--unit", "s3", "--expect", "tenant=acme,globex",
                                    "--expect", "env=dev")
        self.assertEqual(code, 1)
        entry = report["units"]["s3"]
        self.assertEqual(entry["missing"], [{"tenant": "acme", "env": "dev"},
                                            {"tenant": "globex", "env": "dev"}])
        self.assertIsNone(entry["baseline"])

    def test_one_absent_name_among_multiple_requested_units(self):
        self.write_unit("acme/dev/vpc")
        code, report = self.run_cli("--unit", "vpc", "--unit", "s3")
        self.assertEqual(code, 1)
        self.assertEqual(report["units"]["vpc"]["instances"], 1)
        self.assertEqual(report["units"]["s3"]["missing"], [{"tenant": "acme", "env": "dev"}])

    def test_empty_tree_fails_with_or_without_expected_coverage(self):
        for args in ((), ("--unit", "s3"),
                     ("--unit", "s3", "--expect", "tenant=acme", "--expect", "env=dev")):
            with self.subTest(args=args):
                code, report = self.run_cli(*args)
                self.assertEqual(code, 1)
                self.assertEqual(report["unit_count"], 0)

    def test_absent_unit_text_report_needs_no_baseline(self):
        code, report = self.run_cli("--unit", "s3", json_output=False)
        self.assertEqual(code, 1)
        self.assertIn("NO UNITS", report)
        self.assertIn("MISSING   unit=s3", report)

    def test_single_missing_instance_is_still_reported(self):
        self.write_unit("acme/dev/s3")
        code, report = self.run_cli("--expect", "tenant=acme,globex", "--expect", "env=dev")
        self.assertEqual(code, 1)
        self.assertEqual(report["units"]["s3"]["missing"], [{"tenant": "globex", "env": "dev"}])

    def test_single_literal_key_requires_review(self):
        self.write_unit("acme/dev/s3", state_config())
        code, report = self.run_cli()
        self.assertEqual(code, 1)
        self.assertEqual(len(report["units"]["s3"]["literal_state_keys"]), 1)
        self.assertEqual(report["shared_state_keys"], [])

    def test_shared_keys_survive_all_hcl_comment_styles(self):
        for comment in ("", " # backend state", " // backend state", " /* backend state */",
                        " /* backend\n state */"):
            with self.subTest(comment=comment):
                for tenant in ("acme", "globex"):
                    self.write_unit(tenant + "/dev/s3", state_config(comment))
                code, report = self.run_cli()
                self.assertEqual(code, 1)
                self.assertEqual(len(report["shared_state_keys"]), 1)
                self.assertEqual(len(report["shared_state_keys"][0]["files"]), 2)

    def test_commented_keys_are_ignored_and_string_markers_are_preserved(self):
        self.write_unit("acme/dev/s3",
                        '/* remote_state {\n key = "not-active"\n} */\n' +
                        state_config(key="prefix//state#snapshot"))
        self.write_unit("globex/dev/s3", state_config(key="prefix//state#snapshot"))
        code, report = self.run_cli()
        self.assertEqual(code, 1)
        self.assertEqual([item["key"] for item in report["shared_state_keys"]],
                         ["prefix//state#snapshot"])

    def test_dynamic_keys_do_not_trigger_literal_warning(self):
        self.write_unit("acme/dev/s3", state_config(key="${path_relative_to_include()}/terraform.tfstate"))
        code, report = self.run_cli()
        self.assertEqual(code, 0)
        self.assertEqual(report["units"]["s3"]["literal_state_keys"], [])

    def test_input_named_key_outside_state_config_is_not_a_state_key(self):
        for tenant in ("acme", "globex"):
            self.write_unit(tenant + "/prod/kms",
                            'dependency "backend" {\n  config_path = "../api"\n}\n'
                            'inputs = {\n  key = "alias/app"\n}\n')
        code, report = self.run_cli()
        self.assertEqual(code, 0)
        self.assertEqual(report["shared_state_keys"], [])
        self.assertEqual(report["units"]["kms"]["literal_state_keys"], [])

    def test_literal_key_in_generated_backend_block_is_found(self):
        generated = ('generate "backend" {\n  path = "backend.tf"\n  contents = <<EOF\n'
                     'terraform {\n  backend "s3" {\n    key = "shared/terraform.tfstate"\n  }\n}\nEOF\n}\n'
                     'inputs = {\n  key = "alias/app"\n}\n')
        for tenant in ("acme", "globex"):
            self.write_unit(tenant + "/dev/s3", generated)
        code, report = self.run_cli()
        self.assertEqual(code, 1)
        self.assertEqual([item["key"] for item in report["shared_state_keys"]],
                         ["shared/terraform.tfstate"])

    def test_environment_named_refs_remain_visible_in_diff(self):
        for layout in ('terraform {{\n source = "{source}"\n}}\n',
                       'terraform {{ source = "{source}" }}\n',
                       'terraform {{\n source = /* module */ "{source}"\n}}\n',
                       'terraform {{\n source = <<-SRC\n{source}\nSRC\n}}\n'):
            with self.subTest(layout=layout):
                for env in ("dev", "prod"):
                    self.write_unit("acme/" + env + "/s3", layout.format(
                        source="git::https://example.com/modules.git//s3?ref=" + env))
                code, report = self.run_cli()
                self.assertEqual(code, 1)
                variants = report["units"]["s3"]["variants"]
                self.assertEqual(len(variants), 1)
                diff = "\n".join(variants[0]["diff"])
                self.assertIn("ref=dev", diff)
                self.assertIn("ref=prod", diff)
                self.assertNotIn("ref={env}", diff)

    def write_queue_batch(self):
        """Dev keeps 1 day, prod 7; globex dev wrongly carries the prod value."""
        for tenant in ("acme", "globex", "initech"):
            for env, days in (("dev", 1), ("prod", 7)):
                if (tenant, env) == ("globex", "dev"):
                    days = 7
                self.write_unit(f"{tenant}/{env}/queue", f'inputs = {{ retention_days = {days} }}\n')

    def test_mixed_environments_hide_drift_that_within_reports(self):
        self.write_queue_batch()
        code, report = self.run_cli()
        self.assertEqual(code, 1)
        hidden = report["units"]["queue"]["variants"]
        self.assertNotIn(str(self.root / "globex/dev/queue/terragrunt.hcl"),
                         [path for v in hidden for path in v["files"]])

        code, report = self.run_cli("--within", "env")
        self.assertEqual(code, 1)
        self.assertEqual(sorted(report["units"]), ["queue [env=dev]", "queue [env=prod]"])
        dev = report["units"]["queue [env=dev]"]
        self.assertEqual(dev["within"], {"env": "dev"})
        self.assertEqual(dev["baseline"]["count"], 2)
        self.assertEqual(dev["variants"][0]["files"], [str(self.root / "globex/dev/queue/terragrunt.hcl")])
        self.assertEqual(report["units"]["queue [env=prod]"]["variants"], [])

    def test_within_reports_missing_units_in_their_own_slice(self):
        self.write_queue_batch()
        (self.root / "initech/prod/queue/terragrunt.hcl").unlink()
        self.write_unit("acme/stage/bucket")
        code, report = self.run_cli("--within", "env", "--expect", "tenant=acme,globex,initech",
                                    "--expect", "env=dev,prod,stage")
        self.assertEqual(code, 1)
        self.assertEqual(report["units"]["queue [env=prod]"]["missing"],
                         [{"tenant": "initech", "env": "prod"}])
        self.assertEqual(report["units"]["queue [env=dev]"]["missing"], [])
        absent = report["units"]["queue [env=stage]"]
        self.assertIsNone(absent["baseline"])
        self.assertEqual(len(absent["missing"]), 3)

    def test_tied_baseline_is_reported_as_tied(self):
        for tenant, days in (("acme", 1), ("globex", 2)):
            self.write_unit(tenant + "/dev/queue", f'inputs = {{ retention_days = {days} }}\n')
        code, report = self.run_cli()
        self.assertEqual(code, 1)
        self.assertTrue(report["units"]["queue"]["baseline"]["tied"])
        code, text = self.run_cli(json_output=False)
        self.assertIn("no most common variant", text)

    def test_within_rejects_dimensions_the_layout_does_not_capture(self):
        self.write_unit("acme/dev/queue")
        for name in ("unit", "region"):
            with self.subTest(name=name):
                command = [sys.executable, "-B", str(SCRIPT), "--root", str(self.root),
                           "--layout", "{tenant}/{env}/{unit}", "--within", name]
                result = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn("--within", result.stderr)

    def test_chosen_baseline_still_overrides_majority(self):
        chosen = self.write_unit("acme/dev/s3", 'inputs = { size = 1 }\n')
        for tenant in ("globex", "initech"):
            self.write_unit(tenant + "/dev/s3", 'inputs = { size = 2 }\n')
        code, report = self.run_cli("--baseline", chosen)
        self.assertEqual(code, 1)
        entry = report["units"]["s3"]
        self.assertTrue(entry["baseline"]["chosen"])
        self.assertEqual(entry["baseline"]["example"], chosen)
        self.assertEqual(entry["variants"][0]["count"], 2)


if __name__ == "__main__":
    unittest.main()
