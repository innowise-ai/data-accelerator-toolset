---
name: snowflake-grants-after-recreate
description: Restoring Snowflake access after objects are recreated - establishing what grants existed, diffing them against what is in place, emitting the GRANTs to close the gap, and handling the ownership-versus-privilege distinction where these failures usually hide.
---

# Grants after object recreation

`CREATE OR REPLACE` does not modify an object. It drops it and creates a new one
with the same name. Grants belong to the object, so they go with the drop. Nobody
sees an error when this happens. The error surfaces later, for whoever next queries
the object under a role that used to work, and it usually reads "does not exist or
not authorized", which does not point back at the deployment that caused it.

This skill works out what access the recreated objects should have, compares that
with what they have now, and closes the gap. It reports anything it could not
determine instead of guessing a role.

## What recreation does to access

Know the exact rules. Most of the confusion comes from assuming `COPY GRANTS`
restores everything.

| Recreated with | Explicit grants | Schema future grants | Ownership |
|---|---|---|---|
| `CREATE OR REPLACE` | Lost | Applied | Role that ran the statement |
| `CREATE OR REPLACE ... COPY GRANTS` | Copied, except `OWNERSHIP` | Not applied | Role that ran the statement |

Ownership always moves to the role that executed the statement. If a deployment
runs under a service role, that role now owns the object, whoever owned it before.

`CREATE OR REPLACE SCHEMA` and `CREATE OR REPLACE DATABASE` do the same at larger
scale. The container's own grants go, including the `USAGE` every consumer needs
before any object-level grant matters. A dbt full refresh is a `CREATE OR REPLACE`
too.

## Ownership is where the reported failure hides

The typical complaint is that the grant is still on the view but the role that
needs it can't use it. Three mechanisms produce this, and each needs a different
fix.

**Access came through ownership, not through a grant.** An owner has every
privilege on the object, and every role above the owner in the role hierarchy
inherits them. So consumers can reach an object with no explicit grant to them at
all, only because their role sits above the owning role. `SHOW GRANTS ON` the old
object showed one `OWNERSHIP` row and nothing that mentioned those consumers.
`COPY GRANTS` does not copy ownership. After recreation under a different role,
those consumers lose access, and no grant record ever showed they had it. Check
the old owner's position in the hierarchy (`SHOW GRANTS OF ROLE <old_owner>`) to
find out who was relying on it.

**The view runs with its owner's rights.** A view reads its base tables with the
privileges of the view's owner, not the querying role. If the new owner lacks
`SELECT` on a base table, the view fails for every consumer, even though their own
grant on the view is intact. Creating a semantic view requires the owner to have
`SELECT` on the referenced tables, so it fails at creation. A standard view can
fail later, at query time.

**Cortex Agents do not use owner's rights.** A Cortex Agent querying a semantic
view needs its executing role to have `SELECT` on the semantic view **and** on the
underlying tables. A grant on the view alone passes every check a human would run
and still fails for the agent.

## Establish the intended grants

The hard part is knowing what should exist. Once an object has been replaced,
Snowflake mostly forgets what was granted on the old one. Use these sources in
this order, and record which one each intended grant came from.

**A snapshot taken before recreation.** This is the only complete source. If the
recreation has not happened yet, take one:

```sql
show grants on view <db>.<schema>.<object>;

insert into <ops_db>.<ops_schema>.grant_snapshots
select current_timestamp(), '<db>.<schema>.<object>',
       "privilege", "granted_on", "granted_to", "grantee_name", "grant_option"
from table(result_scan(last_query_id()));
```

**The deployment code.** Grants declared next to the object definition, such as a
dbt `grants:` config, a post-deploy SQL file, or a task in the DAG, are an
intended state someone chose deliberately.

**Grant statements in query history.** `ACCOUNT_USAGE.QUERY_HISTORY` keeps a year
of statements:

```sql
select start_time, role_name, query_type, query_text
from snowflake.account_usage.query_history
where query_type in ('GRANT', 'REVOKE')
  and query_text ilike '%<OBJECT_NAME>%'
  and execution_status = 'SUCCESS'
  and start_time >= dateadd('day', -180, current_timestamp())
order by start_time;
```

Include `REVOKE`. A grant that was later deliberately revoked must not be restored.
This search does not see bulk grants like `GRANT SELECT ON ALL VIEWS IN SCHEMA`,
which never name the object, so search for the schema name as well.

