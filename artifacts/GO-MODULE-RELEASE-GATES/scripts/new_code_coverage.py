#!/usr/bin/env python3
"""Coverage of the statements a change added or modified in one Go module.

Overall coverage says how well the whole module is tested. It can stay above a
threshold while every new line is untested, because old, well-tested code holds the
average up. This script answers the narrower question: of the statements this change
touched, how many did the tests execute?

Inputs:
  --profile     a Go cover profile (go test -coverprofile=coverage.out ./...)
  --module-dir  the directory holding the module's go.mod, relative to the current
                directory or absolute (default: the current directory)
  --repo-root   the repository root the diff's paths are relative to
                (default: git rev-parse --show-toplevel, else the current directory)
  --diff        a unified diff with zero context, or '-' for stdin:
                git diff --unified=0 --src-prefix=a/ --dst-prefix=b/ <base>...HEAD \
                  -- '*.go' ':!*_test.go'
  --threshold   percentage required (default 80)

The unit is the statement, as in `go tool cover`. Every profile block that contains
at least one changed line contributes its statements; the block is covered when any
test ran it (a profile can list a block more than once, for example with -coverpkg).
Blank lines, comments and declarations sit in no block and drop out of the ratio.

A changed file whose package does not appear in the profile at all was not measured,
which is different from "nothing to measure". It is reported as unmeasured. When
nothing else was measured either, the result is UNMEASURED, not a pass: usually the
paths do not line up (wrong --repo-root or --module-dir), or the package has no test
files and the Go version predates 1.22, which leaves such packages out of profiles.

Exit status: 0 when coverage meets the threshold or the change touched no
statements; 1 when it is below; 2 on bad input or when nothing could be measured.
Standard library only; Python 3.9+.
"""

import argparse
import json
import os
import posixpath
import re
import subprocess
import sys
from collections import defaultdict

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
BLOCK = re.compile(r"^(.+):(\d+)\.(\d+),(\d+)\.(\d+) (\d+) (\d+)$")


def module_path(go_mod_text):
    for line in go_mod_text.splitlines():
        line = line.strip()
        if line.startswith("module "):
            return line.split(None, 1)[1].strip().strip('"')
    raise ValueError("go.mod has no module directive")


def changed_lines(diff_text):
    """Map repo-relative file path -> set of added or modified line numbers.

    A '+++ ' line is a file header only directly after a '--- ' line; inside a
    hunk the same text is an added line that happens to start with '++ '.
    """
    result = defaultdict(set)
    current = None
    previous = ""
    for line in diff_text.splitlines():
        if line.startswith("+++ ") and previous.startswith("--- "):
            target = line[4:].strip()
            if target == "/dev/null":
                current = None
            else:
                current = target[2:] if target.startswith("b/") else target
                result[current]  # a file with only deletions is still a changed file
        elif current is not None:
            match = HUNK.match(line)
            if match:
                start = int(match.group(1))
                count = 1 if match.group(2) is None else int(match.group(2))
                result[current].update(range(start, start + count))
        previous = line
    return dict(result)


def profile_blocks(profile_text, mod_path, module_rel_dir):
    """Map repo-relative file path -> {position: (statements, max count)}.

    The profile names files by import path. Strip the module path and prefix the
    module's directory to get the path the diff uses. Files from other modules
    (a -coverpkg pattern can pull them in) are skipped. A block is keyed by its
    full start and end position, columns included: several blocks can share one
    line, as in `if err != nil { return err }`.
    """
    blocks = defaultdict(dict)
    prefix = mod_path + "/"
    for line in profile_text.splitlines():
        if not line.strip() or line.startswith("mode:"):
            continue
        match = BLOCK.match(line.strip())
        if not match:
            raise ValueError("unrecognised profile line: " + line)
        name, sline, scol, eline, ecol, stmts, count = match.groups()
        if not name.startswith(prefix):
            continue
        rel = name[len(prefix):]
        if module_rel_dir not in ("", "."):
            rel = module_rel_dir.rstrip("/") + "/" + rel
        key = (int(sline), int(scol), int(eline), int(ecol))
        old_stmts, old_count = blocks[rel].get(key, (int(stmts), 0))
        blocks[rel][key] = (max(old_stmts, int(stmts)), max(old_count, int(count)))
    return blocks


