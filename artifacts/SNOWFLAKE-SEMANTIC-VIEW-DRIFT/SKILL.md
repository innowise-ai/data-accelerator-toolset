---
name: snowflake-semantic-view-drift
description: Detecting and repairing drift between a Snowflake semantic view and the tables beneath it - classifying added, dropped, renamed and retyped columns, and regenerating the view without losing hand-written descriptions.
---

# Semantic view drift

A semantic view declares dimensions, facts and metrics as expressions over base
table columns. When a base table changes and the view does not, the view fails
outright for anyone who touches an affected element — a consumer does not get a
degraded answer, it gets an error. This skill finds that drift, classifies it, and
produces a replacement definition that keeps everything a human wrote.

The expensive part of a semantic view is not the DDL. It is the comments,
synonyms, custom instructions and verified queries, which were written by someone
who understood the data. Any fix that regenerates the view from the table schema
throws those away. Every step below is arranged to prevent that.

## Establish which definition is the real one

There can be three versions of the truth: the definition in source control, the
view deployed in Snowflake, and the live tables. Drift is between the first two
and the third, but only if the first two agree.

If the view is deployed from the repository — a DDL file, a YAML model passed to
`SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML`, a dbt model — compare the deployed view
against that source before doing anything else:

```sql
select get_ddl('semantic_view', '<db>.<schema>.<view>');
-- or, when the source is YAML:
select system$read_yaml_from_semantic_view('<db>.<schema>.<view>');
```

If they differ, someone changed the live object by hand, and that change will be
reverted by the next deployment regardless of what you fix now. Stop and resolve
which one is intended. When they agree, make the fix in the source file, not
against the live object — a fix applied only to Snowflake is undone by the next
deploy, and the drift comes back looking like a new incident.

## Read the declared side

`GET_DDL` is the verbatim source for everything that must be preserved: comments,
synonyms, primary keys, relationships, `AI_SQL_GENERATION`,
`AI_QUESTION_CATEGORIZATION`, verified queries and tags. Keep its output as the
starting text for the fix.

`DESCRIBE SEMANTIC VIEW` gives the same content as rows, which is easier to diff:

```sql
describe semantic view <db>.<schema>.<view>;

select "object_kind", "object_name", "parent_entity", "property", "property_value"
from table(result_scan(last_query_id()))
where "object_kind" in ('TABLE', 'DIMENSION', 'FACT', 'METRIC', 'DERIVED_METRIC', 'RELATIONSHIP');
```

From this, build two maps:

- **Logical table → base table**, from the `TABLE` rows' `BASE_TABLE_DATABASE_NAME`,
  `BASE_TABLE_SCHEMA_NAME` and `BASE_TABLE_NAME` properties.
- **Element → base columns it references**, from each dimension's, fact's and
  metric's `EXPRESSION`. Most expressions are `alias.column`, but some are `CASE`
  expressions, casts or concatenations referencing several columns. Read each one;
  do not assume one element maps to one column. Metrics usually reference facts
  rather than columns, so follow that chain down to the columns it ends on.
  Relationships and primary keys reference columns too.

## Read the live side

```sql
select table_catalog, table_schema, table_name, column_name, ordinal_position,
       data_type, character_maximum_length, numeric_precision, numeric_scale,
       comment
from <db>.information_schema.columns
where table_schema = '<SCHEMA>'
  and table_name in ('<TABLE_1>', '<TABLE_2>')
order by table_name, ordinal_position;
```

Run it once per database the view draws from. Unquoted identifiers are stored in
upper case; compare names the way Snowflake resolves them, or a quoted mixed-case
column will look dropped when it is not.

Check first that every base table still exists. A missing or renamed table breaks
every element over it and is a different conversation from column drift.

## Classify the drift

Report by kind, because each kind has a different fix and a different risk.

| Kind | How it shows | What breaks | Fix |
|---|---|---|---|
| Dropped column | Referenced by an element, absent from the table | Every element referencing it, every metric built on those, any relationship or key using it | Remove or repoint the elements — a consumer-visible change |
| Added column | Present in the table, referenced by nothing | Nothing | Expose it only if someone decides it belongs in the view |
| Renamed column | Looks like one dropped plus one added | Same as dropped | Repoint the expression, keep the element name and its description |
| Changed type | Referenced, present, different type | Depends on the change | Review the elements that use it |

**Dropped columns.** List every consumer-visible element that stops working, not
only the one whose expression names the column. A dropped fact takes every metric
over it down with it, a dropped join key breaks a relationship, and with it every
query that crosses that join. Verified queries that use a removed element fail as
well. Removing an element is a breaking change for whoever queries it by name. Say
so explicitly rather than burying it in the DDL.

**Added columns.** A semantic view is curated. Most tables have columns that were
deliberately left out, so "unreferenced" does not mean "new". Snowflake does not
record when a column was added, so the drift check cannot tell a new column from a
column someone chose to exclude. If the project keeps a list of excluded columns
next to the view definition, use it. If not, list the unreferenced columns and ask
which ones should be exposed, then suggest recording the answer so the next run
does not have to ask again.

