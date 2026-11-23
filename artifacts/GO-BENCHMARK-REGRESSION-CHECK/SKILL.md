---
name: go-benchmark-regression-check
description: Writes a Go benchmark for a component's per-record hot path on a realistic input, and compares it before and after a change with benchstat so a slowdown or an allocation increase is caught and recorded. Use when adding a benchmark, or when a change touches code that runs once per record, event or message.
---

# Catching performance regressions in a Go hot path

A connector, mapper or event processor does the same work once per record, millions
of times a day. A change that adds one allocation or a few hundred nanoseconds per
record looks harmless in review and costs real CPU and memory at volume. A benchmark
on the hot path is how that change becomes visible before it ships.

A benchmark only helps if it measures something real and if its result is compared,
not just printed. Both are where it usually goes wrong.

## Benchmark the path that runs per record

Find the function the runtime calls once per unit of work - `Process`, `Convert`,
`Map`, `Write` for one event - and benchmark that, configured as it is in
production. Benchmarking a helper three calls down measures the helper, and the
regression arrives through the part you did not measure.

```go
func BenchmarkProcess(b *testing.B) {
	p := newProcessor(b, loadConfig(b, "testdata/config_typical.json"))
	event := loadEvent(b, "testdata/event_typical.json")

	b.ReportAllocs()
	for b.Loop() {
		if _, err := p.Process(context.Background(), event); err != nil {
			b.Fatalf("process: %v", err)
		}
	}
}
```

`b.Loop()` (Go 1.24+) runs the setup above it once, times only the loop, and keeps
the compiler from optimising away a result nobody reads. On older Go, use
`for i := 0; i < b.N; i++` and call `b.ResetTimer()` after the setup, or the setup
time is added to the measured total and inflates every per-operation figure.

`b.ReportAllocs()` (or `-benchmem` on the command line) reports allocations per
operation. **Allocations are the more useful number.** They are close to
deterministic, so a change from 14 to 15 allocs/op is real; time per operation
moves with CPU frequency, other processes and the machine. Allocation growth also
costs more at scale than it looks, because it is paid again as garbage-collection
work.

## A realistic input, or the benchmark proves nothing

A two-field toy event measures the fixed overhead of the call and nothing else. Real
payloads have nested objects, long arrays and many fields, and that is where the cost
is: map growth, string building, reflection over every field, repeated decoding.
A regression in any of those does not show on a toy.

Use an input shaped and sized like production traffic, kept in `testdata/`. If
payloads vary widely, add a second benchmark for the large case (`BenchmarkProcess/large`
with `b.Run`) rather than averaging them into one number. Strip anything sensitive
from a captured payload before committing it.

## Compare, don't eyeball

One run of each version and a glance at the numbers cannot tell a 5% regression from
noise. Run each version several times and let `benchstat` decide:

```bash
# baseline: the base branch, in a separate worktree so nothing is stashed or lost
git worktree add --detach ../base <base-branch>
(cd ../base/<module> && go test -run='^$' -bench=. -benchmem -count=10 ./... > /tmp/old.txt)

# candidate: this branch
(cd <module> && go test -run='^$' -bench=. -benchmem -count=10 ./... > /tmp/new.txt)

benchstat /tmp/old.txt /tmp/new.txt
git worktree remove ../base
```

`-run='^$'` skips the unit tests. `-count=10` gives benchstat enough samples to say
whether a difference is significant; it prints the change with a p-value, or `~` when
the difference is within noise. A `~` is a result: it means no measurable change, and
it should be reported as such rather than as a number.

Run both sides on the same machine, one after the other, with nothing heavy running.
Laptop power saving and thermal throttling move ns/op by more than the regressions
you are looking for.

## When a change is a regression

The threshold is the project's call. A common rule: a statistically significant
increase of **10% or more** in time or allocations per operation is a finding. The
change either finds and removes the cause, or the pull request says why the cost is
accepted (a correctness fix that needs the extra work, a feature that is meant to
cost something).

A refactor that should not change behaviour should not change allocations either.
An unexplained allocation increase there is worth investigating even below the
threshold, because it usually means something escaped to the heap that did not
before. `go build -gcflags=-m` on the package shows escape decisions.

Purely cosmetic changes (renames, comments, formatting) can skip the run, but say so
in the commit message so the next reader knows it was a decision, not an omission.

## Record the numbers where readers will find them

Keep the latest figures with the component, typically a Performance section in its
README, with the date and the CPU. The `go test` output header prints the CPU model;
copy it. A figure without its hardware cannot be compared with the next run, and the
next person to benchmark needs to know whether a difference is the code or the
machine.

```markdown
## Performance

Measured 2026-10-19 on Intel Core i7-1185G7, Go 1.24, `go test -bench=. -benchmem -count=10`.

| Benchmark | ns/op | B/op | allocs/op |
|---|---|---|---|
| Process/typical | 18 400 | 6 112 | 41 |
| Process/large | 212 000 | 88 960 | 512 |
```

Keep these figures out of release notes. Users configuring the component cannot act
on ns/op, and the numbers date with the machine.

## Do not gate CI on time per operation

Shared CI runners are noisy enough that a time threshold either fails at random or is
set so loose it catches nothing. If CI checks benchmarks at all, check allocations
per operation, which are stable across machines, and leave time comparisons to a
controlled run like the one above.
