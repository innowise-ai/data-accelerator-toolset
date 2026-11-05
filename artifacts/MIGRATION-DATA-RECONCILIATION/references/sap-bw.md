# SAP BW

Format traps when the legacy side is SAP BW: a DSO or ADSO, an InfoCube, or an
Open Hub or flat-file extract of one.

## Compare the final state

- **A DSO or ADSO has more than one table.** Compare the active data, which is
  what queries read, not the inbound queue or the change log. The change log
  holds before and after images of each change, and comparing it with a target
  that holds current state doubles or cancels every changed record.
- **Routines change the result after the mapping.** Start, end and expert
  routines, and transformations that read the target itself (a lookup on the
  same DSO, or a load from the DSO back into itself), all shape the final state.
  The lakehouse target must implement every one of them before a difference
  means anything. A target built before the last of these steps will differ on
  exactly the rows that step changes.
- **An InfoCube is additive.** Until requests are compressed, the same
  combination of characteristics can appear once per request. Compare on all
  characteristics with the key figures summed, not row by row.
- **Compounded characteristics carry their parent.** A cost centre is unique
  only together with its controlling area, so the key includes both.

## Names

Standard InfoObjects have technical names starting with `0` (`0COMP_CODE`,
`0FISCPER`). Customer InfoObjects live in the `/BIC/` namespace. Extract tools
and loaders rename these in their own way: they strip the `0`, replace the `/`,
and drop or add the text, currency and unit fields that accompany a column. Pair
columns by the names in the actual extract header and the loader's renaming
rules, never by InfoObject names from documentation.

`0RECORDMODE` is delta bookkeeping, not data. Its values are blank for an after
image, `X` for a before image, `D` for a delete, `R` for a reverse image and `N`
for a new image. In an extract of active data it is constant or absent; list it
as legacy-only. An extract taken from a change log has to be netted to the
latest image per key before it can be compared with a current-state target.

## Values

- **ALPHA conversion.** Characteristics with the ALPHA conversion routine store
  numeric values left-padded with zeros to the field length: customer `104711`
  in a 10-character field is `0000104711`. Values that contain letters are not
  padded. So pad only all-digit values, to the InfoObject's length:

  ```sql
  CASE WHEN customer_no RLIKE '^[0-9]+$' THEN lpad(customer_no, 10, '0') ELSE customer_no END
  ```

  Padding every value with a plain `lpad` makes `'AB1'` into `'0000000AB1'`, a
  value neither side holds.
- **NUMC fields** are digits padded with zeros by definition (`007` in a
  three-digit field). The lakehouse often holds them as numbers.
- **Empty values.** An empty characteristic is stored blank. Queries display it
  as `#` or "Not assigned", which is presentation, not the stored value.
- **Dates and times.** Dates are `YYYYMMDD`, and `00000000` means no date.
  Times are `HHMMSS`. Short timestamps are 15-digit numbers `YYYYMMDDhhmmss`, by
  convention in UTC; check that against the time zone the lakehouse stores.
- **Calendar and fiscal periods.** `0CALMONTH` is `YYYYMM` and `0CALWEEK` is
  `YYYYWW`. `0FISCPER` is `YYYYPPP`, so period 1 of 2026 is `2026001`.
  `0FISCPER3` is the period alone, and the mapping from period to calendar dates
  depends on the fiscal year variant (`0FISCVARNT`). Periods above 12 are special
  periods for closing postings, which a calendar-based target may not have.
- **Numbers in text extracts** can carry a trailing minus (`150.00-`) and the
  decimal separator of the user who ran the extract.

## Amounts and currencies

BW stores currency amounts with two decimal places, whatever the currency. For
a currency with a different number of decimals, the stored value is shifted by
`10^(decimals - 2)`: 1,000 JPY, a currency with no decimals, is stored as
`10.00`, and 1.234 KWD, which has three, as `12.34`. Queries and reports apply
the shift back. Whether an extract carries the stored or the displayed value
depends on how it was extracted.

So a ratio of 100 (or 10) between the two sides on rows of a few currencies
only is this convention, not a defect. Before choosing a rule:

- Take the currencies and their decimals from table `TCURX` (field `CURRDEC`)
  in that source system. The list is configuration, and it differs between
  systems; a hardcoded list from another project will be wrong somewhere.
- Decide which form the lakehouse is meant to hold, stored or displayed, and
  scale the legacy side to match. If the target should hold displayed values and
  does not, that is a defect in the pipeline, not a comparison rule.
- Compare an amount together with its currency column. The same number in two
  currencies is not the same amount.

A ratio of 100 on every row, whatever the currency, is not this convention;
it is a defect.
