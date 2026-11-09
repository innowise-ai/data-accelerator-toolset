# Skill catalog

Human-readable index of every artifact in this catalog, generated from
[`index.json`](../index.json) (`toolset_ref: refs/tags/v1.4.1`, schema version 2).
Regenerate this file whenever artifacts are added, removed or re-described in
the index — it is a rendering of `index.json`, not a second source of truth.

59 artifacts today: 36 data-engineering specific (dbt, Snowflake, Spark, Databricks, Airflow,
Tableau, Python pipeline code, sensitive data handling, stack-agnostic pipeline quality
and lakehouse layering), 2 for BI and analytics,
4 for containers and local environments, 2 for infrastructure as code, and 15
general skills that apply to any stack. All are `on-demand` except
`DOCKER-DATA-LOSS-CONFIRMATION`, which is `always`: it installs into every
project that uses Docker, because losing a data volume is not something a team
should have to remember to ask protection against.
An `on-demand` artifact is used when the task calls for it, rather than always
loading it. `Applies to` shows the `applies_to` restriction from the index; "any"
means the artifact carries no language/framework restriction. `Scope` is `project`
unless noted — a `project`-scope artifact is selected by what the project is;
`user`-scope reflects a personal preference instead.

An artifact is only installed into a project if `accelerator-setup`'s
questionnaire and scan match it — this list is the full menu, not what any
one project gets.

## Data engineering (36)

