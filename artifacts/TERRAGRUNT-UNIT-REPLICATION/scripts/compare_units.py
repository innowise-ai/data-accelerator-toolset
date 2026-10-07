#!/usr/bin/env python3
"""Compare Terragrunt unit files that should differ only by tenant, environment
or other path dimension.

Reads only. Prints a report and exits 1 when anything needs review, 0 when the
batch is clean, 2 on a usage error. Python 3.9+, standard library only.

Example, for units laid out as live/<tenant>/<env>/<unit>/terragrunt.hcl:

    python compare_units.py --root live --layout "{tenant}/{env}/{unit}" \
        --expect tenant=acme,globex,initech --expect env=dev,prod
"""

import argparse
import difflib
import itertools
import json
import os
import re
import sys
from collections import defaultdict

SKIP_DIRS = {".terragrunt-cache", ".terragrunt-stack", ".git", ".terraform"}
WORD = r"A-Za-z0-9"
# Keep quoted strings and heredocs opaque when recognizing comments or sources.
HCL_STRING = r'"(?:\\.|[^"\\])*"'
HCL_HEREDOC = r'<<-?([A-Za-z_][A-Za-z0-9_]*)[^\n]*\n.*?^[ \t]*\1[ \t]*(?=\r?$)'
HCL_COMMENT = r'\#[^\n]*|//[^\n]*|/\*.*?\*/'
HCL_TEXT = re.compile(
    HCL_HEREDOC + r'|' + HCL_STRING + r'|(?P<comment>' + HCL_COMMENT + r')',
    re.MULTILINE | re.DOTALL,
)
SOURCE_VALUE = re.compile(r'\bsource\s*=\s*\Z')


