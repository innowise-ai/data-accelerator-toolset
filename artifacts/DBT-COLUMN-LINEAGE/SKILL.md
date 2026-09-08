---
name: dbt-column-lineage
description: Tracing a column's origin and transformations through dbt models via the dbt Cloud Discovery API - upstream sources, downstream dependents, and what changed at each hop. Requires Desktop Commander to run Python scripts locally.
---

# dbt column lineage

Trace column origins and transformations through dbt models using the dbt
Cloud Discovery API. Answers "where did this field in the mart come from" and
"what breaks if I change this column" without reading SQL by hand across a
chain of models.

**Requires Desktop Commander to execute Python scripts locally on your
machine.** This skill calls dbt Cloud's Discovery API, not dbt Core's local
manifest — it needs a dbt Cloud account and a network path to it.

## Prerequisites

1. **Desktop Commander MCP server** installed and running.
2. **Python 3.7+** installed on your local machine.
3. **Required Python packages**:
   ```bash
   pip install -r requirements.txt
   ```

## Environment setup

Scripts run locally via Desktop Commander and read credentials from
environment variables — nothing is hardcoded, nothing is passed as a CLI
argument that would land in shell history.

| Variable | Description | Example |
|---|---|---|
| `DBT_CLOUD_HOST` | GraphQL API endpoint URL | `https://metadata.cloud.getdbt.com/beta/graphql` |
| `DBT_CLOUD_ENVIRONMENT_ID` | dbt Cloud environment ID (numeric) | `123456` |
| `DBT_CLOUD_TOKEN` | Bearer token for authentication | from dbt Cloud → Account Settings → API Access |
| `SKILL_SCRIPTS_PATH` | Absolute path to this skill's `scripts/` directory | platform-specific, see below |

### macOS / Linux

Add to `~/.zshrc` or `~/.bashrc`, then `source` it:

```bash
export DBT_CLOUD_HOST="https://metadata.cloud.getdbt.com/beta/graphql"
export DBT_CLOUD_ENVIRONMENT_ID="your_environment_id"
export DBT_CLOUD_TOKEN="your_bearer_token"
export SKILL_SCRIPTS_PATH="/absolute/path/to/DBT-COLUMN-LINEAGE/scripts"
```

### Windows (PowerShell)

Add to `$PROFILE` (create it first if `Test-Path $PROFILE` is false):

```powershell
$env:DBT_CLOUD_HOST = "https://metadata.cloud.getdbt.com/beta/graphql"
$env:DBT_CLOUD_ENVIRONMENT_ID = "your_environment_id"
$env:DBT_CLOUD_TOKEN = "your_bearer_token"
$env:SKILL_SCRIPTS_PATH = "C:\absolute\path\to\DBT-COLUMN-LINEAGE\scripts"
```

Prefer user-scope environment variables over `setx` run as administrator —
`setx` writes to the machine-wide store, which is a wider blast radius than a
credential this personal needs.

## Workflow

All scripts execute locally via Desktop Commander, which captures stdout/
stderr and returns it. Route the user's goal to the matching script:

| User goal | Action |
|---|---|
| "I want to explore a column's lineage" | Full lineage workflow below |
| "What models exist?" | `get_all_models.py` |
| "What columns are in model X?" | `get_model_columns.py` |
| "Show me the SQL for model X" | `get_model.py --show-sql` |

### Full lineage workflow

1. **Validate the model exists.**
   ```bash
   python "${SKILL_SCRIPTS_PATH}/get_all_models.py" --filter "model_name"
   ```
   Confirm the exact `uniqueId` — the format is `model.<PROJECT>.<model_name>`,
   e.g. `model.ANALYTICS.fact_orders`.

2. **Validate the column exists.** Column names are case-sensitive in the
   lineage API — an unvalidated typo returns an empty result, not an error.
   ```bash
   python "${SKILL_SCRIPTS_PATH}/get_model_columns.py" model.PROJECT.model_name
   ```

