---
name: go-module-release-gates
description: Runs the release gates for one Go module in a repository that holds several - race-enabled tests, overall and new-code coverage, lint and formatting scoped to the change, and a version bump that matches its changelog entry. Use when preparing a pull request or a release for a Go module that versions and ships on its own.
---

# Release gates for one Go module

Some repositories hold many Go modules that each version and ship on their own: a
repository of connectors or plugins, a set of services, a library collection. Each
module has its own `go.mod`, its own version and its own release. In that layout
**the module is the unit of work, not the repository**, and almost every repo-level
signal answers the wrong question.

This artifact is the gate set for one module, and the reasons each gate exists. The
commands assume the Go toolchain and golangci-lint; the new-code coverage step uses
the bundled script, which needs only Python.

## Why the repository root is the wrong place to look

- **`go test ./...` at the root does not test nested modules.** The `./...` pattern
  stops at any directory with its own `go.mod`. A root run can pass while every
  module is broken. The same holds for `go vet ./...` and `go build ./...`.
- **The root `go.mod` describes only what lives directly under it.** If the root is a
  module at all, its dependency pins say nothing about what the shipped modules use.
  Reading it to learn the repository's dependencies gives a confident, wrong answer.
- **CI may build only what changed.** Pipelines that generate jobs from the diff never
  build untouched modules. A green build on a change that touched no module may have
  run almost nothing. Ask what CI ran before taking it as evidence.

So find the module first, then run everything from inside it.

## 1. Find the module

Map each changed file to the nearest `go.mod` above it:

```bash
git diff --name-only <base>...HEAD
find . -name go.mod -not -path '*/vendor/*'
```

If the change spans several modules, gate each one separately. Each has its own
version, its own changelog and its own verdict. A shared-library change that
several modules depend on through a pinned version does not reach them until each is
bumped; do not report them as fixed.

## 2. Tests, with the race detector

From the module directory:

```bash
go test -race -trimpath -coverprofile=coverage.out ./...
```

`-race` is the gate that pays for itself in long-running code. Connectors and
services hold state across goroutines (a client shared by workers, a cache, a
reconnect path) and a data race there corrupts data intermittently, under load,
long after review. The detector needs cgo (`CGO_ENABLED=1`) and a C toolchain;
if it cannot run, say so rather than dropping the flag silently.

If tests fail, report the failures and still run the remaining gates. A reviewer
needs the whole picture, not the first red light. That is also why the command
leaves out `-failfast`: stopping at the first failure leaves a partial coverage
profile, and the coverage gates below would then measure the wrong thing.

## 3. Coverage: overall and new code

Overall coverage comes from the profile:

```bash
go tool cover -func=coverage.out | tail -1   # total: (statements) NN.N%
```

**Overall coverage is not enough on its own.** A module at 85% can absorb a change
whose new code has no tests at all, because the old, tested code holds the average
up. The gate that catches that is coverage of the lines this change added or
modified:

```bash
git diff --unified=0 --src-prefix=a/ --dst-prefix=b/ <base>...HEAD -- '*.go' ':!*_test.go' \
  | python3 <artifact dir>/scripts/new_code_coverage.py --profile coverage.out --diff - --threshold 80
```

Run it from the module directory: the module defaults to the current directory and
the repository root to `git rev-parse --show-toplevel`. The explicit prefixes keep
the diff readable whatever the local `diff.noprefix` or `diff.mnemonicPrefix`
settings are.

The script reads the diff's hunk headers for the changed lines and maps the
profile's import paths back to repository paths through the module path in `go.mod`.
It counts statements, as `go tool cover` does: every profile block that contains a
changed line contributes its statements, covered if any test ran the block. Comments,
blank lines and declarations sit in no block and fall out of the ratio. When a change
touches no statement (comments, imports, tests only), the result is N/A and passes.
It lists the changed lines that sit in blocks no test ran.

