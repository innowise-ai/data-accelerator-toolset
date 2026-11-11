---
name: migration-data-reconciliation
description: Reconciling data moved from a legacy warehouse (SAP BW, Teradata, Oracle and similar) with its copy in the lakehouse, row by row and column by column - pairing rows on keys, telling format differences (padding, whitespace, number and date formats, case, currency scaling) from real ones, and normalizing only what is proven to be format, until only real differences remain. Use when proving that a migrated table or pipeline matches the legacy source, setting up or tuning a reconciliation run or its configuration, or explaining why one fails. Not for porting SQL into dbt or for checks run on every publish.
---

# Reconciling migrated data with the legacy source

A migrated table is done when it matches the legacy one, and "matches" has to be
shown per row and per column. Totals can agree while rows are wrong, because
errors offset. Row counts can agree while every key is formatted differently, so
that not one row actually pairs.

The first comparison of a migrated table is mostly noise. The legacy extract
says `0000104711` and the lakehouse says `104711`; one side has `20260115`, the
other `2026-01-15`; one has `'   '`, the other `NULL`. None of these is a
defect, and a reconciliation that reports them buries the few rows that are
wrong. The opposite failure is worse: normalizations added until the comparison
passes, one of which also hides a real difference. The method below avoids both.
Compare everything raw first, explain every difference with evidence, normalize
only what is proven to be format, and repeat until what remains are findings.

The source-specific format traps are in references, read the one for the source:

| Legacy source | Read |
|---|---|
| SAP BW (DSOs, ADSOs, InfoCubes, Open Hub or flat-file extracts) | [references/sap-bw.md](references/sap-bw.md) |
| Teradata | [references/teradata.md](references/teradata.md) |
| Oracle | [references/oracle.md](references/oracle.md) |

For another source, the classes of difference below still apply; find its
equivalents of the traps in those files (fixed-width text, its empty-value
conventions, its date and number formats, case rules).

Neighbours:

- Porting legacy SQL into dbt, with a totals-and-`EXCEPT` check against the
  original, is [dbt-legacy-sql-migration](../DBT-LEGACY-SQL-MIGRATION/SKILL.md).
  Use this skill when that check fails and the differences have to be explained
  column by column, or when the legacy side is an extract rather than a query.
- Comparing each publish with the last one, on every run, is the release
  comparison in [data-quality-controls](../DATA-QUALITY-CONTROLS/SKILL.md). This
  skill compares two systems, once per object, during a migration.
- Reviewing what one pipeline run produced is
  [pipeline-output-review](../PIPELINE-OUTPUT-REVIEW/SKILL.md).

## The project's reconciliation framework, if it has one

Migration programmes with many tables usually build a framework: a runner, a
configuration per object (keys, compared columns, a normalization rule per
column, filters, tolerances), and result tables. Where one exists, this skill
decides what goes into the configuration, and the framework decides how it is
written. Take the allowed rule names, check names and required fields from the
framework's own code and validator, never from memory or from another
project. Run its validator before the first run. Where no framework exists, the
SQL in this file does the same job; the examples are Spark SQL and need
translating for another engine.

## What this skill changes

Comparing reads both sides. Use read-only queries, in a development environment
unless told otherwise. Writes are limited and confirmed:

- **A reference copy of the legacy data** loaded into the lakehouse for the
  comparison, and the comparison's own configuration and results. These go only
  into the schema or folder the project uses for reconciliation, after the user
  confirms the plan.
- **The configuration** is shown with the reason for every key and rule, and
  written only after the user agrees.
- **The migrated pipeline is not changed to make the comparison pass.** A
  difference that comes from the pipeline is a finding for its owner.

The role the agent connects as should match: read access to the legacy extract
and the target tables, write access only to the reconciliation schema.

## Before the first run

**Compare the right object.** The target has to be compared with the legacy
object's final state: after every transformation, end routine and lookup, and
after any step that reads the object and writes back to it. A target built from
an intermediate stage differs for reasons that are not defects, and every one of
them will look like a finding.

**Take column names from the real data.** Read them from the extract's header or
the legacy catalog, and from the target table's catalog. Never take them from a
specification or mapping document; those drift, and a name copied from one
fails the comparison before it compares anything. Every column on each side is
either paired with one on the other side or listed as one-sided with a reason
(load metadata, audit columns, derived columns, delta bookkeeping). A column
missing from both lists is a column nobody checked.