| Skill | Applies to | Topic(s) | What it does |
|---|---|---|---|
| **Structure Airflow DAGs for safe, cheap imports** (`AIRFLOW-DAG-STRUCTURE`) | airflow | orchestration | Structures Airflow DAGs so nothing expensive or fragile runs at import time. |
| **Trace wrong data when the pipeline succeeded** (`DATA-INCIDENT-TRACING`) | any | debugging, data-quality | Traces wrong data back to the code that produced it when the pipeline reported success. |
| **Build data quality controls: quarantine, release diff, scorecards** (`DATA-QUALITY-CONTROLS`) | any | data-quality, ingestion | Builds the controls that keep invalid records out of published data, show what each publish changes, and score data quality per source and stage. |
| **Design Databricks declarative pipelines: table types, expectations, CDC** (`DATABRICKS-DECLARATIVE-PIPELINE-DESIGN`) | databricks | ingestion, data-modeling, data-quality | Designs Lakeflow pipelines (formerly DLT): a streaming table or materialized view per dataset, expectations, AUTO CDC and Auto Loader ingestion, without a full refresh losing history. |
| **Change Unity Catalog access without over-granting** (`DATABRICKS-UNITY-CATALOG-ACCESS-CHANGE`) | databricks | security, database-administration | Grants, revokes and restricts access in Databricks Unity Catalog with the smallest change that does the job, after tracing every path through which access is inherited. |
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
| **Turn a requested metric into a definition that can be implemented twice** (`KPI-DEFINITION-BUILDING`) | any | data-modeling | Turns a metric requested in words into a specification precise enough that two independent implementations produce the same number. |
| **Define what belongs in each medallion layer, on any platform** (`MEDALLION-LAYER-BOUNDARIES`) | any | data-modeling, ingestion | Sets what bronze, silver and gold each hold and must not hold, how data moves between them safely, and where quality checks sit, for Fabric, Databricks, plain Spark or dbt. |
| **Reconcile migrated data with the legacy warehouse, column by column** (`MIGRATION-DATA-RECONCILIATION`) | any | data-quality | Compares data moved from a legacy warehouse (SAP BW, Teradata, Oracle) with its lakehouse copy, separates format differences from real ones, and reports only the real ones. |
| **Generate SQL from natural language, validated before it runs** (`NL2SQL-QUERY-VALIDATION`) | sql | data-quality | Generates SQL from natural language without letting an unvalidated query reach the database. |
| **Pick the cheapest checks a pipeline change needs** (`PIPELINE-CHECK-SELECTION`) | any | testing, data-quality | Selects the cheapest checks that would actually catch the regression a change can cause. |
| **Review the data a pipeline run actually produced** (`PIPELINE-OUTPUT-REVIEW`) | any | code-review, data-quality | Reviews the data a pipeline run actually produced, not just whether tests passed. |
| **Test pipeline code with pytest, mocking I/O** (`PYTEST-DATA-PIPELINES`) | python | testing | Tests data pipeline code with pytest, mocking at the I/O boundary. |
| **Implement SCD Type 2 with correct validity intervals** (`SCD2-IMPLEMENTATION`) | sql | data-modeling | Implements Slowly Changing Dimension Type 2 in SQL with correct validity intervals. |
| **Decide what personal data a model may carry** (`SENSITIVE-DATA-HANDLING`) | any | security | Decides what personal data a model may carry, and keeps deletion possible later. |
| **Find Snowflake queries worth optimising** (`SNOWFLAKE-COST-HOTSPOTS`) | snowflake | performance, database-administration | Finds the Snowflake queries actually worth optimising and reads the metrics that point at a fix. |
| **Restore grants after Snowflake objects are recreated** (`SNOWFLAKE-GRANT-RESTORE`) | snowflake | data-quality | Restores access after Snowflake objects are recreated, without guessing at roles. |
| **Diagnose one Snowflake query from its profile** (`SNOWFLAKE-QUERY-PROFILE-DIAGNOSIS`) | snowflake | performance, debugging, database-administration | Diagnoses one Snowflake query from its profile and operator statistics. |
| **Rewrite Snowflake SQL without changing results** (`SNOWFLAKE-QUERY-REWRITE`) | snowflake | performance, refactoring | Rewrites a Snowflake query for performance without changing its results. |
| **Repair Snowflake semantic view drift** (`SNOWFLAKE-SEMANTIC-VIEW-DRIFT`) | snowflake | data-modeling, data-quality | Finds where a semantic view no longer matches its tables and repairs it without losing hand-written descriptions. |
| **Tune a slow Spark job from its Spark UI evidence** (`SPARK-JOB-TUNING`) | spark, databricks | performance, debugging | Finds the stage and the cause that dominate a slow or memory-failing Spark job, fixes that cause and measures the result. |
| **Build cohort, trend and ranking calculations that survive filters** (`TABLEAU-ANALYTICAL-CALCS`) | tableau | data-modeling | Implements known metric shapes in Tableau by choosing between a row-level expression, a level-of-detail expression and a table calculation, and knowing which filters change the answer. |
| **Write a dashboard FAQ from the workbook, not from memory** (`TABLEAU-DASHBOARD-FAQ`) | tableau | documentation | Documents an existing Tableau dashboard from its workbook file and a screenshot of the landing view, taking each metric definition from the workbook rather than inferring one. |
| **Repoint a Tableau workbook at a new warehouse safely** (`TABLEAU-DATASOURCE-MIGRATION`) | tableau | refactoring | Works out what in a workbook will not survive a connection swap, and proves the dashboard still produces the same numbers afterwards. |
| **Find out why a Tableau dashboard is slow before rewriting it** (`TABLEAU-PERFORMANCE-DIAGNOSIS`) | tableau | performance | Establishes which interaction is slow and where the time actually goes — the queries, Tableau's own compute, or rendering — before anything is rewritten. |
| **Assess an inherited Tableau workbook before changing it** (`TABLEAU-WORKBOOK-AUDIT`) | tableau | debugging | Assesses a workbook nobody on the team built: what is in it, which dependencies make a change risky, and what the file cannot tell you. |
| **Review what changed between two Tableau workbook versions** (`TABLEAU-WORKBOOK-DIFF`) | tableau | code-review | Compares two versions of a workbook by inventory rather than by text, and separates the differences that can move a number from the ones that cannot. |

## BI and analytics (2)

| Skill | Applies to | Topic(s) | What it does |
|---|---|---|---|
| **Translate a metric between SQL and a level-of-detail expression without changing the number** (`TABLEAU-MEASURE-TRANSLATION`) | tableau | data-modeling, analytics | Rewrites an existing metric in either direction between SQL and a FIXED, INCLUDE or EXCLUDE expression, stating the grains and filter positions the number depends on. |
| **Define Pulse metrics so the insight matches the warehouse number** (`TABLEAU-PULSE-READINESS`) | tableau | data-modeling, analytics | Defines a Pulse metric from a published data source so the generated insight is about the intended number, and checks an existing insight by recomputing the comparison. |

## Containers and local environment (4)

| Skill | Applies to | Topic(s) | What it does |
|---|---|---|---|
| **Wire a local data stack in Compose with real readiness checks** (`DOCKER-COMPOSE-LOCAL-STACK`) | docker | containerization | Wires local data stacks in Compose so services wait for a database to be ready, not merely started. |
| **Confirm data loss before Docker cleanup commands run** (`DOCKER-DATA-LOSS-CONFIRMATION`) | docker | — (`always`) | Stops Docker cleanup commands from deleting data until the loss has been stated and confirmed. |
| **Build Python data images that cache well and keep secrets out** (`DOCKER-IMAGE-BUILD`) | docker | containerization | Builds Python data images that keep credentials out of layers, cache well and run as non-root. |
| **Add a first Docker setup to a Python data project** (`DOCKER-PROJECT-SETUP`) | python | containerization | Adds a first working Docker setup to a Python data project, with its dependencies as Compose services. |

