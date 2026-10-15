# Building the controls in dbt

## Why dbt tests are not the quarantine

A dbt test reports a problem with a model; it does not route records. In
`dbt build`, a model's tests run after the model is built, and a test that fails
with `severity: error` makes dbt skip everything downstream of that model. That is
the opposite of failing the smallest entity: one bad line stops every order.
Lowering the test to `severity: warn` lets everything through, the bad line
included.

`store_failures` writes the failing rows of a test to a table, which helps when
investigating, but that table is rebuilt on every run. It has no history, no
occurrence count and no resolution, so it cannot be the quarantine.

Keep dbt tests for what they are good at: guarding the models these controls
produce (keys unique, the quarantine's identity columns not null). Build the
record routing as models.

## The models, per entity type

```text
stg_order_lines                 typed rows of the batch, with segment and batch_id
int_order_lines__failures       one row per record and failed rule
int_order_lines__valid          staged rows with no rejecting failure and a valid parent
int_dq__failures                union of every entity type's failures
dq_quarantine                   incremental: the quarantine table
```

The structural check runs before `stg_*` is built, in the orchestrator or in a
macro run as an `on-run-start` hook or a separate operation, so that a dropped
column stops the batch instead of failing to compile halfway through.

## Rules from a seed

Keep the rule parameters in a seed, `dq_rules.csv`:

```text
rule_id,entity_type,field,check_kind,param_min,param_max,severity,segment,message_template
LINE_QTY,order_line,quantity,range,1,10000,reject,,Line {key}: quantity {value} is outside 1 to 10000
LINE_PRODUCT,order_line,product_code,not_null,,,reject,,Line {key}: product code is missing
```

Read the rules at compile time and generate one `select` per rule. `run_query`
returns nothing useful while dbt parses the project, so the macro returns an empty
list when `execute` is false, and the model declares its dependency on the seed in
a comment, because a `ref` inside a macro that only runs at execution time is
invisible to the parser:

```sql
{% macro dq_rules_for(entity_type) %}
  {% if not execute %}{{ return([]) }}{% endif %}
  {% set query %}
    select rule_id, field, check_kind, param_min, param_max, severity
    from {{ ref('dq_rules') }}
    where entity_type = '{{ entity_type }}'
  {% endset %}
  {{ return(run_query(query).rows) }}
{% endmacro %}

{% macro dq_check(rule, column) %}
  {%- if rule['check_kind'] == 'not_null' -%}
    {{ column }} is null
  {%- elif rule['check_kind'] == 'range' -%}
    ({{ column }} < {{ rule['param_min'] }} or {{ column }} > {{ rule['param_max'] }})
  {%- else -%}
    {{ exceptions.raise_compiler_error("Unknown check_kind '" ~ rule['check_kind'] ~ "' in rule " ~ rule['rule_id']) }}
  {%- endif -%}
{% endmacro %}
```

```sql
-- int_order_lines__failures.sql
-- depends_on: {{ ref('dq_rules') }}
{% set rules = dq_rules_for('order_line') %}

{% for rule in rules %}
select
    l.segment,
    l.batch_id,
    'order_line' as entity_type,
    l.line_key as entity_key,
    l.order_key as parent_key,
    '{{ rule["rule_id"] }}' as rule_id,
    '{{ rule["field"] }}' as field,
    cast(l.{{ rule["field"] }} as {{ dbt.type_string() }}) as offending_value,
    '{{ rule["severity"] }}' as severity
from {{ ref('stg_order_lines') }} l
where {{ dq_check(rule, 'l.' ~ rule["field"]) }}
{% if not loop.last %}union all{% endif %}
{% endfor %}
```

A new rule of an existing kind is now a seed row. A new kind of check is a new
branch in `dq_check`, written once. The range check does not flag nulls, because
both comparisons are null; a field that must be present needs its own `not_null`
rule. When an entity type has no rules yet, the loop produces no SQL, so give
the model a fallback `select` that returns no rows, with the same columns.

Fill in the message at query time, by joining the failures to `dq_rules` on
`rule_id` and replacing `{key}` and `{value}` in the template with `replace()`.
The template stays in the seed, where it can be reworded without touching code.

Per-segment rules (the `segment` column filled) are applied by adding
`and l.segment = '...'` to that rule's `where`, so the same seed covers global and
segment-specific rules.

## Valid rows and the hierarchy

`int_order_lines__valid` keeps a staged line when it has no failure with
`severity = 'reject'` and its order is valid. "Its order is valid" means the
order passed validation in this batch, or the order was not in this batch at all
and is already published. An order that is in this batch and failed takes its
lines with it, even if an older version of it stays published.

## The quarantine table

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['segment', 'entity_type', 'entity_key', 'rule_id', 'field']
) }}
```

Every column in `unique_key` must be non-null. A merge compares keys with `=`,
null never equals null, and a row with a null `field` is inserted again on every
run. Write an empty string for rules that have no single field.

On an incremental run, the model selects three kinds of rows, and only these:

- **Failing now, already in the table:** keep `first_seen_*`, set `last_seen_*` to
  this batch, and add one to `occurrences` only if `last_seen_batch` was a
  different batch. That makes rerunning the same batch change nothing. A row that
  was resolved and fails again is set back to `open`.
- **Failing now, not in the table:** insert with `occurrences = 1`.
- **Open in the table, its record is in this batch, and it no longer fails:** set
  `status = 'resolved'` with this batch as `resolved_batch`. Records that are not
  in this batch are not selected at all, so the merge leaves their open rows
  untouched; a record that was not sent has not been fixed.

Join the existing rows from `{{ this }}` to `int_dq__failures` with a full outer
join on the five key columns, and to the set of keys present in the batch for the
third case.

## Published snapshots and the comparison

Keep published state with a dbt snapshot of the published model. Its current rows
are those with `dbt_valid_to is null`. Configure how the snapshot treats records
that are missing from the source to match the project's deletion rule
(`hard_deletes` in dbt 1.9 and later).

The comparison model joins the validated rows of the batch to the current
snapshot rows **of the segments that delivered in this batch**. Joining to the
whole snapshot reports every segment that did not deliver today as entirely
deleted.

dbt cannot wait for a person, so an approval gate lives in the orchestrator: one
job builds everything up to the validated state and the comparison, and stops; the
publish models are built by a second job, after approval, with `--select`. The
publish mode per segment can be a seed the first job reads to decide whether to
start the second automatically.

## Measures

Keep measure definitions in a seed as well (measure id, entity type, field,
statistic, better direction, target) and generate the computation with a macro,
as for rules. Materialise the results incrementally, keyed by measure, segment,
stage and batch, so each batch adds a point to the trend instead of replacing the
last one.
