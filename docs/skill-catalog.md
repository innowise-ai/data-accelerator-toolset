# Skill catalog

Human-readable index of every artifact in this catalog, generated from
[`index.json`](../index.json) (`toolset_ref: refs/tags/v0.6.3`, schema version 2).
Regenerate this file whenever artifacts are added, removed or re-described in
the index — it is a rendering of `index.json`, not a second source of truth.

30 artifacts today: 20 data-engineering specific (dbt, Snowflake, Airflow,
Python pipeline code, stack-agnostic pipeline quality) and 10 general skills
that apply to any stack. All are `on-demand` — an agent uses one when the task
calls for it, rather than always loading it. `Applies to` shows the
`applies_to` restriction from the index; "any" means the artifact carries no
language/framework restriction. `Scope` is `project` unless noted — a
`project`-scope artifact is selected by what the project is; `user`-scope
reflects a personal preference instead.

An artifact is only installed into a project if `accelerator-setup`'s
questionnaire and scan match it — this list is the full menu, not what any
one project gets.

## Data engineering (20)

| Skill | Applies to | Topic(s) | What it does |
|---|---|---|---|
| **Airflow DAG conventions** (`AIRFLOW-DAG-CONVENTIONS`) | airflow | orchestration | Structures Airflow DAGs so nothing expensive or fragile runs at import time. |
| **dbt column lineage** (`DBT-COLUMN-LINEAGE`) | dbt | data-modeling | Traces where a dbt model's column came from and what depends on it, without reading SQL by hand across the model chain. Requires dbt Cloud + MCP server. |
| **dbt error debugging** (`DBT-ERROR-DEBUGGING`) | dbt | debugging | Diagnoses a failing dbt build from the compiled SQL rather than the error text. |
| **dbt incremental models** (`DBT-INCREMENTAL-MODELS`) | dbt | data-modeling, performance | Chooses an incremental strategy and unique key that survive late data and schema drift. |
| **dbt model creation** (`DBT-MODEL-CREATION`) | dbt | data-modeling | Runs the build-and-verify loop for a new dbt model instead of stopping at compile. |
| **dbt model documentation** (`DBT-MODEL-DOCUMENTATION`) | dbt | documentation | Writes model and column descriptions that state what the SQL cannot. |
| **dbt model refactoring** (`DBT-MODEL-REFACTORING`) | dbt | refactoring | Restructures a dbt model while proving its output did not change. |
| **dbt model testing** (`DBT-MODEL-TESTING`) | dbt | testing, data-quality | Picks dbt schema tests that catch real defects for each column role. |
| **dbt project conventions** (`DBT-PROJECT-CONVENTIONS`) | dbt | data-modeling, data-quality | Establishes what belongs in each dbt layer and why the boundaries hold. |
| **Legacy SQL to dbt** (`DBT-SQL-MIGRATION`) | dbt | refactoring, data-modeling | Ports legacy SQL into dbt layer by layer and reconciles against the original. |
| **Data incident investigation** (`DATA-INCIDENT-DEBUGGING`) | any | debugging, data-quality | Traces wrong data back to the code that produced it when the pipeline reported success. |
| **ETL decomposition** (`ETL-DECOMPOSITION`) | python | refactoring, orchestration | Splits a monolithic extract-transform-load function into testable units with I/O at the edges. |
| **Pipeline output review** (`PIPELINE-OUTPUT-REVIEW`) | any | code-review, data-quality | Reviews the data a pipeline run actually produced, not just whether tests passed. |
| **Pipeline regression gates** (`PIPELINE-REGRESSION-GATES`) | any | testing, data-quality | Selects the cheapest checks that would actually catch the regression a change can cause. |
| **pytest for data pipelines** (`PYTEST-DATA-PIPELINES`) | python | testing | Tests data pipeline code with pytest, mocking at the I/O boundary. |
| **Safe NL2SQL guardrails** (`SAFE-NL2SQL-GUARDRAILS`) | sql | data-quality | Generates SQL from natural language without letting an unvalidated query reach the database. |
| **SCD Type 2 implementation** (`SCD2-IMPLEMENTATION`) | sql | data-modeling | Implements Slowly Changing Dimension Type 2 in SQL with correct validity intervals. |
| **Snowflake cost hunting** (`SNOWFLAKE-EXPENSIVE-QUERIES`) | snowflake | performance | Finds the Snowflake queries actually worth optimising and reads the metrics that point at a fix. |
| **Snowflake query diagnosis** (`SNOWFLAKE-QUERY-BY-ID`) | snowflake | performance, debugging | Diagnoses one Snowflake query from its profile and operator statistics. |
| **Snowflake query rewriting** (`SNOWFLAKE-QUERY-TEXT`) | snowflake | performance, refactoring | Rewrites a Snowflake query for performance without changing its results. |

## General skills (10)

| Skill | Applies to | Topic(s) | What it does |
|---|---|---|---|
| **Change review** (`CHANGE-REVIEW`) | any | code-review | Reviews a code change for correctness, risk, test coverage and backward compatibility. |
| **Error diagnosis** (`ERROR-DIAGNOSIS`) | any | debugging | Finds the cause of a failure by narrowing it down and proving it before changing code. |
| **Implementation planning** (`IMPLEMENTATION-PLANNING`) | any | development-process | Turns agreed requirements into an ordered plan with verifiable steps. |
| **Plan execution** (`PLAN-EXECUTION`) | any | development-process | Works through an agreed plan one step at a time and handles it when reality diverges. |
| **Project documentation** (`PROJECT-DOCUMENTATION`) | any | documentation | Documents architecture decisions, component boundaries and constraints a reader cannot infer from the code. |
| **Refactoring safety** (`REFACTORING-SAFETY`) | any | refactoring | Plans and sequences a refactor so behaviour is provably unchanged at every step. |
| **Requirements brainstorming** (`REQUIREMENTS-BRAINSTORMING`) | any | development-process | Works out what is actually needed before any code is written. |
| **Technical writing** (`TECHNICAL-WRITING`) | any | writing | Improves technical prose without changing its meaning or terminology. Scope: `user` (personal preference, not project-selected). |
| **Test design and review** (`TEST-DESIGN-REVIEW`) | any | testing | Decides what is worth testing and judges whether existing tests would catch a defect. |
| **Work verification** (`WORK-VERIFICATION`) | any | development-process | Checks that work actually does what was asked before it is reported as finished. |

## How a project gets a subset of these

See the [installer README](https://github.com/innowise-ai/data-accelerator-installation#how-it-works):
`accelerator-setup` scans the project, asks what the scan can't detect, and
writes a profile; `accelerator install` reads that profile and installs only
the artifacts that match — nothing here is installed wholesale.