**Sibling objects.** Other objects in the same schema, created the same way, show
the local convention. This is inference, not evidence. Present a grant derived
this way as a proposal and ask before emitting it.

Do not rely on `ACCOUNT_USAGE.GRANTS_TO_ROLES` here. It does not contain grants on
dropped objects, and a replaced object counts as dropped. It also lags by up to
two hours, so it can miss the current state too.

## Read the current state

```sql
show grants on view <db>.<schema>.<object>;
show future grants in schema <db>.<schema>;
show grants on schema <db>.<schema>;
show grants on database <db>;
```

Check the container grants as well as the object grants. A consumer with `SELECT`
on the view but no `USAGE` on its schema is still locked out. If the schema is a
managed access schema, only the schema owner or a role with `MANAGE GRANTS` can
issue grants in it. Emitted statements will fail under any other role, so say
which role has to run them.

## Diff and emit

Compare intended against current as `(privilege, grantee type, grantee)` triples
per object. Grantee type matters: a grant to a database role is not the same as a
grant to an account role with the same name. Keep three outputs separate, because
they carry different risks:

1. **Missing privileges.** Plain `GRANT` statements, safe to apply:

   ```sql
   grant select on view <db>.<schema>.<object> to role <role>;
   ```

2. **Ownership that moved.** Do not emit this as a routine fix. Transferring
   ownership back changes who can replace or drop the object, and if the
   deployment role is not in the new owner's hierarchy, the next deployment fails.
   Show the choice: transfer ownership, or grant the missing privileges directly
   to the consumers that used to reach the object through it. When transferring,
   keep the existing grants:

   ```sql
   grant ownership on view <db>.<schema>.<object> to role <role> copy current grants;
   ```

3. **What could not be determined.** List every object with no intended-state
   source, every grant known only by inference, every share the object used to be
   in, and every grantee type other than an account role. An object that was in a
   share is removed from it by recreation, and restoring that is a data-sharing
   decision, not a gap-fill.

Never fill a gap by guessing a role. A wrong grant is a security change that looks
like a fix. A missing grant surfaces as an error the next time someone needs it.

## Verify as the consumer

A grant that exists is not the same as access that works. Test under each role
that needs access:

```sql
use role <consumer_role>;
use secondary roles none;
select 1 from <db>.<schema>.<object> limit 1;
```

`use secondary roles none` is not optional. With secondary roles active, the test
succeeds through some other role the tester happens to hold, and proves nothing
about the role under test. For a semantic view, query it through
`semantic_view(...)` with one dimension. For a Cortex Agent's role, also select
from each underlying table.

## Acceptance

1. Every role that could reach the object before can reach it now, verified by
   querying under that role with secondary roles off.
2. Every emitted grant traces to a snapshot, the deployment code, or a grant
   statement in history. Anything from sibling inference was confirmed by a human.
3. Every grant that could not be established is listed, never silently skipped.
4. Any ownership change is reported as a decision, not applied as part of the
   routine fix.

## Stop repeating this

If grants are being recomputed by hand after every deployment, the deployment is
missing a step. Fix it once:

- Prefer `CREATE OR ALTER` where the object type supports it. It changes the
  object in place, so grants and ownership stay.
- Otherwise put `COPY GRANTS` on every `CREATE OR REPLACE`. In dbt, set
  `copy_grants: true` and declare `grants:` on the model so dbt reapplies them
  after each build.
- Run deployments under the role meant to own the objects, or a role that has been
  granted it, so ownership does not move.
- Use schema-level future grants for objects that new features keep adding. Where
  schema-level and database-level future grants exist for the same object type,
  the schema-level ones win and the database-level ones are ignored.
- Run the consumer-role verification above as a post-deploy check, so the person
  who caused a lost grant is the one who finds out.

This covers grants only. Masking and row access policies, and tags, belong to the
object too. If the object carried any, check they are still attached
(`information_schema.policy_references`); this skill does not restore them.

## Anti-patterns

- Assuming `COPY GRANTS` restores ownership
- Restoring grants from sibling objects without saying they were inferred
- Guessing a role for a grant that has no source
- Re-granting something that had been deliberately revoked
- Verifying with secondary roles on
- Granting `SELECT` on a semantic view and stopping there when a Cortex Agent is
  the consumer
- Transferring ownership as part of a routine gap-fill
