# Skill catalog

Human-readable index of every artifact in this catalog, generated from
[`index.json`](../index.json) (`toolset_ref: refs/tags/v1.0.0`, schema version 2).
Regenerate this file whenever artifacts are added, removed or re-described in
the index — it is a rendering of `index.json`, not a second source of truth.

38 artifacts today: 23 data-engineering specific (dbt, Snowflake, Airflow,
Python pipeline code, sensitive data handling, stack-agnostic pipeline quality),
4 for containers and local environments, and 11 general skills that apply to any
stack. All are `on-demand` except `DOCKER-DATA-LOSS-CONFIRMATION`, which is
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
| **Structure Airflow DAGs for safe, cheap imports** (`AIRFLOW-DAG-STRUCTURE`) | airflow | orchestration | Structures Airflow DAGs so nothing expensive or fragile runs at import time. |
| **Trace wrong data when the pipeline succeeded** (`DATA-INCIDENT-TRACING`) | any | debugging, data-quality | Traces wrong data back to the code that produced it when the pipeline reported success. |
| **Diagnose a failing dbt build from compiled SQL** (`DBT-BUILD-FAILURE-DIAGNOSIS`) | dbt | debugging | Diagnoses a failing dbt build from the compiled SQL rather than the error text. |
| **Trace a dbt column upstream and downstream** (`DBT-COLUMN-LINEAGE`) | dbt | data-modeling | Traces where a dbt model's column came from and what depends on it, without reading SQL by hand across the model chain. Requires dbt Cloud + MCP server. |
| **Choose a dbt incremental strategy and unique key** (`DBT-INCREMENTAL-STRATEGY`) | dbt | data-modeling, performance | Chooses an incremental strategy and unique key that survive late data and schema drift. |
| **Define what belongs in each dbt layer** (`DBT-LAYER-BOUNDARIES`) | dbt | data-modeling, data-quality | Establishes what belongs in each dbt layer and why the boundaries hold. |
| **Port legacy SQL into dbt and reconcile it** (`DBT-LEGACY-SQL-MIGRATION`) | dbt | refactoring, data-modeling | Ports legacy SQL into dbt layer by layer and reconciles against the original. |
| **Build and verify a new dbt model** (`DBT-MODEL-BUILD-VERIFY`) | dbt | data-modeling | Runs the build-and-verify loop for a new dbt model instead of stopping at compile. |
| **Write dbt model and column descriptions** (`DBT-MODEL-DESCRIPTIONS`) | dbt | documentation | Writes model and column descriptions that state what the SQL cannot. |
| **Refactor a dbt model and prove output is unchanged** (`DBT-MODEL-REFACTORING`) | dbt | refactoring | Restructures a dbt model while proving its output did not change. |
| **Pick dbt schema tests for each column role** (`DBT-MODEL-TESTING`) | dbt | testing, data-quality | Picks dbt schema tests that catch real defects for each column role. |
| **Split a monolithic ETL function into testable units** (`ETL-DECOMPOSITION`) | python | refactoring, orchestration | Splits a monolithic extract-transform-load function into testable units with I/O at the edges. |
| **Generate SQL from natural language, validated before it runs** (`NL2SQL-QUERY-VALIDATION`) | sql | data-quality | Generates SQL from natural language without letting an unvalidated query reach the database. |
| **Pick the cheapest checks a pipeline change needs** (`PIPELINE-CHECK-SELECTION`) | any | testing, data-quality | Selects the cheapest checks that would actually catch the regression a change can cause. |
| **Review the data a pipeline run actually produced** (`PIPELINE-OUTPUT-REVIEW`) | any | code-review, data-quality | Reviews the data a pipeline run actually produced, not just whether tests passed. |
| **Test pipeline code with pytest, mocking I/O** (`PYTEST-DATA-PIPELINES`) | python | testing | Tests data pipeline code with pytest, mocking at the I/O boundary. |
| **Implement SCD Type 2 with correct validity intervals** (`SCD2-IMPLEMENTATION`) | sql | data-modeling | Implements Slowly Changing Dimension Type 2 in SQL with correct validity intervals. |
| **Decide what personal data a model may carry** (`SENSITIVE-DATA-HANDLING`) | any | security | Decides what personal data a model may carry, and keeps deletion possible later. |
| **Find Snowflake queries worth optimising** (`SNOWFLAKE-COST-HOTSPOTS`) | snowflake | performance | Finds the Snowflake queries actually worth optimising and reads the metrics that point at a fix. |
| **Restore grants after Snowflake objects are recreated** (`SNOWFLAKE-GRANT-RESTORE`) | snowflake | data-quality | Restores access after Snowflake objects are recreated, without guessing at roles. |
| **Diagnose one Snowflake query from its profile** (`SNOWFLAKE-QUERY-PROFILE-DIAGNOSIS`) | snowflake | performance, debugging | Diagnoses one Snowflake query from its profile and operator statistics. |
| **Rewrite Snowflake SQL without changing results** (`SNOWFLAKE-QUERY-REWRITE`) | snowflake | performance, refactoring | Rewrites a Snowflake query for performance without changing its results. |
| **Repair Snowflake semantic view drift** (`SNOWFLAKE-SEMANTIC-VIEW-DRIFT`) | snowflake | data-modeling, data-quality | Finds where a semantic view no longer matches its tables and repairs it without losing hand-written descriptions. |

