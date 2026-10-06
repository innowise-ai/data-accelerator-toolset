# Skill catalog

Human-readable index of every artifact in this catalog, generated from
[`index.json`](../index.json) (`toolset_ref: refs/tags/v0.6.3`, schema version 2).
Regenerate this file whenever artifacts are added, removed or re-described in
the index — it is a rendering of `index.json`, not a second source of truth.

38 artifacts today: 23 data-engineering specific (dbt, Snowflake, Airflow,
Python pipeline code, sensitive data handling, stack-agnostic pipeline quality),
4 for containers and local environments, and 11 general skills that apply to any
stack. All are `on-demand` except `DOCKER-DESTRUCTIVE-GUARDRAILS`, which is
`always`: it installs into every project that uses Docker, because losing a data
volume is not something a team should have to remember to ask protection against.
An `on-demand` artifact is used when the task calls for it, rather than always
loading it. `Applies to` shows the `applies_to` restriction from the index; "any"
means the artifact carries no language/framework restriction. `Scope` is `project`
unless noted — a `project`-scope artifact is selected by what the project is;
`user`-scope reflects a personal preference instead.

An artifact is only installed into a project if `accelerator-setup`'s
questionnaire and scan match it — this list is the full menu, not what any
one project gets.

## Data engineering (23)

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
| **Sensitive data handling** (`SENSITIVE-DATA-HANDLING`) | any | security | Decides what personal data a model may carry, and keeps deletion possible later. |
| **SCD Type 2 implementation** (`SCD2-IMPLEMENTATION`) | sql | data-modeling | Implements Slowly Changing Dimension Type 2 in SQL with correct validity intervals. |
| **Snowflake cost hunting** (`SNOWFLAKE-EXPENSIVE-QUERIES`) | snowflake | performance | Finds the Snowflake queries actually worth optimising and reads the metrics that point at a fix. |
| **Snowflake grants after recreation** (`SNOWFLAKE-GRANTS-AFTER-RECREATE`) | snowflake | data-quality | Restores access after Snowflake objects are recreated, without guessing at roles. |
| **Snowflake query diagnosis** (`SNOWFLAKE-QUERY-BY-ID`) | snowflake | performance, debugging | Diagnoses one Snowflake query from its profile and operator statistics. |
| **Snowflake query rewriting** (`SNOWFLAKE-QUERY-TEXT`) | snowflake | performance, refactoring | Rewrites a Snowflake query for performance without changing its results. |
| **Snowflake semantic view drift** (`SNOWFLAKE-SEMANTIC-VIEW-DRIFT`) | snowflake | data-modeling, data-quality | Finds where a semantic view no longer matches its tables and repairs it without losing hand-written descriptions. |

## Containers and local environment (4)

| Skill | Applies to | Topic(s) | What it does |
|---|---|---|---|
| **Docker build strategies** (`DOCKER-BUILD-STRATEGIES`) | docker | containerization | Builds Python data images that keep credentials out of layers, cache well and run as non-root. |
| **Docker Compose patterns** (`DOCKER-COMPOSE-PATTERNS`) | docker | containerization | Wires local data stacks in Compose so services wait for a database to be ready, not merely started. |
| **Docker destructive-command guardrails** (`DOCKER-DESTRUCTIVE-GUARDRAILS`) | docker | — (`always`) | Stops Docker cleanup commands from deleting data until the loss has been stated and confirmed. |
| **Docker project foundations** (`DOCKER-PROJECT-FOUNDATIONS`) | python | containerization | Adds a first working Docker setup to a Python data project, with its dependencies as Compose services. |

## General skills (11)

| Skill | Applies to | Topic(s) | What it does |
|---|---|---|---|
| **Change review** (`CHANGE-REVIEW`) | any | code-review | Reviews a code change for correctness, risk, test coverage and backward compatibility. |
| **Error diagnosis** (`ERROR-DIAGNOSIS`) | any | debugging | Finds the cause of a failure by narrowing it down and proving it before changing code. |
| **Implementation planning** (`IMPLEMENTATION-PLANNING`) | any | development-process | Turns agreed requirements into an ordered plan with verifiable steps. |
| **Plan execution** (`PLAN-EXECUTION`) | any | development-process | Works through an agreed plan one step at a time and handles it when reality diverges. |
| **Project adaptation** (`PROJECT-ADAPTATION`) | any | development-process, documentation | Adapts installed toolset skills by adding repository paths, commands, conventions and examples inside each installed SKILL.md. |
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