A changed file whose package is not in the profile at all is reported as
**unmeasured**, and when nothing else was measured the result is UNMEASURED with exit
status 2, never a pass. Two causes are common: the paths do not line up (the script
was pointed at the wrong module or root), or the package has no test files and Go is
older than 1.22, which leaves such packages out of the profile. Either way, a pass
would be a claim about code nobody measured.

A per-package profile only credits tests in the same package. If a module tests a
package through another one, add `-coverpkg=./...` to the test run, or that
package's coverage reads lower than it is.

The threshold is the project's decision. 80% for both is a common bar; what matters
is that it is written down and the same for every module.

## 4. Lint and formatting, scoped to the change

```bash
golangci-lint run --new-from-rev=<base> ./...
git diff --name-only --relative --diff-filter=d <base>...HEAD -- '*.go' | xargs -r gofmt -l
go vet ./...
```

`--new-from-rev` reports only issues in lines the change touched (golangci-lint v2
also offers `--new-from-merge-base`). `--relative` keeps the list to files under the current module and makes the paths
relative to it. `xargs -r` matters: `gofmt -l` with no arguments reads standard input
and waits.

Scope `gofmt` to the files the change touched. Repositories that grew module by
module often carry pre-existing formatting debt, and reporting it on every change
buries the one file this change mis-formatted. The same goes for lint findings in
untouched code: if you run the linter without `--new-from-rev` as well, report those
separately as debt, not as this change's failure.

Use the golangci-lint version CI uses. A newer or older one finds different issues,
and a local pass then says nothing about the pipeline.

## 5. The version moved, and the changelog says so

When a module's version lives in a file (a release manifest, a `version.go`, a
package metadata file) rather than only in a git tag, **a change without a version bump ships
nothing**. The pull request is green, CI publishes no new artifact because the
version already exists, and the fix never reaches an environment. It is invisible in
the diff unless someone looks for the absent line.

Check, against the base branch:

- The version file changed, and the new version is higher.
- The bump matches the change: patch for fixes, minor for new behaviour, major for a
  breaking change to configuration or output.
- The changelog has an entry headed with exactly that version and its release date.
  Release tooling often refuses to publish a version with no matching heading, which
  fails the release instead of the pull request.
- If the version is carried by a git tag instead, nested modules use the directory
  as the tag prefix (`connectors/reader/v1.4.2`). A tag without the prefix belongs to
  the root module. From v2 on, the module path itself must end in the major version
  (`example.com/repo/connectors/reader/v2`), and every importer changes its import
  path; a v2 tag on a module path without `/v2` is not usable as v2.

For how to write the entry itself, see
[release-notes-preparation](../RELEASE-NOTES-PREPARATION/SKILL.md).

## 6. Benchmarks, if the project keeps them

If the module has a benchmark on its hot path and the change touches that path, rerun
it and compare. See
[go-benchmark-regression-check](../GO-BENCHMARK-REGRESSION-CHECK/SKILL.md).

## Failing, warning, and the difference

Hold **new** code to every gate and fail the check when it misses one. Treat
**pre-existing** gaps in untouched code - a legacy module with no benchmark,
formatting debt in files the change did not touch - as warnings to track. Failing a
small fix because the module was already below the bar makes people avoid fixing
legacy modules at all.

## Report

One line per gate, then the overall verdict:

```text
Module: connectors/reader (example.com/repo/connectors/reader)
Tests (race):        PASS
Coverage (overall):  84.2% - PASS (>= 80%)
Coverage (new code): 71.4% (10 of 14 statements in changed code) - FAIL
                     not covered: connectors/reader/plugin/read.go: 88-91
Lint:                PASS
gofmt (changed):     PASS
Version:             1.4.1 -> 1.4.2 - PASS
Changelog:           ## [1.4.2] - 2026-10-19 found - PASS
Benchmark:           WARN - none on the hot path (pre-existing)
Overall:             FAIL
```

A WARN does not fail the check. Every FAIL names what to change.

Delete `coverage.out` when done; it is build output, not something to commit.
