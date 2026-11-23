"""CLI regression tests for new_code_coverage.py; fixtures need no Go toolchain."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPT = (Path(__file__).resolve().parents[1] / "artifacts" /
          "GO-MODULE-RELEASE-GATES" / "scripts" / "new_code_coverage.py")

GO_MOD = "module example.com/repo/connectors/reader\n\ngo 1.22\n"
READ_GO = "connectors/reader/plugin/read.go"

# Block 10-12 (3 statements) ran, 14-15 (2) did not, 20-22 (2) ran in one test
# and not in another (the same block listed twice, as -coverpkg produces).
# Line 30 holds two blocks, as `if err != nil { return err }` does: the condition
# ran, the return did not.
PROFILE = """mode: atomic
example.com/repo/connectors/reader/plugin/read.go:10.2,12.10 3 4
example.com/repo/connectors/reader/plugin/read.go:14.2,15.20 2 0
example.com/repo/connectors/reader/plugin/read.go:20.2,22.3 2 0
example.com/repo/connectors/reader/plugin/read.go:20.2,22.3 2 1
example.com/repo/connectors/reader/plugin/read.go:30.2,30.16 1 5
example.com/repo/connectors/reader/plugin/read.go:30.16,30.28 1 0
example.com/repo/shared/util.go:1.1,3.2 1 0
"""


def diff(path, *hunks):
    lines = ["diff --git a/%s b/%s" % (path, path),
             "--- a/%s" % path, "+++ b/%s" % path]
    for start, count in hunks:
        header = "@@ -1,0 +%d @@" % start if count is None else "@@ -1,0 +%d,%d @@" % (start, count)
        lines.append(header)
        lines.extend("+x" for _ in range(1 if count is None else count))
    return "\n".join(lines) + "\n"


class NewCodeCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="new-code-coverage-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.module = self.root / "connectors" / "reader"
        self.module.mkdir(parents=True)
        (self.module / "go.mod").write_text(GO_MOD, encoding="utf-8")
        self.profile = self.root / "coverage.out"
        self.profile.write_text(PROFILE, encoding="utf-8")

    def run_cli(self, diff_text, *extra, cwd=None, repo_root=True):
        diff_file = self.root / "change.diff"
        diff_file.write_text(diff_text, encoding="utf-8")
        command = [sys.executable, "-B", str(SCRIPT), "--profile", str(self.profile),
                   "--diff", str(diff_file), "--json"]
        if cwd is None:
            command += ["--module-dir", str(self.module)]
        if repo_root:
            command += ["--repo-root", str(self.root)]
        completed = subprocess.run(command + list(extra), capture_output=True,
                                   text=True, cwd=cwd)
        payload = json.loads(completed.stdout) if completed.stdout.strip() else None
        return completed.returncode, payload, completed.stderr

    def test_counts_statements_of_blocks_on_changed_lines(self):
        # Blocks 10-12 (3 statements, ran) and 14-15 (2, did not); 13 and 16-17 are in no block.
        code, result, _ = self.run_cli(diff(READ_GO, (10, 8)))
        self.assertEqual((result["covered"], result["total"]), (3, 5))
        self.assertEqual(result["uncovered"], {READ_GO: [14, 15]})
        self.assertEqual(result["verdict"], "FAIL")
        self.assertEqual(code, 1)

    def test_a_block_covered_by_any_test_counts_as_covered(self):
        code, result, _ = self.run_cli(diff(READ_GO, (20, 3)))
        self.assertEqual((result["covered"], result["total"]), (2, 2))
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(code, 0)

    def test_blocks_sharing_one_line_are_counted_separately(self):
        code, result, _ = self.run_cli(diff(READ_GO, (30, 1)))
        self.assertEqual((result["covered"], result["total"]), (1, 2))
        self.assertEqual(result["uncovered"], {READ_GO: [30]})
        self.assertEqual(code, 1)

    def test_one_changed_line_counts_its_whole_block(self):
        # A hunk header without a count is one line; it sits in a two-statement block.
        code, result, _ = self.run_cli(diff(READ_GO, (14, None)))
        self.assertEqual((result["covered"], result["total"]), (0, 2))
        self.assertEqual(result["uncovered"], {READ_GO: [14]})
        self.assertEqual(code, 1)

    def test_nothing_instrumented_is_not_a_failure(self):
        # Line 5 is outside every block: a comment or an import, say.
        code, result, _ = self.run_cli(diff(READ_GO, (5, 1)))
        self.assertIsNone(result["percent"])
        self.assertEqual(result["verdict"], "N/A")
        self.assertEqual(code, 0)

    def test_declarations_only_file_in_a_measured_package_is_not_unmeasured(self):
        code, result, _ = self.run_cli(diff("connectors/reader/plugin/types.go", (1, 5)))
        self.assertEqual(result["unmeasured"], [])
        self.assertEqual(result["verdict"], "N/A")
        self.assertEqual(code, 0)

    def test_package_missing_from_the_profile_is_unmeasured_not_passed(self):
        code, result, _ = self.run_cli(diff("connectors/reader/client/dial.go", (1, 5)))
        self.assertEqual(result["unmeasured"], ["connectors/reader/client/dial.go"])
        self.assertEqual(result["verdict"], "UNMEASURED")
        self.assertEqual(code, 2)

    def test_unmeasured_package_is_listed_beside_a_measured_result(self):
        text = diff(READ_GO, (20, 3)) + diff("connectors/reader/client/dial.go", (1, 5))
        code, result, _ = self.run_cli(text)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["unmeasured"], ["connectors/reader/client/dial.go"])
        self.assertEqual(code, 0)

    def test_pure_deletion_changes_nothing(self):
        code, result, _ = self.run_cli(diff(READ_GO, (14, 0)))
        self.assertEqual(result["total"], 0)
        self.assertEqual(code, 0)

    def test_files_outside_the_module_and_tests_are_ignored(self):
        text = (diff("shared/util.go", (1, 3)) +
                diff("connectors/reader/plugin/read_test.go", (10, 3)))
        code, result, _ = self.run_cli(text)
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["unmeasured"], [])
        self.assertEqual(code, 0)

    def test_threshold_is_configurable(self):
        code, result, _ = self.run_cli(diff(READ_GO, (10, 6)), "--threshold", "60")
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(code, 0)

    def test_deleted_file_is_ignored(self):
        text = ("diff --git a/connectors/reader/plugin/old.go b/connectors/reader/plugin/old.go\n"
                "--- a/connectors/reader/plugin/old.go\n+++ /dev/null\n@@ -1,3 +0,0 @@\n-x\n-x\n-x\n")
        code, result, _ = self.run_cli(text)
        self.assertEqual(result["total"], 0)
        self.assertEqual(code, 0)

    def test_added_line_that_looks_like_a_file_header_is_content(self):
        text = ("--- a/%s\n+++ b/%s\n@@ -1,0 +14,2 @@\n+++ x\n+y\n" % (READ_GO, READ_GO))
        code, result, _ = self.run_cli(text)
        self.assertEqual((result["covered"], result["total"]), (0, 2))
        self.assertEqual(code, 1)

    @unittest.skipIf(shutil.which("git") is None, "git not installed")
    def test_defaults_work_from_inside_the_module_of_a_git_repository(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        code, result, _ = self.run_cli(diff(READ_GO, (10, 8)), cwd=str(self.module),
                                       repo_root=False)
        self.assertEqual((result["covered"], result["total"]), (3, 5))
        self.assertEqual(code, 1)

    def test_missing_go_mod_is_an_input_error(self):
        (self.module / "go.mod").unlink()
        code, result, stderr = self.run_cli(diff(READ_GO, (10, 1)))
        self.assertEqual(code, 2)
        self.assertIsNone(result)
        self.assertIn("error:", stderr)


if __name__ == "__main__":
    unittest.main()