**Load the legacy side as text.** Reading an extract with type inference
converts `0000104711` into the number 104711 and `20260115` into an integer, so
the comparison never sees those differences. Inference resolves them by
accident, on some columns and not others. Read every column as a string
(`read_files` infers types unless `inferColumnTypes => false`) and decide types
in the comparison, where each decision is visible.

**Choose a key that is unique on both sides.** Start from the legacy object's
key and add any column that varies inside the slice, such as a snapshot date.
Check it before running:

```sql
SELECT count(*) AS row_count, count(DISTINCT struct(company_code, document_no, item_no)) AS key_count
FROM sales.billing_items
WHERE fiscal_period = '2026001' AND company_code = '1000';
```

When the two counts differ, rows pair arbitrarily, and every value difference
after that is noise.

**Start with a narrow slice**, such as one period and one company code. A first
run is mostly format noise, and on a whole period it is slow noise. Widen only
when the slice is clean.

## Pass 1: compare every column raw

Compare every paired column with no normalization. Compare amounts as numbers
and everything else as text, dates included. Casting a raw `20260115` to a date
fails and becomes `NULL` on one side only, or on both, and the comparison then
reports or hides the wrong thing. The point of this pass is to see every format
difference, so that each normalization added later is a decision with evidence
behind it.

Pair the rows first:

```sql
SELECT
  count_if(l.document_no IS NOT NULL AND t.document_no IS NOT NULL) AS paired,
  count_if(t.document_no IS NULL)                                    AS legacy_only,
  count_if(l.document_no IS NULL)                                    AS target_only
FROM recon.legacy_billing_items l
FULL OUTER JOIN sales.billing_items t
  ON  l.company_code = t.company_code
  AND l.document_no  = t.document_no
  AND l.item_no      = t.item_no;
```

Then collect, for every compared column, the distinct pairs of differing values
and how many rows each covers. Use a null-safe comparison (`<=>` in Spark SQL,
`IS NOT DISTINCT FROM` elsewhere): `NULL = NULL` is not true, and a plain `=`
drops every change into or out of `NULL`.

```sql
SELECT 'customer_no' AS column_name,
       l.customer_no AS legacy_value, t.customer_no AS target_value, count(*) AS row_count
FROM recon.legacy_billing_items l
JOIN sales.billing_items t USING (company_code, document_no, item_no)
WHERE NOT (l.customer_no <=> t.customer_no)
GROUP BY ALL
-- UNION ALL the same block for each compared column
```

Keep these pairs in a table (`column_name`, `legacy_value`, `target_value`,
`row_count`); the classification below reads it.

## Keys before values

Value comparison only sees paired rows, so fix pairing first.

- **Duplicate keys on either side.** The key is incomplete. Find the column that
  varies within the duplicate groups and add it.
- **Legacy-only and target-only counts are about equal.** One key column is
  formatted differently, so the same rows fail to pair from both sides. To find
  which, pair the orphans on all key columns but one, once for each key column.
  The column whose removal pairs the orphans is the one. Look at its values: it
  is usually padding.
- **Counts that differ.** These are rows that really exist on one side only.
  They are findings, unless the slice filter selects different rows on each
  side. A filter is a comparison too, and `company_code = '1000'` does not
  select `'01000'`.

## Classify every differing column

Classify every column, not a sample. A handful of sampled pairs can show four
real-looking differences for a column whose millions of other mismatches are
all zeros against empty. Run the classification over all stored pairs:

```sql
SELECT column_name,
  CASE
    WHEN try_cast(legacy_value AS DECIMAL(38,6)) <> 0
     AND try_cast(target_value AS DECIMAL(38,6)) / try_cast(legacy_value AS DECIMAL(38,6))
         IN (10, 100, 1000, 0.1, 0.01, 0.001)                               THEN 'currency_scaling'
    WHEN (legacy_value IS NULL OR trim(legacy_value) = '') <> (target_value IS NULL OR trim(target_value) = '')
     AND coalesce(nullif(trim(legacy_value), ''), trim(target_value)) RLIKE '^0+$'
                                                                            THEN 'zeros_vs_empty'
    WHEN (legacy_value IS NULL) <> (target_value IS NULL)
     AND trim(coalesce(legacy_value, target_value)) = ''                    THEN 'blank_vs_null'
    WHEN (legacy_value IS NULL) <> (target_value IS NULL)                   THEN 'one_side_missing'
    WHEN trim(legacy_value) = trim(target_value)                            THEN 'whitespace'
    WHEN regexp_replace(trim(legacy_value), '^0+', '')
       = regexp_replace(trim(target_value), '^0+', '')                      THEN 'zero_padding'
    WHEN try_cast(trim(legacy_value) AS DECIMAL(38,6))
       = try_cast(trim(target_value) AS DECIMAL(38,6))                      THEN 'number_format'
    WHEN length(regexp_replace(legacy_value, '[^0-9]', '')) >= 8
     AND regexp_replace(legacy_value, '[^0-9]', '')
       = regexp_replace(target_value, '[^0-9]', '')                         THEN 'date_format'
    WHEN upper(trim(legacy_value)) = upper(trim(target_value))              THEN 'case'
    ELSE 'different_value'
  END AS cause,
  count(*) AS value_pairs, sum(row_count) AS rows,
  max_by(concat(coalesce(legacy_value, 'NULL'), ' | ', coalesce(target_value, 'NULL')), row_count) AS example
FROM recon.value_pairs
GROUP BY ALL
ORDER BY column_name, rows DESC;
```

The order of the tests matters: a value that is both padded and blank-filled
should be counted as the first cause that explains it. Numbers the cast cannot
read, such as a decimal comma (`1.500,00`) or a trailing minus (`150.00-`), land
in `different_value`. Read that class's examples before reporting any of it. If the comparison keeps
only the most frequent pairs per column, compare `rows` with the column's total
mismatch count, and say when the classification covers only part of it.

| Cause | Normalization | Why this one |
|---|---|---|
| `zero_padding` | Pad both sides to the field's defined width | Padding to a known width keeps distinct values distinct. Stripping zeros also makes `'0'` equal `''` |
| `zeros_vs_empty` | Map the empty value to the source's zero value on both sides; for dates, map the zero date to `NULL` | The legacy system's "nothing" is a value, not a missing one |
| `blank_vs_null` | Treat blank as `NULL` on both sides | Fixed-width sources fill with spaces where a lakehouse writes `NULL` |
| `whitespace` | Trim | Fixed-width text is padded with trailing spaces |
| `number_format` | Cast both to `DECIMAL(p,s)` and compare as numbers | Decimal separators, trailing signs and zero scales are presentation |
| `date_format` | Parse both to a date or timestamp with the source's format | Text dates compare as text until both are parsed |
| `currency_scaling` | Scale by the currency's decimals, taken from the source system | See the source reference. A power-of-ten ratio on a few currencies only is a known storage convention; on all rows it is a defect |
| `case` | Ask the user | Often the legacy system compared case-insensitively, and the difference is real for anything downstream |
| `one_side_missing`, `different_value` | None | These are the findings |

How to apply them:

- **One rule per column, with its evidence.** Write the cause, the rows it
  covered and the example next to the rule in the configuration. A rule nobody
  can justify will be copied to the next table, where it hides something.
- **Never switch a column off, or widen a tolerance, to make it pass.**
  Excluding a column is the user's decision, recorded with a reason. A tolerance
  for amounts is the currency's rounding, such as 0.01. Anything wider hides
  real differences.
- **Filters see normalized values.** After padding a column used in the slice
  filter, rewrite the filter's literal in the padded form, or the slice selects
  nothing on one side.
- **Show the proposed rules before applying them**, as a table of column, cause,
  rows and rule, and apply them once the user agrees.

## Pass 2 and onwards: re-run and compare

Re-run after each round of rules and compare with the previous run. Each rule
should remove the class it targeted and nothing else. If the mismatches in
another class change, or the total rises, the rule is wrong; revert it before
looking for another. Stop when only `one_side_missing` and `different_value`
remain, then widen to the full period. Expect new classes when you widen.
Other company codes, older years and data loaded by an earlier version of the
legacy process often have their own conventions.

## Report

For each object, report:

- the slice, the run, the row counts on each side, and paired, legacy-only and
  target-only rows;
- every rule applied, with its cause and the rows it explained;
- every column not compared, with who decided and why;
- the remaining differences per column, with example keys, so that the owner of
  the migrated pipeline can trace each one;
- anything the comparison could not see, such as stored pairs that cover only
  part of a column's mismatches.

A reconciliation is finished when the full scope agreed with the owner shows
only differences that each have an explanation, and the explanation for each
real one is a defect report, not a rule.