def measure(changed, blocks):
    covered, total = 0, 0
    uncovered = defaultdict(set)
    measured_dirs = {posixpath.dirname(p) for p in blocks}
    unmeasured = []
    for path in sorted(changed):
        file_blocks = blocks.get(path)
        if not file_blocks:
            # No blocks for the file. If its package is in the profile, the file
            # holds only declarations; if not, the package was never measured.
            if posixpath.dirname(path) not in measured_dirs:
                unmeasured.append(path)
            continue
        lines = changed[path]
        for (sline, _scol, eline, _ecol), (stmts, count) in sorted(file_blocks.items()):
            touched = [n for n in range(sline, eline + 1) if n in lines]
            if not touched:
                continue
            total += stmts
            if count > 0:
                covered += stmts
            else:
                uncovered[path].update(touched)
    return covered, total, {p: sorted(l) for p, l in uncovered.items()}, unmeasured


def collapse(lines):
    """[3, 4, 5, 9] -> '3-5, 9'"""
    ranges, start, prev = [], None, None
    for n in lines:
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            ranges.append((start, prev))
            start = prev = n
    if start is not None:
        ranges.append((start, prev))
    return ", ".join(str(a) if a == b else "%d-%d" % (a, b) for a, b in ranges)


def default_repo_root():
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, check=True)
        return out.stdout.strip() or "."
    except (OSError, subprocess.CalledProcessError):
        return "."


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--profile", required=True)
    parser.add_argument("--module-dir", default=".")
    parser.add_argument("--diff", required=True, help="diff file, or - for stdin")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--threshold", type=float, default=80.0)
    parser.add_argument("--json", action="store_true", help="print a JSON result")
    args = parser.parse_args(argv)

    try:
        repo_root = os.path.realpath(args.repo_root or default_repo_root())
        module_dir = os.path.realpath(args.module_dir)
        module_rel = os.path.relpath(module_dir, repo_root).replace(os.sep, "/")
        if module_rel == ".." or module_rel.startswith("../"):
            raise ValueError("module directory %s is outside the repository root %s"
                             % (module_dir, repo_root))
        with open(os.path.join(module_dir, "go.mod"), encoding="utf-8") as f:
            mod_path = module_path(f.read())
        with open(args.profile, encoding="utf-8") as f:
            blocks = profile_blocks(f.read(), mod_path, module_rel)
        if args.diff == "-":
            diff_text = sys.stdin.read()
        else:
            with open(args.diff, encoding="utf-8") as f:
                diff_text = f.read()
    except (OSError, ValueError) as err:
        print("error: %s" % err, file=sys.stderr)
        return 2

    in_module = module_rel + "/" if module_rel != "." else ""
    changed = {p: l for p, l in changed_lines(diff_text).items()
               if p.startswith(in_module) and p.endswith(".go") and not p.endswith("_test.go")}
    covered, total, uncovered, unmeasured = measure(changed, blocks)

    if total > 0:
        percent = 100.0 * covered / total
        verdict = "PASS" if percent >= args.threshold else "FAIL"
    elif unmeasured:
        percent, verdict = None, "UNMEASURED"
    else:
        percent, verdict = None, "N/A"

    if args.json:
        print(json.dumps({"module": mod_path, "covered": covered, "total": total,
                          "percent": percent, "threshold": args.threshold,
                          "verdict": verdict, "uncovered": uncovered,
                          "unmeasured": unmeasured}, indent=2))
    else:
        if verdict == "UNMEASURED":
            print("new-code coverage: UNMEASURED - the changed files' packages are not in the profile")
        elif percent is None:
            print("new-code coverage: N/A (no statements changed) - PASS")
        else:
            print("new-code coverage: %.1f%% (%d of %d statements in changed code) - %s (threshold %.0f%%)"
                  % (percent, covered, total, verdict, args.threshold))
        for path, lines in sorted(uncovered.items()):
            print("  not covered: %s: %s" % (path, collapse(lines)))
        for path in unmeasured:
            print("  unmeasured:  %s (package not in the profile)" % path)
    if verdict == "UNMEASURED":
        return 2
    return 1 if verdict == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
