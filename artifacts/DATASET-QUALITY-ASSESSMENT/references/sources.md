# What was read

Classify the source before any column check. The class decides what a count
means. A null rate on a SharePoint view is the view's rate, not the list's. A
duplicate count on a fact after a bidirectional relationship has multiplied
rows is the relationship's grain, not the fact's. The column rules in
[the skill](../SKILL.md) apply after classification. Only the way you reach
the rows changes.

This is one reference for five classes, not one skill per engine. A CSV on
disk and a published model are the same judgement. The dialect is named only
where the function actually differs.

## When the source cannot be read

Stop. Ask for the smallest substitute that still supports the claim: column
names and types, the row count, a sample, the stated grain, and any declared
relationships. A rate needs the rows or the aggregates that were computed. A
grain needs whoever stated it. Do not invent a schema to fill the gap. A
plausible column list reads exactly like the real one, and every later chart
inherits it.

Do not ask the user to paste secrets or connection strings. A connection
string is not a dataset, and a pasted one is a secret in the transcript.

## What every class records

The class, the object name, the grain, whether the profile is the population
or a sample, and what you could not see. The EDA report and the dashboard
draft inherit this block unchanged. A dashboard draft that proposes a visual
at a grain the source class cannot support is wrong even if the chart type is
sensible.

## 1. Flat file

A csv, tsv, xlsx, parquet, json, jsonl, or a local extract.

Profile the file you were given and say so. An Excel workbook is one sheet at
a time; name the sheet. Three sheets are three datasets until someone says
they are one, and a rate computed across sheets the user did not name is a
dataset you assembled.

Merged cells, a title row above the header, and numbers stored as text are
data findings, not cleaning steps you silently apply. Skipping a title row
without saying so changes which row is the header, and the column names in
the report are then yours. Numbers stored as text will not min and max as
numbers. Report the type you saw, and leave the coercion as a finding.

There are no declared relationships. Any join you use is inferred, and it
stays inferred. A file may be a filtered export. Coverage is the file, not
the system it was exported from. A row count of the file is not a row count
of that system.

## 2. Queryable table or view

BigQuery, Azure SQL, SQL Server, Synapse, Fabric, Snowflake, Databricks SQL,
and anything else you can aggregate with SQL. One class.

Profile with aggregates: counts, null counts, approximate distinct counts,
min, max, quantiles. Do not pull the table into the chat. The chat is not a
warehouse, and a pasted extract is a sample that the next reader will treat
as the population.

A view is profiled as published. Filters and joins inside the view are
already applied. Say you did not see the base tables unless the SQL was
provided. A null in a view can be a null in the table or a join that did not
match, and the view alone cannot tell those apart.

Read-only. No DDL. No temp tables unless the user asked and the role is
allowed to create them. A profile that creates an object has left the
assessment and started a pipeline.

A sample answers "this shape exists". It does not answer a rate for the
population. If you report a rate from a sample, say it is the sample's rate.
State when a full scan is the only way to answer, such as an exact distinct
on a wide fact or a quantile the engine cannot approximate, and prefer a
sample when the user has not agreed to the scan. An approximate distinct can show a
column is nowhere near a key. It cannot clear one. The exact comparison stays
insufficient evidence until the scan is agreed.

Blank and whitespace-only are not null, so a null count understates missingness.
Name the trim you used. The engines do not spell it the same way, and the
predicate is part of the evidence.

Name the dialect only for the two functions that differ, and write the
function you ran next to the number:

| Dialect | Approximate distinct | Quantile |
|---|---|---|
| BigQuery | `APPROX_COUNT_DISTINCT` | `APPROX_QUANTILES` |
| Snowflake | `APPROX_COUNT_DISTINCT` | `APPROX_PERCENTILE` |
| SQL Server, Azure SQL, Synapse, a Fabric warehouse or lakehouse SQL endpoint | `APPROX_COUNT_DISTINCT` | `PERCENTILE_CONT`, which is exact, so it sorts |
| Databricks SQL, Spark SQL | `approx_count_distinct` | `percentile_approx` |