def parse_layout(layout):
    """Return one matcher per path segment: ("lit", text), ("any", None) or ("cap", name)."""
    parts = [p for p in layout.strip("/").split("/") if p]
    matchers = []
    for part in parts:
        capture = re.fullmatch(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", part)
        if capture:
            matchers.append(("cap", capture.group(1)))
        elif part == "*":
            matchers.append(("any", None))
        elif "{" in part or "}" in part or "*" in part:
            raise ValueError(f"layout segment '{part}' must be a literal, '*' or a single '{{name}}'")
        else:
            matchers.append(("lit", part))
    names = [m[1] for m in matchers if m[0] == "cap"]
    if "unit" not in names:
        raise ValueError("layout must capture {unit}, the name units are grouped by")
    if len(names) != len(set(names)):
        raise ValueError("layout captures the same name twice")
    return matchers


def match_layout(matchers, segments):
    if len(segments) != len(matchers):
        return None
    captured = {}
    for (kind, value), segment in zip(matchers, segments):
        if kind == "lit" and segment != value:
            return None
        if kind == "cap":
            captured[value] = segment
    return captured


def discover(root, file_name, matchers):
    units, unmatched = [], []
    for directory, subdirs, files in os.walk(root):
        subdirs[:] = sorted(d for d in subdirs if d not in SKIP_DIRS)
        if file_name not in files:
            continue
        relative = os.path.relpath(directory, root).replace(os.sep, "/")
        segments = [] if relative == "." else relative.split("/")
        captured = match_layout(matchers, segments)
        path = os.path.join(directory, file_name)
        if captured is None:
            unmatched.append(path)
            continue
        with open(path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
        units.append({"path": path, "dims": captured, "text": text})
    return units, unmatched


def boundary_pattern(value):
    return re.compile(rf"(?<![{WORD}]){re.escape(value)}(?![{WORD}])")


def normalize(text, dims):
    """Normalize dimension values, preserving literal module sources and their refs."""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    out = "\n".join(lines).strip("\n")
    replacements = [(boundary_pattern(value), "{" + name + "}")
                    for name, value in sorted(dims.items(), key=lambda item: -len(item[1]))
                    if name != "unit"]

    def replace(part):
        for pattern, token in replacements:
            part = pattern.sub(token, part)
        return part

    # Use spans, not sentinel strings that might themselves match a dimension.
    parts, start, previous_end = [], 0, 0
    for match in HCL_TEXT.finditer(out):
        if match.lastgroup == "comment":
            continue
        if SOURCE_VALUE.search(strip_comments(out[previous_end:match.start()])):
            parts.extend((replace(out[start:match.start()]), match.group()))
            start = match.end()
        previous_end = match.end()
    parts.append(replace(out[start:]))
    return "".join(parts)


def strip_comments(text):
    """Remove HCL comments without interpreting comment markers inside strings."""
    return HCL_TEXT.sub(
        lambda match: re.sub(r'[^\r\n]', ' ', match.group())
        if match.lastgroup == "comment" else match.group(), text)


def label(dims):
    return " ".join(f"{k}={v}" for k, v in sorted(dims.items()) if k != "unit")


def foreign_values(normalized, dims, observed):
    """Values of another tenant/env/... that appear in this unit after its own were replaced."""
    hits = []
    lines = normalized.split("\n")
    for name, values in observed.items():
        for value in sorted(values):
            if value == dims.get(name):
                continue
            pattern = boundary_pattern(value)
            for number, line in enumerate(lines, 1):
                if pattern.search(line):
                    hits.append({"dimension": name, "value": value, "line": number, "text": line.strip()})
    return hits


LITERAL_KEY = re.compile(r'^\s*key\s*=\s*"([^"$]*)"\s*$', re.MULTILINE)
# A Terragrunt remote_state block, or a Terraform backend block (also inside generated contents).
STATE_BLOCK = re.compile(r'\b(?:remote_state|backend\s+"[^"\n]*")\s*\{')


def block_body(text, open_brace):
    """Text between the brace at open_brace and its match; quoted strings are skipped."""
    depth, index = 0, open_brace
    while index < len(text):
        char = text[index]
        if char == '"':
            index += 1
            while index < len(text) and text[index] not in '"\n':
                index += 2 if text[index] == "\\" else 1
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[open_brace + 1:index]
        index += 1
    return text[open_brace + 1:]


def literal_state_keys(text):
    """Literal `key` values inside state configuration only, so a module input named
    `key` (a KMS alias, an object key) is not mistaken for a state key."""
    text = strip_comments(text)
    keys = []
    for match in STATE_BLOCK.finditer(text):
        keys.extend(LITERAL_KEY.findall(block_body(text, match.end() - 1)))
    return keys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=".", help="directory the layout is relative to (default: .)")
    parser.add_argument("--layout", required=True,
                        help="unit directory relative to --root, e.g. '{tenant}/*/{env}/{unit}'; '*' ignores a segment")
    parser.add_argument("--file", default="terragrunt.hcl", help="unit file name (default: terragrunt.hcl)")
    parser.add_argument("--expect", action="append", default=[], metavar="DIM=V1,V2",
                        help="expected values for a dimension; repeat per dimension")
    parser.add_argument("--unit", action="append", default=[], help="only check this unit name; repeatable")
    parser.add_argument("--baseline", action="append", default=[], metavar="PATH",
                        help="unit file to diff the others of its unit name against; repeatable, one per "
                             "unit name (default: the most common variant, which is not proof of correctness)")
    parser.add_argument("--max-diff-lines", type=int, default=40)
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)

    try:
        matchers = parse_layout(args.layout)
        expected = {}
        for item in args.expect:
            name, _, values = item.partition("=")
            if not values:
                raise ValueError(f"--expect '{item}' must look like DIM=V1,V2")
            expected[name] = [v for v in values.split(",") if v]
        dim_names = [m[1] for m in matchers if m[0] == "cap" and m[1] != "unit"]
        unknown = set(expected) - set(dim_names)
        if unknown:
            raise ValueError(f"--expect names {sorted(unknown)} that the layout does not capture")
    except ValueError as error:
        parser.error(str(error))

    if not os.path.isdir(args.root):
        parser.error(f"--root '{args.root}' is not a directory")

    units, unmatched = discover(args.root, args.file, matchers)
    baselines = {os.path.normcase(os.path.abspath(p)) for p in args.baseline}
    missing_baselines = sorted(p for p in args.baseline
                               if os.path.normcase(os.path.abspath(p)) not in
                               {os.path.normcase(os.path.abspath(u["path"])) for u in units})
    if missing_baselines:
        parser.error(f"--baseline {missing_baselines} is not one of the unit files found under --root")

    observed = defaultdict(set)
    for unit in units:
        for name in dim_names:
            observed[name].add(unit["dims"][name])
    for name, values in expected.items():
        observed[name].update(values)

    # Coverage: the combinations every unit name should exist for.
    if dim_names and all(name in expected for name in dim_names):
        combos = set(itertools.product(*(expected[n] for n in dim_names)))
        coverage_source = "expected"
    else:
        combos = {tuple(u["dims"][n] for n in dim_names) for u in units}
        combos = {c for c in combos if all(n not in expected or c[i] in expected[n] for i, n in enumerate(dim_names))}
        coverage_source = "observed"

    # State keys are compared across every unit found: a new copy can collide with any of them.
    keys = defaultdict(list)
    for unit in units:
        for key in literal_state_keys(unit["text"]):
            keys[key].append(unit["path"])

    if args.unit:
        units = [u for u in units if u["dims"]["unit"] in set(args.unit)]

    groups = defaultdict(list)
    for unit in units:
        groups[unit["dims"]["unit"]].append(unit)
    for name in args.unit:
        groups.setdefault(name, [])

    report = {"root": args.root, "layout": args.layout, "unit_count": len(units),
              "coverage_from": coverage_source, "unmatched_files": unmatched, "units": {}, "shared_state_keys": []}
    needs_review = bool(unmatched) or not units

    for key, paths in sorted(keys.items()):
        if len(paths) > 1:
            report["shared_state_keys"].append({"key": key, "files": paths})
            needs_review = True

    for name in sorted(groups):
        members = groups[name]
        present = {tuple(u["dims"][n] for n in dim_names) for u in members}
        missing = sorted(combos - present)
        unexpected = sorted(u["path"] for u in members
                            if any(n in expected and u["dims"][n] not in expected[n] for n in dim_names))

        for unit in members:
            unit["normalized"] = normalize(unit["text"], unit["dims"])
        variants = defaultdict(list)
        for unit in members:
            variants[unit["normalized"]].append(unit)
        chosen = [u for u in members if os.path.normcase(os.path.abspath(u["path"])) in baselines]
        ordered = sorted(variants.items(), key=lambda item: (
            not any(u in chosen for u in item[1]), -len(item[1]), item[1][0]["path"]))
        baseline_text, baseline_units = ordered[0] if ordered else ("", [])
        if chosen:
            baseline_units = sorted(baseline_units, key=lambda u: u not in chosen)

        entry = {
            "instances": len(members),
            "missing": [dict(zip(dim_names, c)) for c in missing],
            "unexpected": unexpected,
            "baseline": {"count": len(baseline_units), "example": baseline_units[0]["path"],
                         "chosen": bool(chosen)} if baseline_units else None,
            "variants": [],
            "foreign_values": [],
            "literal_state_keys": sorted(u["path"] for u in members if literal_state_keys(u["text"])),
        }
        for text, same in ordered[1:]:
            diff = list(difflib.unified_diff(baseline_text.split("\n"), text.split("\n"),
                                             "baseline", "variant", n=1, lineterm=""))
            entry["variants"].append({
                "count": len(same),
                "files": sorted(u["path"] for u in same),
                "diff": diff[:args.max_diff_lines],
                "diff_truncated": len(diff) > args.max_diff_lines,
            })
        for unit in members:
            for hit in foreign_values(unit["normalized"], unit["dims"], observed):
                entry["foreign_values"].append(dict(hit, file=unit["path"], unit=label(unit["dims"])))

        if (not members or missing or unexpected or entry["variants"]
                or entry["foreign_values"] or entry["literal_state_keys"]):
            needs_review = True
        report["units"][name] = entry

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_text(report, dim_names)
    return 1 if needs_review else 0


