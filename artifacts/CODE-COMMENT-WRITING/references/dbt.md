# Comments in a dbt project

dbt gives a model two places for text, and they have different readers. The
descriptions in its properties file (`schema.yml`) are published: `dbt docs` shows
them, and with `persist_docs` they are written into the warehouse as table and column
comments, where analysts read them. Comments in the `.sql` file are for whoever edits
the model. The rules in SKILL.md hold; this file covers where dbt moves the line
between the two.

## The model header and `schema.yml`

| Fact | Place in dbt |
|---|---|
| What the model is, its grain, what each column means, business rules a consumer needs | `schema.yml`, as [dbt-model-descriptions](../../DBT-MODEL-DESCRIPTIONS/SKILL.md) describes |
| A check, a non-obvious predicate, engine behaviour the SQL relies on | A SQL comment at the code, as in SKILL.md |
| How to read the SQL itself, when its structure is not obvious (why a CTE deduplicates before the join rather than after) | A short header comment in the `.sql` file |
| Columns a macro generates | The macro's description, **and** every model's `schema.yml` entry, sharing one `{% docs %}` block |

Where SKILL.md puts a table's column list in the model header, dbt puts it in
`schema.yml`. Do not keep a second list in the header. Two lists drift, and the one
in `schema.yml` is the one consumers see, so it is the one that has to be right.

Keep the header comment to what someone editing the SQL needs and `schema.yml` cannot
say. If the header starts restating the model description, delete the restatement:
the next person to change the grain will update one of the two, not both.

## `--` comments and `{# #}` comments

dbt renders Jinja before any SQL runs, and a `--` comment is SQL. Jinja inside it is
still rendered:

```sql
-- {{ ref('orders_v1') }}
```

That line, left behind as a note, still makes `orders_v1` a parent of the model in the
DAG, and removing `orders_v1` then breaks this model. A `run_query` call inside a `--`
comment still runs its query. Comment out Jinja with `{# #}`, which dbt removes before
rendering.

The two kinds also end up in different places. `{# #}` comments are gone from the
compiled SQL. `--` comments stay in `target/compiled` and `target/run`, and travel to
the warehouse with the query, where they appear in query history. So a note about the
Jinja itself (why a loop builds these columns, what a macro argument controls) goes
in `{# #}`. A note about the SQL that someone reading the compiled query or the query
history needs goes in `--`.

## Macros

A macro is a helper. A macro file that defines several macros opens with a `{# #}`
list of them, one short line each, and each check inside a macro gets its comment
directly above it, like any other check:

```sql
{#
  scd2_validity(relation, key, changed_at): adds validity columns to a change feed.
  The relation must have a _loaded_at column.
#}
{% macro scd2_validity(relation, key, changed_at) %}
with deduped as (
    select *
    from {{ relation }}
    -- One row per key and changed_at, keeping the latest load. Example: the source
    -- re-sends a change with the same changed_at; without this, the key gets a
    -- version that ends at the moment it starts, and which of the two copies
    -- becomes the real version depends on how the database orders ties.
    qualify row_number() over (
        partition by {{ key }}, {{ changed_at }}
        order by _loaded_at desc
    ) = 1
)

select
    *,
    {{ changed_at }} as valid_from,
    lead({{ changed_at }}) over (partition by {{ key }} order by {{ changed_at }}) as valid_to,
    lead({{ changed_at }}) over (partition by {{ key }} order by {{ changed_at }}) is null as is_current
from deduped
{% endmacro %}
```

The failure case there was traced against the code. Two rows share a key and a
`changed_at`, so `lead()` sees a tie. The row it orders first gets the other row's
`changed_at` as its `valid_to`, which equals its own `valid_from`. Which row is
ordered first is not defined.

The macro's description, and the descriptions of the columns it adds, go in the
macro properties file, where `dbt docs` publishes them:

```yaml
macros:
  - name: scd2_validity
    description: Adds valid_from, valid_to and is_current to a change feed.
    arguments:
      - name: relation
        type: relation
        description: The change feed. Must have a _loaded_at column.
      - name: key
        type: string
        description: Column that identifies one entity across its versions.
      - name: changed_at
        type: string
        description: Column holding the time the version took effect.
```

Each model that calls the macro lists the columns it adds in its own `schema.yml`
entry, because that is where a reader of the model looks. Define each description
once, in a `{% docs %}` block in a `.md` file under `models/`, and reference it from
every model, so the copies cannot drift:

```markdown
{% docs scd2_valid_to %}
changed_at of the next version of the same key; null for the current version.
{% enddocs %}
```

```yaml
models:
  - name: dim_customer_history
    description: One row per customer per version.
    columns:
      - name: valid_to
        description: "{{ doc('scd2_valid_to') }}"
```

When the macro's output changes, the docs block changes with it, and every model
picks up the new text.

## Hooks and `config()`

`pre_hook` and `post_hook` are SQL strings that dbt runs as written. Put the reason
for a hook in a `{# #}` comment above the `config()` call, not inside the hook string.
A `--` inside a one-line hook string comments out everything after it on that line,
including SQL someone adds there later.

## Tests

A singular test in `tests/` is a check. Its comment, at the top of the file, says
what the test asserts and gives one failure case, like any other check. A generic
test in `schema.yml` whose purpose is not obvious from its name can carry its failure
case in a YAML `#` comment beside it. YAML comments are not published, so this is
text for maintainers, not for consumers.