Anything else: use that engine's approximate distinct and its quantile, and
name them. Where the engine has no approximate quantile, an exact percentile
is a full sort. Say so, and run it on a sample the user has agreed to rather
than on the population by default.

## 3. SharePoint

A list, or a file in a library.

A list is not a table. Choice, person, lookup, and yes/no columns have
SharePoint types. Report the type you actually saw. A person column flattened
to a display name has lost the account. A choice column read as free text has
lost the allowed set, and a new value then looks like ordinary text rather
than a value the list does not offer.

A lookup is a declared relationship you may not be allowed to expand. If you
cannot expand it, the column is an id, not the target entity. Do not invent
the target's attributes from the lookup's name. The name is a label. The id
is what you have.

A list view is not the list. The view can be filtered and it can be capped.
Say which you profiled. A rate on a capped view is the first page of the
list, and it will not match the list. Treating the page as the population is
how a threshold becomes a quiet filter.

A file in a library, once you have the file, is class 1, plus which file and
which version is current if several share a name. Two files with the same
name are not the same extract. Name the one you opened.

## 4. Published Power BI semantic model

The model is the dataset. Do not flatten it and profile every column as one
table. Grain is the fact table plus its relationships. A duplicate check on a
dimension key is a different claim from a duplicate check on a fact after a
bidirectional relationship has multiplied rows. The second count is the
relationship. "Fixing" it by deleting fact rows deletes the children the
relationship was showing.

Measures are the metrics. A column with the same name is not the measure. The
measure can filter, and the column will not. Summing the column and calling
it the measure is how a dashboard draft invents a definition the model
already has. Filter direction and cardinality are part of the evidence. A
both-direction filter or a many-to-many will fan a count out, and a visual
that sums a column will follow that fan-out.

Profile through the model: a measure, a DAX query the user runs, or an extract
of the model definition they already have. The question for that query is a
count, a null count, a distinct count, at the grain of one table, not a
flattened export of the model. Knowledge about grain and relationships
belongs here. A click-path through Desktop, and a client for the REST API or
XMLA, do not.

If you only have the report and not the model, say the report is not the
dataset. The report is a view of the model with its own filters. Profiling
what a page shows is not profiling the table.

You will often lack row-level security, incremental-refresh partitions, and
report-level filters. Mark those unseen rather than guessing. A row count
taken as a role the reader is not in is a different population. An incremental
model may hold partitions you were not shown, and a count of the partitions
you saw is not a count of the model.

## 5. Published Tableau data source

A published data source, an extract, or a packaged data source the user can
describe.

Relationships, physical joins, and blends are different grains. Name which
one the dataset uses. A relationship keeps each table at its own grain and
aggregates before combining, so a row count of one table is not a row count
of the relationship. A physical join materialises one row grain, and a
fan-out there is already in the row you profile. A blend is not a join. It
queries each source separately and combines aggregates. Treating a blend as a
join invents a row the data source never built, and a duplicate check on that
invented row is a check of nothing.

An extract has a refresh time. A live connection does not, and the profile is
only as fresh as the moment it was taken. Write that moment down. Tomorrow's
live query is not this profile.

A field caption is not the warehouse column name. Keep both when you have
them. A caption can be renamed without the column changing, and a later
dashboard that cites only the caption cannot be traced back to the field the
rate was computed on.

An aggregated field or a level-of-detail calculation is already at a grain.
Do not treat it as a row-level column. A null rate on an aggregate is not the
null rate of the column underneath it, and a level-of-detail expression has
already chosen a grain. Profiling it as a row answers a question at the wrong
grain. Do not write a new level-of-detail expression to profile with. Ask the
user to run one only if they ask for the expression.

If you cannot read the data source, the substitute is the field list, the
relationship or join description, extract versus live, and a sample crosstab.
The crosstab is a sample. Say so, and do not promote it to the population.
Do not ask for a session against the Tableau REST API. The field list and the
crosstab are the substitute that still supports the claim.
