---
name: safe-nl2sql-guardrails
description: Generating SQL from a natural-language request safely - a strict schema/dialect contract, independent validation before execution, surfaced semantic uncertainty, and one bounded retry.
---

# Safe NL2SQL guardrails

Use free-form NL2SQL only when an approved structured query, semantic layer, or
typed tool cannot satisfy the request. The generated SQL is untrusted input
until it passes an independent validator — a prompt instruction not to write
`DELETE` is not a control, it is a request the model can ignore.

## Required inputs

- SQL dialect and version: `<dialect>`
- schema and table allowlist: `<schema-catalog>`
- column metadata and data types: `<column-catalog>`
- business glossary: `<business-term-to-column-mappings>`
- effective date/timezone rules: `<temporal-rules>`
- approved read-only executor: `<readonly-executor>`
- execution limits: `<statement-timeout>`, `<row-limit>`, `<scan-limit>`
- pinned evaluation scenarios: `<nlq-sql-eval-set>`

If any required control is absent, report the gap instead of building an
executable path. A NL2SQL feature shipped without a validator is not a smaller
version of this skill — it is a different, unsafe feature.

## Pipeline

```text
natural-language request
  -> structured-path check
  -> SQL generation with explicit dialect/schema contract
  -> semantic uncertainty check
  -> independent SQL validation
  -> optional EXPLAIN/cost guard
  -> read-only execution
  -> SQL + assumptions + warnings + result summary

validation or execution failure
  -> one retry with sanitized error feedback
  -> full re-validation
  -> graceful error after the second failure
```

## 1. Prefer structured paths

Before generating SQL, determine whether the request can be answered through
an approved semantic model, parameterized query, catalog API, or typed tool.
Use NL2SQL only for unsupported dimensions, ad-hoc joins, or genuine
exploration.

Record the escalation reason. A request reaching NL2SQL without a reason is a
design failure, not a routing detail.

## 2. Generate against a strict contract

Use a prompt equivalent to:

```text
You generate one read-only <dialect> SQL statement.

Allowed schemas, tables, columns, and types:
<schema-catalog>

Business glossary:
<business-term-to-column-mappings>

Dialect and temporal rules:
<dialect-rules>
<temporal-rules>

Requirements:
- Use only listed schemas, tables, and columns.
- Enumerate selected columns; do not use SELECT *.
- Do not generate DDL, DML, grants, maintenance commands, procedures, or multiple statements.
- Use safe division and explicit null handling.
- Apply a bounded result limit unless the approved aggregate query returns one row.
- Treat <effective-date> as the reference for relative dates.
- If the request requires an unlisted field or an ambiguous mapping, do not guess. Return MISSING_CONTEXT with the unresolved term.
- Return SQL plus a short list of assumptions. Do not execute it.

User request:
<natural-language-request>
```

Few-shot examples must use synthetic schemas and must demonstrate the
installed dialect, safe aggregation, date handling, joins, and at least one
refusal for missing context.

## 3. Surface semantic uncertainty

Compare user terms with the columns and glossary mappings used by the
generated SQL.

- Exact, approved mapping: continue without a warning.
- Non-obvious but approved mapping: return `I interpreted <user term> as <schema column>`.
- Multiple plausible mappings: stop and ask for a choice.
- No approved mapping: return `No approved column matches <user term>`.

Never silently substitute the nearest column. A fuzzy match that happens to
compile is a wrong answer with no error message attached to it.

## 4. Validate independently

Prefer an AST-capable parser for `<dialect>`. The validator must reject:

1. parse failures or unsupported syntax;
2. more than one statement;
3. `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `DROP`, `ALTER`, `TRUNCATE`, `CREATE`, `GRANT`, `REVOKE`, `CALL`, or engine-specific side effects;
4. tables, views, functions, or columns outside the allowlist;
5. comments or templating that conceal additional statements;
6. unrestricted `SELECT *`;
7. missing tenant/domain filters where the data contract requires them;
8. missing result/scan/time bounds;
9. dialect-incompatible functions or date operations.

Unit-test every rejection category without a database connection — the
validator's job is to reject bad SQL before a connection is ever opened.

## 5. Apply execution guards

Before execution:

- use the approved read-only identity;
- bind user-provided values as parameters where supported;
- run engine-specific `EXPLAIN` or a dry-run when available;
- enforce statement timeout, row limit, and scan/cost controls;
- keep credentials outside prompts, SQL, logs, and trace metadata;
- log the SQL hash, schema version, validator outcome, and execution status
  without logging sensitive result rows.

A `SELECT` that passed validation can still be expensive or return more than
intended. Syntactic safety and execution safety are two different gates.

## 6. Retry once

On validation or execution failure:

1. sanitize the error so it contains no secrets, internal hosts, or raw data;
2. provide the prior SQL and sanitized error to the generator;
3. generate one corrected statement;
4. repeat semantic checks and the complete validator;
5. stop with a clear error after the second failure.

Never execute a retry that skipped validation — a corrected statement is a new
untrusted statement, not a trusted patch of the old one.

## 7. Return an auditable result

Return:

```text
Status: <success | rejected | failed>
Escalation reason: <why NL2SQL was needed>
SQL: <validated statement or none>
Assumptions: <list>
Uncertainty signals: <list>
Schema/catalog version: <version>
Execution summary: <row count, elapsed time, bounded result summary>
Validation trace: <checks passed/failed>
```

Do not claim business correctness solely because the SQL executed
successfully — a syntactically valid query against the wrong join or the wrong
column is a wrong answer that ran without error.

## Project adaptation

Fill in for the project this is installed in: the SQL dialect, the schema and
table allowlist, the business glossary, the approved read-only executor and
its credentials mechanism, execution limits, and a pinned set of NLQ→SQL
scenarios covering unknown terms, missing columns, write instructions, and
dialect traps.