## Containers and local environment (4)

| Skill | Applies to | Topic(s) | What it does |
|---|---|---|---|
| **Wire a local data stack in Compose with real readiness checks** (`DOCKER-COMPOSE-LOCAL-STACK`) | docker | containerization | Wires local data stacks in Compose so services wait for a database to be ready, not merely started. |
| **Confirm data loss before Docker cleanup commands run** (`DOCKER-DATA-LOSS-CONFIRMATION`) | docker | — (`always`) | Stops Docker cleanup commands from deleting data until the loss has been stated and confirmed. |
| **Build Python data images that cache well and keep secrets out** (`DOCKER-IMAGE-BUILD`) | docker | containerization | Builds Python data images that keep credentials out of layers, cache well and run as non-root. |
| **Add a first Docker setup to a Python data project** (`DOCKER-PROJECT-SETUP`) | python | containerization | Adds a first working Docker setup to a Python data project, with its dependencies as Compose services. |

## General skills (11)

| Skill | Applies to | Topic(s) | What it does |
|---|---|---|---|
| **Review a code change for correctness and risk** (`CODE-CHANGE-REVIEW`) | any | code-review | Reviews a code change for correctness, risk, test coverage and backward compatibility. |
| **Check work does what was asked before reporting done** (`COMPLETION-VERIFICATION`) | any | development-process | Checks that work actually does what was asked before it is reported as finished. |
| **Prove the cause of a code failure before fixing it** (`ERROR-DIAGNOSIS`) | any | debugging | Finds the cause of a failure by narrowing it down and proving it before changing code. |
| **Turn agreed requirements into a step-by-step plan** (`IMPLEMENTATION-PLANNING`) | any | development-process | Turns agreed requirements into an ordered plan with verifiable steps. |
| **Execute a plan step by step and handle divergence** (`PLAN-EXECUTION`) | any | development-process | Works through an agreed plan one step at a time and handles it when reality diverges. |
| **Adapt installed skills to this repository** (`PROJECT-ADAPTATION`) | any | development-process, documentation | Adapts installed toolset skills by adding repository paths, commands, conventions and examples inside each installed SKILL.md. |
| **Document decisions and boundaries code can't show** (`PROJECT-DOCUMENTATION`) | any | documentation | Documents architecture decisions, component boundaries and constraints a reader cannot infer from the code. |
| **Plan a refactor in behaviour-preserving steps** (`REFACTOR-STEP-PLANNING`) | any | refactoring | Plans and sequences a refactor so behaviour is provably unchanged at every step. |
| **Work out what is needed before writing code** (`REQUIREMENTS-BRAINSTORMING`) | any | development-process | Works out what is actually needed before any code is written. |
| **Edit technical prose without changing meaning** (`TECHNICAL-PROSE-EDITING`) | any | writing | Improves technical prose without changing its meaning or terminology. Scope: `user` (personal preference, not project-selected). |
| **Decide what to test and whether tests catch defects** (`TEST-DESIGN-REVIEW`) | any | testing | Decides what is worth testing and judges whether existing tests would catch a defect. |

## How a project gets a subset of these

See the [installer README](https://github.com/innowise-ai/data-accelerator-installation#how-it-works):
`accelerator-setup` scans the project, asks what the scan can't detect, and
writes a profile; `accelerator install` reads that profile and installs only
the artifacts that match — nothing here is installed wholesale.