3. **Trace the lineage.**
   ```bash
   python "${SKILL_SCRIPTS_PATH}/get_column_lineage.py" model.PROJECT.model_name COLUMN_NAME --tree
   ```

4. **Explore a specific transformation**, on follow-up:
   ```bash
   python "${SKILL_SCRIPTS_PATH}/get_model.py" model.PROJECT.upstream_model --show-sql
   ```

## Scripts reference

| Script | Purpose | Key arguments |
|---|---|---|
| `get_all_models.py` | List models in the environment | `--filter`, `--page-size` |
| `get_model.py` | Get model details and compiled SQL | `--show-sql` |
| `get_model_columns.py` | List a model's columns | `--filter` |
| `get_column_lineage.py` | Trace a column's lineage | `--tree`, `--output` |

## Output formats

**Tabular** (default): flat DataFrame, for programmatic use.
**Tree** (`--tree`): indented upstream/downstream hierarchy.

Example tree output:

```text
UPSTREAM (where this column comes from):
→ [fact_orders].ORDER_STATUS [passthrough]
  └─ [stg_orders].order_status [passthrough]
    └─ [raw_orders].status_code [renamed]

DOWNSTREAM (what depends on this column):
→ [fact_orders].ORDER_STATUS
  └─ [agg_orders_daily].order_status
```

`transformationType` (`passthrough` / `transformed` / `renamed`) is the answer
to "what did they do to this column" — read it before reading the SQL.

## Interpreting results

- **parentColumns** — upstream columns this one derives from.
- **childColumns** — downstream columns that depend on this one.
- **transformationType** — `passthrough`, `transformed`, `renamed`, etc.
- **nodeUniqueId** — the model containing this column.

To explain a specific transformation: take the model from `nodeUniqueId` in
the lineage result, pull its SQL with `get_model.py <unique_id> --show-sql`,
and locate the column reference there.

## GraphQL reference

For query customization, see [`references/graphql_reference.md`](references/graphql_reference.md).

## Desktop Commander execution notes

Detect the platform from Desktop Commander's `systemInfo`
(`isMacOS`/`isWindows`/`isLinux`/`platform`), then run:

- **macOS/Linux:** `source ~/.zshrc && python3 "${SKILL_SCRIPTS_PATH}/script_name.py" [arguments]`
- **Windows PowerShell:** `python "${env:SKILL_SCRIPTS_PATH}/script_name.py" [arguments]`
- **Windows cmd:** `python "%SKILL_SCRIPTS_PATH%/script_name.py" [arguments]`

Use Desktop Commander's `start_process` with `timeout_ms` around 30000 for API
calls. stdout carries the result (JSON, table, or tree); stderr carries status
and errors. Forward slashes work in paths on all three platforms — prefer them
over backslashes to avoid escaping.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `command not found: python` | Python not on `PATH` | Try `python3` on macOS/Linux |
| `SKILL_SCRIPTS_PATH not set` | Env vars not loaded | Desktop Commander does not auto-source shell configs — prefix commands with `source ~/.zshrc &&` |
| `Missing required environment variables` | Credentials not configured | Walk the user through Environment setup above |
| API authentication error | Invalid or expired token | Generate a new token in dbt Cloud → Account Settings → API Access |
| Empty lineage result for a column that should exist | Case mismatch | Re-run `get_model_columns.py` and copy the exact casing |

## Known limits

- Reads metadata, not data — it shows where a column comes from, not whether
  its values are correct. It does not replace validating a pipeline's output.
- The Discovery API's lineage endpoint is a beta GraphQL schema
  (`/beta/graphql`). If a query starts failing, check the schema in
  `references/graphql_reference.md` before assuming the skill is broken.
- Needs dbt **Cloud**, not dbt Core — there is no local-manifest fallback.
- Runs on the local machine via Desktop Commander, not in a sandboxed agent
  context; on a managed or client machine this may run into local execution
  policy.