**Renames.** A naive diff reports a rename as one dropped column and one added
column. Applying that literally deletes the element, discards its description, and
adds a fresh element with no description under a new name. Every consumer query
that used the old element name breaks, even though the data is still there.

The element name is the contract with consumers; the base column behind it is an
implementation detail. A confirmed rename is fixed by changing the expression and
leaving the element name, comment and synonyms untouched.

Treat a drop and an add in the same table as a rename candidate when the data type
matches, and more strongly when the ordinal position or the column comment
matches, or when the names are close. Look for direct evidence:

```sql
select start_time, user_name, query_text
from snowflake.account_usage.query_history
where query_text ilike '%rename column%'
  and query_text ilike '%<OLD_COLUMN>%'
  and execution_status = 'SUCCESS'
  and start_time >= dateadd('day', -90, current_timestamp())
order by start_time desc;
```

An `ALTER TABLE ... RENAME COLUMN` statement is strong evidence. Its absence is
weak evidence, because a pipeline that rebuilds the table with `CREATE OR REPLACE`
renames a column without ever issuing a rename statement. Present each candidate
with the evidence for it and get confirmation before generating DDL that treats it
as a rename. A guessed rename silently rebinds a trusted element name to different
data. That is worse than a broken view, because nothing errors.

**Type changes.** Widening a `VARCHAR` length or a `NUMBER` precision is usually
harmless. A column that became a string breaks `SUM` and `AVG` metrics over it. A
`DATE` that became a `TIMESTAMP` changes grouping granularity: dimensions still
return, with different values. A string that became a number can break comparisons
inside `CASE` expressions. Name the affected elements; do not reword their
descriptions to match, because the description may now be the only record of what
the element was meant to be.

## Generate the replacement

Start from the `GET_DDL` output, or the source file if the view is deployed from
source control, and edit only what the drift requires. Do not rebuild the
definition from the table schema. Editing the existing text is what carries the
comments, synonyms, relationships, custom instructions, verified queries and tags
across; regenerating it is how they get lost.

- **Confirmed renames**: change the expression only.
- **Dropped columns**: remove the elements the user agreed to remove, including
  metrics and verified queries that depend on them. Do not quietly repoint an
  element to a similar-looking column.
- **New columns the user chose to expose**: add the element with no `COMMENT`, and
  list it in the report as needing a description. If the base column has a comment,
  offer it as a proposal marked with where it came from. Do not write it into the
  view without confirmation.
- **Keep `COPY GRANTS`** on the `CREATE OR REPLACE`. Without it, every explicit grant
  on the view is lost. Even with it, ownership moves to the role that runs the
  statement. See
  [snowflake-grants-after-recreate](../SNOWFLAKE-GRANTS-AFTER-RECREATE/SKILL.md).

Never write a description yourself. A plausible invented description is worse than
a missing one: a missing description is visibly incomplete, while an invented one
is trusted by every downstream agent and analyst that reads it, and nothing ever
flags it as a guess.

## Validate before replacing

Only comments can be changed with `ALTER SEMANTIC VIEW`; everything else needs the
view recreated. Create the new definition under a temporary name in the same
schema first. It fails at creation if any expression references a column that
does not exist, which is the cheapest place to find a mistake:

```sql
create semantic view <db>.<schema>.<view>__drift_check
  ...;  -- the edited definition, without COPY GRANTS

select * from semantic_view(
    <db>.<schema>.<view>__drift_check
    dimensions <table_alias>.<dimension>
    metrics <table_alias>.<metric>
) limit 10;

drop semantic view <db>.<schema>.<view>__drift_check;
```

Query at least one dimension and one metric from each logical table, and one
query that crosses each relationship. Then apply the real change through whatever
normally deploys the view.

## Acceptance

The job is done when all of these hold. Check each one; do not infer them from the
DDL having run without errors.

1. Re-running the drift check against the deployed view reports no dropped, renamed
   or retyped columns, and no unreviewed added ones.
2. For every element that existed before and still exists, `COMMENT` and synonyms
   are identical to the pre-change `GET_DDL`. Compare the two as text; do not
   eyeball them.
3. Every element added in this change is either described by a human or listed in
   the report as needing a description.
4. Every element removed in this change is named in the report as a breaking
   change for consumers.
5. The roles that could query the view before still can. `COPY GRANTS` covers the
   explicit grants, but not ownership. A Cortex Agent's executing role also needs
   `SELECT` on the base tables, not only on the view.

## Anti-patterns

- Regenerating the view from the table schema instead of editing the existing
  definition
- Applying a rename as a drop plus an add, which renames a consumer-facing element
  and discards its description
- Confirming a rename from name similarity alone
- Treating every unreferenced column as new and exposing it
- Writing descriptions for new elements instead of flagging them
- Fixing the live view while the source-controlled definition still has the drift
- `CREATE OR REPLACE` without `COPY GRANTS`
