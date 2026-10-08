---
name: code-comment-writing
description: Writing and maintaining code comments, file headers and docstrings - deciding where each fact goes (above the check, in the file header, in a helper and every file that uses it, or in project docs), giving each check one failure case that is true of the code, leaving out pointers, history and restated code, and keeping comments true when the code changes. Use when writing, editing or reviewing comments in SQL, Python, JavaScript or other code, and when changing code that has comments on or around it.
---

# Writing code comments

A comment is for the next person who opens this file to change it. It says what the
code does and why, at the place where it does it. It is not a changelog, a design
discussion, or a pointer to somewhere else. Each of those has a better home, and in a
comment each one either goes stale or sends the reader away from the code they are
trying to understand.

Comments decay faster than any other documentation, because nothing runs them. A wrong
comment sits directly above the code it contradicts and is read before that code, so
it is trusted at the worst possible moment. Most of what follows is about writing
fewer comments, in the right place, that stay true.

This skill decides what a comment contains and where it goes. Its neighbours:

- Design reasons, rejected options, history and runbooks belong in project
  documentation: [project-documentation](../PROJECT-DOCUMENTATION/SKILL.md).
- In a dbt project, model and column descriptions belong in `schema.yml`:
  [dbt-model-descriptions](../DBT-MODEL-DESCRIPTIONS/SKILL.md).
- Tightening the wording of a comment whose content is already right is prose
  editing: [technical-prose-editing](../TECHNICAL-PROSE-EDITING/SKILL.md).
- Reviewing a whole change is [code-change-review](../CODE-CHANGE-REVIEW/SKILL.md).
  A comment the change made false is one of its findings; this skill says what the
  comment should say instead.

Two stacks move some of the lines drawn below. On a dbt project (`dbt_project.yml`),
read [references/dbt.md](references/dbt.md). On a Dataform project
(`workflow_settings.yaml` or `dataform.json`, `.sqlx` files under `definitions/`),
read [references/dataform.md](references/dataform.md).

These rules decide content and placement, not format. Match the project's existing
header layout and docstring convention before introducing your own.

## Where each fact goes

| Fact | Place |
|---|---|
| A check: a guard, validation or assertion | Directly above the code that implements it, in whichever file that is: the model, the module or the helper |
| What the check protects against | In that same comment, as one concrete failure case |
| A protective condition inside a statement (a `WHERE` or `JOIN` predicate, an `if` that skips a record), when it is hard to understand | One short line above the statement saying what the condition ensures, with no example. Most conditions need no comment at all |
| A group of non-obvious columns or expressions | One line where the group starts, not one per column |
| Engine or library behaviour the code relies on | One line, at the expression |
| A table's columns, when the project documents them in code | That model's header comment. Not every model needs a column list, and where the project keeps columns in metadata (dbt `schema.yml`, Dataform `columns`) they go there instead. If it is unclear whether a list is wanted, ask |
| Columns a helper generates | In the helper's doc, **and** wherever each model that uses the helper lists its columns, so the schema is findable from the model |
| A rule that applies to one source, customer or entity | Once, in the file where the rule takes effect |
| Something no check catches but that may matter later | A very short note in the header of the file that holds the checks, or in the project's docs if they exist |
| Design reasons, rejected options, measurements, the history of the work, test runbooks | Project docs, not code |

**A check's comment sits on the check** because that is the only place it moves with
the code. A note at the top of the file about a check fifty lines below survives the
check's deletion; a comment directly above the check is deleted in the same edit. It
also answers the question a maintainer has when they look at a check: what breaks if
I remove this?

**Columns a helper generates are written down twice, on purpose.** Duplication is
usually how comments drift, and this is the one place to accept it.
Someone reading a model wants that model's schema. They may not know the helper
exists, and will not open it to find out. The helper's doc serves whoever maintains
the helper; the model's list serves whoever reads the model. The cost is that both
copies change in the same commit whenever the helper's output changes.

**Design reasons go to docs** because they are an argument, and an argument outgrows a
comment. It needs the alternatives and the measurements to be checkable, and it stays
relevant after the code it justified has been rewritten. Keep the reason in the code
and move the argument out. "Joins on the hashed key: the composite key join timed out
at production volume" is a reason, and it fits on one line. The benchmark table and
the three options that were tried are the argument.

A file with several checks or functions, such as a helper module, a macro file or a
validation library, opens with a list of them, one very short line each. The list is a
table of contents. The details go at each implementation, so the list has nothing
that can drift except names.

## What a comment on a check says

Name the condition, then the failure it prevents as a concrete scenario. The scenario
is what makes the check reviewable: a reader can test it against the code, and a
maintainer who wants to delete the check sees exactly what they would bring back.

Make the scenario concrete enough to trace (two loads in the wrong order, a re-sent
row, a sender adding a column) without the identifiers or counts of one particular
incident. An order id or last Tuesday's row count means nothing to the next reader
and looks like something they should search for.

A guard on a dbt incremental model:

```sql
{{ config(materialized='incremental') }}

select order_id, status, loaded_at
from {{ ref('stg_orders') }}

{% if is_incremental() %}
-- Only rows loaded after the newest row already in this table. Example: without
-- it, every run appends the whole of stg_orders again, and each order gains one
-- more copy per run.
where loaded_at > (select max(loaded_at) from {{ this }})
{% endif %}
```

A check in a Python loader:

```python
EXPECTED_HEADER = ["order_id", "sku", "quantity", "unit_price"]


def read_order_lines(path):
    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        # The header must equal EXPECTED_HEADER, in order, because rows are read by
        # position. Example: the sender swaps quantity and unit_price; both columns
        # still parse as Decimal, so every line would load with its price as its
        # quantity and its quantity as its price.
        if header != EXPECTED_HEADER:
            raise ValueError(f"{path}: unexpected header {header}")
        for row in reader:
            yield row[0], row[1], Decimal(row[2]), Decimal(row[3])
```

### The example must be true of the code

Before writing a failure case, trace it. Remove the check in your head and follow the
code to the failure. Does it really get there?

In the dbt model above it does, because the config has no `unique_key`, so each run
inserts every row it selects. Add `unique_key='order_id'` and the same comment becomes
false. The model now merges on `order_id`, so re-selecting old rows updates them and
creates no copies. The filter still matters, but for a different reason, and the
comment has to say that one:

```sql
-- Only rows loaded after the newest row already in this table, so each run merges
-- the new rows rather than the whole of stg_orders.
```

In the Python loader, the claim holds because both columns go through `Decimal`, which
accepts either value. Had `quantity` gone through `int()`, a swapped file would fail at
the first price with a fractional part, and only a file whose prices are all whole
numbers would load swapped. The comment would then have to say exactly that.

If only part of a claim holds, narrow the example rather than overstate it. An
overstated failure case is worse than none. The reader trusts it, and either keeps a
check that does less than it claims, or finds the claim false and removes the check
in confidence, along with the protection it really did give.

### Conditions, groups and engine behaviour

A protective condition gets one line saying what it ensures, and only when a reader
would otherwise stop and wonder:

```sql
-- Current address only, so each order joins to at most one address row.
left join customer_addresses a
    on a.customer_id = o.customer_id
   and a.valid_to is null
```

A run of related columns gets one line where the run starts:

```sql
    -- _source_file, _loaded_at and _row_hash: load metadata, not business data.
    _source_file,
    _loaded_at,
    _row_hash
```

Behaviour the code depends on but does not show gets one line at the expression:

```python
# sorted() is stable, so records with equal timestamps keep their file order.
records = sorted(records, key=lambda r: r["changed_at"])
```

### Helpers and the files that use them

A helper module opens with its list, and each function documents the columns it adds:

```python
"""Load helpers shared by the ingestion jobs.

with_load_metadata   adds load columns to every record
reject_duplicates    fails a batch that repeats a primary key
"""


def with_load_metadata(records, source_file, loaded_at):
    """Return the records with three columns added:

    _source_file   name of the file the record came from
    _loaded_at     UTC time of the load, the same for every record in the batch
    _row_hash      SHA-256 of the record's fields before these columns were added
    """
```

Every job that calls it repeats those columns where it lists its own, because that is
where a reader of the job looks:

```python
"""Loads the daily orders file into raw.orders.

Columns: order_id, sku, quantity and unit_price from the file, then from
with_load_metadata:
    _source_file   name of the file the record came from
    _loaded_at     UTC time of the load
    _row_hash      SHA-256 of the record's fields before these columns were added
"""
```

## What stays out of the code

**Pointers.** "See X for details", "(see orders.sql)", "§2.5", line numbers. A pointer
makes the reader leave the code to find out whether the fact even matters, and it
breaks without anyone noticing when the target moves: line numbers shift with the
next edit, sections are renumbered, files are renamed. If the reader needs the fact
here, write it here in one line. If they do not, leave it out.

**Restating at length what is documented elsewhere.** One line of what, at most. Two
full copies drift apart, and the reader cannot tell which one is current. The
helper-generated columns above are the one deliberate exception.

**A migration diary.** "Was", "used to", "the first version", "moved from", the story
of a ticket. A comment describes the code as it is. Nobody can act on what it used to
be, and the history already lives in version control with its date and author
attached. Migration decisions go in the project docs.

**Restating the code.** `-- set valid_to to the next changed_at`, above the line that
does exactly that. It says nothing a reader of the line did not already know, and it
adds a second thing to keep in sync with the code.

**Rationale essays.** Keep the reason, drop the argument, as above.

**Facts that go stale by design.** Branch names, run dates, row counts, "currently
three senders". They are true on the day they are written, and nothing tells anyone
when they stop being true.

## Length and wording

Keep it short. More than three or four lines above one statement means the rest
belongs in docs.

Write in plain words, in the present tense, about the code as it is now.

Be precise about operators and edge cases. In the incremental model above,
`loaded_at > max(loaded_at)` reads as "new rows", but it means "rows loaded strictly
after the newest one already here". A row that arrives late with the same `loaded_at`
as the previous run's newest row is skipped. If that can happen in this pipeline, the
comment says so, because it is the case the next maintainer will be debugging. In the
same way, a filter `src.version > tgt.version` drops rows that are not newer, which
means older or the same version re-sent, not only "older".

## Keep comments true

When you change code, re-read every comment on and around it, and the file header.
Update or delete what no longer holds. That includes comments you did not write. A
comment your change made false is a defect in your change, whoever wrote the comment.

When you remove a check, remove its description everywhere it appears: the helper's
list, the headers of the files that described it, the project docs. Search for the
check's name and for the failure it described. A list entry for a check that no
longer exists tells the next reader they are protected when they are not.

When a helper's generated columns change, every file that lists them changes in the
same commit.

When the user shortens or rewrites a comment, their wording is the decision. Keep it in
later edits, and use it in sibling files that follow the same pattern, rather than
restoring the longer version.

Before you call the work finished, read the diff once more for its comments alone.
Every check you added or touched should have its comment directly above it, with a
failure case you traced. Nothing should point at another file, section or line. Every
file whose columns a helper builds should list those columns. Nothing in the code
should be an argument that belongs in docs. Every comment you touched should describe
the code after your change, not before it.