def print_text(report, dim_names):
    print(f"{report['unit_count']} unit files under {report['root']} matched {report['layout']}")
    print(f"coverage compared against {report['coverage_from']} combinations of: {', '.join(dim_names) or '(none)'}")
    if not report["unit_count"]:
        print("NO UNITS: no selected unit files were found; the batch cannot be verified")
    if report["unmatched_files"]:
        print(f"\nfiles that do not fit the layout ({len(report['unmatched_files'])}):")
        for path in report["unmatched_files"]:
            print(f"  {path}")
    for item in report["shared_state_keys"]:
        print(f"\nSHARED STATE KEY '{item['key']}' is a literal in {len(item['files'])} units:")
        for path in item["files"]:
            print(f"  {path}")
    for name, entry in report["units"].items():
        if entry["baseline"] is None:
            print(f"\n== {name}: 0 instances; no baseline available")
            print(f"  MISSING   unit={name} (absent everywhere)")
        else:
            source = "chosen" if entry["baseline"]["chosen"] else "most common"
            print(f"\n== {name}: {entry['instances']} instances, {entry['baseline']['count']} identical to "
                  f"baseline ({source}: {entry['baseline']['example']})")
        for combo in entry["missing"]:
            print(f"  MISSING   {' '.join(f'{k}={v}' for k, v in combo.items())}")
        for path in entry["unexpected"]:
            print(f"  UNEXPECTED {path}")
        for hit in entry["foreign_values"]:
            print(f"  FOREIGN   {hit['file']}:{hit['line']} ({hit['unit']}) mentions "
                  f"{hit['dimension']} '{hit['value']}': {hit['text']}")
        for path in entry["literal_state_keys"]:
            print(f"  LITERAL STATE KEY {path}")
        for variant in entry["variants"]:
            print(f"  VARIANT in {variant['count']} file(s): {', '.join(variant['files'][:5])}"
                  + (" ..." if len(variant["files"]) > 5 else ""))
            for line in variant["diff"]:
                print(f"    {line}")
            if variant["diff_truncated"]:
                print("    ... diff truncated, rerun with --max-diff-lines")


if __name__ == "__main__":
    sys.exit(main())
