# Building the controls in Python pipeline code

The concepts are the same as in SKILL.md; this file covers where they go in a
Python pipeline. For keeping the I/O at the edges so these functions can be
tested, see [etl-decomposition](../../ETL-DECOMPOSITION/SKILL.md).

## The structural check is a comparison, not a parse

Compare the delivery's columns and types with the expected schema for the
segment before validating any record, and stop the batch on a difference:

```python
def structural_problems(columns, expected):
    """Return readable problems; an empty list means the structure matches.

    columns and expected map a column name to its type name.
    """
    problems = [f"column {name} is missing" for name in expected if name not in columns]
    problems += [
        f"column {name} is {columns[name]}, expected {expected[name]}"
        for name in expected
        if name in columns and columns[name] != expected[name]
    ]
    problems += [f"unexpected column {name}" for name in columns if name not in expected]
    return problems
```

Whether an unexpected column stops the batch or only warns is the project's
decision; keep that last kind of problem separate if it only warns.

## Validation returns failures, it does not raise

A validation function that raises on the first bad record stops the batch, which
is the dbt test problem again. Have each check return failure records, and split
the batch on them:

```python
def validate(records, rules):
    failures = [
        failure
        for record in records
        for rule in rules
        if (failure := rule.check(record)) is not None
    ]
    rejected = {f.entity_key for f in failures if f.severity == "reject"}
    valid = [r for r in records if r.key not in rejected]
    return valid, failures
```

The rule objects are built from the rule configuration. Each check kind (not
null, range, pattern, reference) is a small function written once; the rules are
instances of those kinds with parameters from the configuration file, so a new
rule of an existing kind needs no code. Apply the parent rule after this: drop
the children of every rejected parent before writing anything.

A schema library can run the checks, provided it can collect every failure instead
of stopping at the first one, and report which row failed; the routing into valid
and quarantined records is still yours.

## Writing the quarantine

Write the quarantine with an upsert keyed on `(segment, entity_type, entity_key,
rule_id, field)`, in one transaction with the valid records, so a crash cannot
leave the published data updated and the quarantine not, or the other way round.

Make the batch id an argument of the run, not something the run generates. A
retried run then knows it is the same batch, and the rule from
[quarantine.md](quarantine.md) holds: occurrences go up only for a new batch, and
a rerun changes nothing.

## Slow external checks

Check URLs and other external references in a separate step before validation,
with a cache keyed on the reference and a per-host limit on concurrent requests
(a semaphore per host in `asyncio`, for instance). Store the result as a field the
rules can read. The validation loop itself never waits on the network.
