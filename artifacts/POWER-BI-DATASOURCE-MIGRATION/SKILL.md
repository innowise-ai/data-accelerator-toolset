---
name: power-bi-datasource-migration
description: Working out what in a Power BI model will not survive a warehouse connection swap, and proving the report still returns the same numbers afterwards. Use when a semantic model has to point at a new warehouse or a replacement source. Not for redesigning the warehouse it is moving to.
---

# Repointing a model at a new warehouse

The model is the last thing anyone remembers when a warehouse is replaced,
and it is the thing that fails in front of readers. The swap itself is
usually one operation — point Power Query at the new source and let columns
rebind by name — and that operation is what makes this risky, because its
failure mode is partial success. Most columns rebind, the report opens, the
page renders, and some of the numbers are different.

So the work is not the swap. It is knowing beforehand what in this model
will not survive it, and afterwards proving that what did survive still
means the same thing.

**Where this stops.** The question here is what in the model breaks. Whether
the new warehouse is modelled well, whether the tables should be
restructured, and what the pipeline that fills them should look like are out
of scope. If the tables genuinely have to change shape, that is
[dbt-legacy-sql-migration](../DBT-LEGACY-SQL-MIGRATION/SKILL.md), run before
or after this one and not inside it. This skill does not become a Snowflake
modelling exercise on the way across.

Its neighbours:

- [dbt-legacy-sql-migration](../DBT-LEGACY-SQL-MIGRATION/SKILL.md) ports SQL
  into dbt and reconciles it. That is the warehouse side of the same
  programme. Logic lifted out of Power Query belongs there. This artifact
  repoints a model.
- [power-bi-measure-translation](../POWER-BI-MEASURE-TRANSLATION/SKILL.md)
  is where the SQL and the DAX are brought into line. This skill treats DAX
  as stable across the warehouse change and does not rewrite it to suit the
  new engine.
- [power-bi-model-audit](../POWER-BI-MODEL-AUDIT/SKILL.md) produces the
  inventory this migration starts from. Run it first if nobody knows what is
  in the model.
- [power-bi-model-diff](../POWER-BI-MODEL-DIFF/SKILL.md) compares the project
  before and after, which is a cross-check on what the swap changed in the
  files. A file that looks unchanged can still return different numbers,
  which is why the diff is not the proof.

What actually moves between warehouses — folding, types, date tables, native
SQL — is in
[references/what-does-not-survive.md](references/what-does-not-survive.md).

## Inventory before touching anything

Take this while the old connection still answers. Afterwards the baseline is
gone.

- **Every connection**, including sources no visual uses. They will all try
  to rebind. Read them from the project, not from a screenshot of the model
  view.
- **Every Power Query expression**, partition and shared, with the warehouse
  objects it names. A native SQL string is the largest single source of
  breakage, because it carries a dialect and identifiers nothing checks
  until it runs.
- **Whether each step folds**, judged by the SQL the connector sends on the
  old warehouse. Record that SQL. "It folds today" is not "it will fold
  there".
- **Every column the model uses**, with its source name, its type, and which
  measures, calculated columns, and functions depend on it. This is the
  mapping the rebind will be judged against.
- **Date tables**, and whether they are generated in the model or loaded from
  the warehouse. DAX time intelligence assumes a complete date table. The
  DAX will not say that the new table has holes.
- **Roles** whose filters mention columns that are about to rebind. A role
  that still parses and filters the wrong rows is a silent success.

Take the numbers the report shows at a known filter state, below the
headline total: the grain the page actually slices by, and the row count of
each table the swap touches. That is the baseline.

## Rebinding by name is the silent failure

Columns match by name. Three outcomes, and only the first announces itself.

**The column is missing.** The model marks it broken, and everything that
depends on it breaks too, including a function several steps away. Noisy,
and the best case, because you know.

**The name matches and the type changed.** Partly visible. A timestamp
arriving as a string, or a decimal arriving at a different scale, changes
what sorts, what joins, and what a measure returns. The report still opens.

**The name matches and the meaning changed.** Not visible. The type is
fine, the report renders, and the number is a different number. This is the
outcome the baseline exists to catch. Nothing in the project flags it.

DAX is stable across warehouses. A measure does not contain the dialect, and
rewriting measures because the warehouse changed is how a migration invents
new bugs. The parts that are not stable are M, types, date tables, and the
SQL a step folds to. A function moves only because a column it is called
with moved. List those callers so you know what to reconcile. Do not rewrite
the function to "suit Snowflake".

## Prove the report, not the headline

After the swap, reconcile at the grain you recorded, not at the grand total.
Two errors cancel at the total and show up in the slices. Row counts of the
tables that rebound come first: a count that moved means every measure over
that table is unexplained until the missing or extra rows are explained.

Compare the SQL the connector sends now with the SQL you recorded before,
for the steps the report relies on. A step that folded before and does not
fold now will still return rows, and it will return them by pulling a larger
set and filtering locally, which can change both the number and the time.
"It opens" does not mean it folds.

A function or a measure an agent rewrote during the swap is unverified. The
proof is the baseline, not a formula that compiles. If you cannot run the
old and the new at the same filters, say the migration is unproved and stop.
Do not fill the gap with a plausible reason the numbers should match.

## The report pointer is a different swap

`definition.pbir` can point the report at a different semantic model. That
is not a warehouse migration. It has the same silent failure: the report
opens, visual names still resolve, and the numbers belong to another model.
If that is the change in front of you, name the two models and run the same
baseline. Do not treat it as a Power Query problem, and do not follow it
into how the service publishes either model.