## Infrastructure as code (2)

| Skill | Applies to | Topic(s) | What it does |
|---|---|---|---|
| **Review a Terraform plan in plain language before apply** (`TERRAFORM-PLAN-REVIEW`) | terraform | code-review, security, infrastructure | Reads a Terraform plan before it is applied and restates each change in plain language, so a reviewer without deep Terraform knowledge can approve or stop it. |
| **Replicate Terragrunt units across tenants without drift** (`TERRAGRUNT-UNIT-REPLICATION`) | terragrunt | infrastructure, refactoring | Adds or moves Terragrunt units in bulk and verifies every tenant and environment got the intended copy. |

## General skills (15)

| Skill | Applies to | Topic(s) | What it does |
|---|---|---|---|
| **Review a code change for correctness and risk** (`CODE-CHANGE-REVIEW`) | any | code-review | Reviews a code change for correctness, risk, test coverage and backward compatibility. |
| **Write code comments in the right place and keep them true** (`CODE-COMMENT-WRITING`) | any | documentation | Decides what a code comment says and where it goes, and keeps comments true as the code changes. |
| **Check work does what was asked before reporting done** (`COMPLETION-VERIFICATION`) | any | development-process | Checks that work actually does what was asked before it is reported as finished. |
| **Write a daily standup update from your actual activity** (`DAILY-STANDUP-UPDATE`) | any | writing, development-process | Drafts a daily standup or status update from commits, pull requests and reviews since the last working day. Scope: `user`. |
| **Prove the cause of a code failure before fixing it** (`ERROR-DIAGNOSIS`) | any | debugging | Finds the cause of a failure by narrowing it down and proving it before changing code. |
| **Turn agreed requirements into a step-by-step plan** (`IMPLEMENTATION-PLANNING`) | any | development-process | Turns agreed requirements into an ordered plan with verifiable steps. |
| **Execute a plan step by step and handle divergence** (`PLAN-EXECUTION`) | any | development-process | Works through an agreed plan one step at a time and handles it when reality diverges. |
| **Adapt installed skills to this repository** (`PROJECT-ADAPTATION`) | any | development-process, documentation | Adapts installed toolset skills by adding repository paths, commands, conventions and examples inside each installed SKILL.md. |
| **Document decisions and boundaries code can't show** (`PROJECT-DOCUMENTATION`) | any | documentation | Documents architecture decisions, component boundaries and constraints a reader cannot infer from the code. |
| **Plan a refactor in behaviour-preserving steps** (`REFACTOR-STEP-PLANNING`) | any | refactoring | Plans and sequences a refactor so behaviour is provably unchanged at every step. |
| **Research what people said about a topic in the last 30 days** (`RECENT-DISCUSSION-RESEARCH`) | any | research | Collects recent posts and engagement about a topic from Reddit, X, YouTube, TikTok, Hacker News, Polymarket, GitHub and the web, and summarises them with sources. Scope: `user`. Upstream: the author's `last30days` skill, pinned to a commit. |
| **Sharpen a request before the agent starts work** (`REQUEST-REFINEMENT`) | any | development-process | On your command, rewrites a request with what the project already answers, asks only what it cannot infer, and starts once you confirm. Scope: `user`. Runs only when called as `/request-refinement`. |
| **Work out what is needed before writing code** (`REQUIREMENTS-BRAINSTORMING`) | any | development-process | Works out what is actually needed before any code is written. |
| **Edit technical prose without changing meaning** (`TECHNICAL-PROSE-EDITING`) | any | writing | Improves technical prose without changing its meaning or terminology. Scope: `user` (personal preference, not project-selected). |
| **Decide what to test and whether tests catch defects** (`TEST-DESIGN-REVIEW`) | any | testing | Decides what is worth testing and judges whether existing tests would catch a defect. |

## How a project gets a subset of these

See the [installer README](https://github.com/innowise-ai/data-accelerator-installation#how-it-works):
`accelerator-setup` scans the project, asks what the scan can't detect, and
writes a profile; `accelerator install` reads that profile and installs only
the artifacts that match — nothing here is installed wholesale.
