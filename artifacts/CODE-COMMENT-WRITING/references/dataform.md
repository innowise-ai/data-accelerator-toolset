# Comments in a Dataform project

A Dataform model is a `.sqlx` file: a `config` block, optional `pre_operations` and
`post_operations` blocks, and the SQL. Shared JavaScript helpers live in `includes/`.
The rules in SKILL.md hold; this file covers the places where Dataform and BigQuery
change them.

## `config.description` is BigQuery metadata

Dataform writes `config.description` to the BigQuery table as its description, where
anyone browsing the dataset reads it. Keep it to one paragraph on what the table
holds. The details for whoever edits the model go in the header comment.

Column descriptions in `config.columns` are published the same way. If the project
documents columns there, that is where a model's column list goes, and the header
does not repeat it. If the project documents columns in the header, follow that.

## The model header

The header comment sits at the top of the `.sqlx` file, in this order:

1. What the table is, in one line.
2. Its columns, one row each: the name, then its source or meaning, aligned.
3. How to read it: the grain, and anything about the structure a reader needs before
   the SQL makes sense.
4. Rules that apply to one source or entity.

Columns built by a helper in `includes/` appear in this list too, as SKILL.md
describes, even though the helper documents them as well.

## Comments in `pre_operations`

On an incremental table, `pre_operations` often holds a statement that only runs on
incremental builds, wrapped in `${when(incremental(), ...)}`. On the first build the
`when()` renders nothing. A SQL comment placed in the block outside the `when()` is
then the only thing left in it, and that empty statement breaks the first build.

Put a comment about the statement inside the `when()` template, with the statement.
Put a note about the block as a whole above `pre_operations {`.

## JavaScript helpers in `includes/`

A helper file is a helper module. It opens with a list of the functions it exports,
one short line each, and each function documents what it returns, including every
column it generates. Each check in a helper gets its comment directly above it, with
one failure case, as in SKILL.md. Every model that uses a column-generating helper
lists those columns in its own header.
