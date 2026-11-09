# Oracle

Format traps when the legacy side is Oracle, compared through an export or a
direct query.

## Values

- **An empty string is `NULL`.** Oracle stores `''` in a `VARCHAR2` as `NULL`.
  A lakehouse keeps the two apart, so a pipeline that writes `''` produces a
  `blank_vs_null` difference on every such row. Decide which the target should
  hold and normalize the comparison to it; do not let it hide a real `NULL`.
- **`DATE` includes a time.** An Oracle `DATE` holds the time to the second, and
  a lakehouse `DATE` holds none. If the target maps it to `DATE`, check whether
  the time was ever used:

  ```sql
  -- On Oracle: rows where the time part is not midnight
  SELECT count(*) FROM sales.orders WHERE order_date <> TRUNC(order_date);
  ```

  A non-zero count means the target loses information, which is a defect or a
  decision for the owner, not a format difference. The digits differ, so the
  classification will not call it `date_format`.
- **Exports follow the session's NLS settings.** `NLS_DATE_FORMAT` decides how
  dates are written; the common default `DD-MON-RR` has month names in the
  session's language and a two-digit year, which the `RR` rule maps to a
  century. `NLS_NUMERIC_CHARACTERS` decides the decimal separator, and
  `NLS_TIMESTAMP_FORMAT` the timestamps. Read the settings of the session that
  wrote the export before parsing anything.
- **`NUMBER` without precision** holds up to 38 significant digits at any
  scale, while a lakehouse `DECIMAL(p,s)` rounds to its scale. Differences in
  the last digits come from that type decision; compare at the target's scale
  and report the rounding once, rather than per row. `BINARY_DOUBLE` and
  `FLOAT` are compared at an agreed scale, not for exact equality.
- **`CHAR(n)`** is padded with trailing spaces, and Oracle compares two `CHAR`
  values with blank padding but a `CHAR` and a `VARCHAR2` without it. Trim for
  the comparison.
- **Time zones.** `TIMESTAMP WITH LOCAL TIME ZONE` is shown in the session's
  time zone, and `TIMESTAMP WITH TIME ZONE` keeps its offset. Compare both as
  instants.
- **Character sets.** Text moved between a single-byte database character set
  and UTF-8 can arrive with replaced or garbled characters. Those show up as
  `different_value`, and the fix is the export's encoding, not a comparison
  rule.

Oracle compares strings case-sensitively unless `NLS_COMP` and `NLS_SORT` are
set to linguistic, case-insensitive settings. A `case` difference against
Oracle is therefore unusual and worth asking about.
