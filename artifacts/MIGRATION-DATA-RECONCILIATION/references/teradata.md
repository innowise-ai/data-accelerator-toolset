# Teradata

Format traps when the legacy side is Teradata, compared through an export
(BTEQ, FastExport, TPT) or a direct query.

## Comparison rules that the lakehouse does not share

- **Case.** In Teradata session mode, the default for BTEQ, character
  comparisons are `NOT CASESPECIFIC` unless the column says otherwise; in ANSI
  mode they are case-specific. A legacy join, `GROUP BY` or uniqueness check may
  therefore have treated `'abc'` and `'ABC'` as one value, and the lakehouse
  treats them as two. That shows up as rows that do not pair, or as duplicates
  in the target. It is a logic difference, not a format, so ask before
  normalizing case.
- **Trailing spaces.** Teradata compares strings as if the shorter one were
  padded with spaces, so `'abc' = 'abc  '`. `CHAR(n)` columns are stored padded,
  and exports keep the padding. Trim both sides.
- **SET tables** silently reject rows that duplicate an existing row exactly;
  `MULTISET` tables keep them. A lakehouse table keeps duplicates, so a target
  can hold rows that the legacy table never could. Check which kind each legacy
  table is before calling extra target rows a defect.

## Values

- **Dates.** A `DATE` is stored as an integer,
  `(year - 1900) * 10000 + month * 100 + day`, so an export that casts it to a
  number writes `1260115` for 2026-01-15. As text, its format depends on the
  session's `DATEFORM`: `INTEGERDATE` gives `YY/MM/DD`, with a two-digit year,
  and `ANSIDATE` gives `YYYY-MM-DD`. A column-level `FORMAT` phrase can override
  either. Find out which one the export used before parsing.
- **Timestamps** carry up to six fractional digits. Values exported as text are
  rendered in the session time zone. Compare instants, not text.
- **Numbers.** A `FORMAT` phrase on a column changes how exports render it,
  including separators and sign position. Compare `DECIMAL` columns as decimals
  at their declared scale, and `FLOAT` columns, which are binary doubles, at an
  agreed scale rather than for exact equality.
- **`NULL` and empty strings** are distinct in Teradata, but a delimited export
  usually writes both as nothing. The distinction is lost in the file, so
  compare it only against a source that keeps it, such as a direct query.
