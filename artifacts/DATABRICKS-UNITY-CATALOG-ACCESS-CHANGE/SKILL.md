---
name: databricks-unity-catalog-access-change
description: Changing access in Databricks Unity Catalog - working out who can reach an object and through which grant, then granting, revoking, transferring ownership, applying row filters and column masks, and granting on external locations with the smallest change that does the job, confirming each write. Use when someone needs access to a catalog, schema, table, volume or storage path, cannot read something they should, or must lose access, or when rows or columns of a table need restricting.
---

# Changing Unity Catalog access

In Unity Catalog, whether a principal can read a table is decided by the
hierarchy above the table as much as by the table itself. A grant on a catalog
or schema reaches every object inside it, including objects created later, and
there is no general deny that a table can set against it. Mistakes go in two
directions. A grant made at schema level to answer today's request also gives
away the tables added next month. A revoke on a table appears to work, but the
principal still reads the table through a schema grant to a group they belong
to. Every step below is about seeing the hierarchy before changing it.

This skill covers Unity Catalog securables. The legacy Hive metastore table
access control works differently; if the objects are in `hive_metastore`, say
so and stop rather than applying these rules there.

## What this skill changes

Working out the current state only reads: `SHOW GRANTS`, `information_schema`,
`DESCRIBE`. Everything that changes access is a write, and each one is handled
the same way:

- **Show the statement, what it changes and who it reaches**, including objects
  it covers by inheritance, and wait for the user to confirm before running it.
  Run confirmed statements one at a time and read the state again after each.
- **Ownership transfers** are presented as a decision with their consequences,
  never applied as part of a routine fix.
- **Row filters and column masks** can lock out readers on unsupported compute,
  so list which jobs and clusters read the table before applying one.
- **Grants managed in code.** If the project manages grants in Terraform or a
  bundle, a grant made in SQL is drift that the next apply may remove. Propose
  the change in that code instead, and do not edit it unless asked.

Run under the least privilege that does the job. These instructions are
guidance, not a control; what actually limits the agent is the identity it
connects as. Set that up to match:

- **A read identity by default**, with `BROWSE` on the catalogs in scope (or
  `USE CATALOG` and `USE SCHEMA`) and `READ METADATA` on them. Without
  `READ METADATA`, ownership or `MANAGE`, `SHOW GRANTS` shows only the caller's
  own grants. That gives an incomplete answer with no error, so say in the
  report what the identity could not see. Do not ask for `MANAGE` to get
  visibility: `MANAGE` can grant its holder any data privilege.
- **Writes** run under the object's owner or a principal with `MANAGE` on it,
  normally a human or the deployment service principal, not the agent's read
  identity. If the agent must apply them, use a separate identity with `MANAGE`
  on the one catalog or schema in question, never a metastore admin.

## How access is decided

- **The hierarchy.** Metastore, then catalog, then schema, then tables, views,
  volumes, functions and models. Models are functions for grants
  (`GRANT ... ON FUNCTION`).
- **Inheritance.** A privilege granted on a catalog or schema applies to all
  current and future objects in it. Privileges granted on the metastore do not
  inherit, except `READ METADATA`.
- **Usage privileges.** `SELECT` on a table is not enough; the principal also
  needs `USE CATALOG` on its catalog and `USE SCHEMA` on its schema. This is the
  most common cause of "it was granted but still fails".
- **`BROWSE`** shows names, descriptions and tags, and lets a user request
  access, without reading data. Databricks recommends granting it on catalogs
  to the `All account users` group, so people can find what exists.
- **Views.** A user needs `SELECT` on the view; the view reads its tables with
  its owner's privileges. A view that fails for everyone after an ownership
  change is usually missing the new owner's grants on the tables.
- **Ownership.** The principal that creates an object owns it. The owner has
  every privilege on it and can grant, transfer ownership and drop it.
  Ownership does not inherit downward: a catalog owner can manage the schemas
  in it but does not own them.
- **`MANAGE`** allows granting and revoking, transferring ownership, renaming
  and dropping. Its holder can grant themselves `SELECT`, so treat `MANAGE` as
  full access when deciding who gets it.
- **`ALL PRIVILEGES`** means all applicable privileges on the object, except
  `MANAGE`, `READ METADATA`, `EXTERNAL USE SCHEMA` and `EXTERNAL USE LOCATION`.
  Revoking it also removes the individual privileges it implied.
- **No deny.** The only way to take a privilege away is to revoke the grant
  that gives it, wherever in the hierarchy that is. ABAC deny policies exist,
  in Beta, but they deny only `MANAGE ACCESS CONTROL`, not data access.
- **Principals.** Users, groups and service principals must be defined at the
  account level to receive Unity Catalog privileges. A legacy workspace-local
  group cannot be granted them. Grant to groups and avoid direct grants to
  users. Grant to service principals for jobs.

## Find who can reach what before changing anything

```sql
SHOW GRANTS ON TABLE main.sales.orders;
SHOW GRANTS `data-analysts` ON SCHEMA main.sales;

SELECT grantee, privilege_type, inherited_from
FROM main.information_schema.table_privileges
WHERE table_schema = 'sales' AND table_name = 'orders';
```

`SHOW GRANTS` on an object lists the privileges that affect it, inherited
ones included. `INHERITED_FROM` in `information_schema.table_privileges` names
the catalog or schema a privilege comes from, which is what a revoke has to
target. A principal with `MANAGE` on an object sees only their own grants on it
in `information_schema`, so use `SHOW GRANTS` there.

Grants usually go to groups, so a person's access depends on their memberships,
including nested groups. Ask which groups the person is in, or check them in
the account console, rather than reading only the grants that name them.

Write the result down as rows of principal, privilege, and where it is granted
(object, schema or catalog), plus the group through which the person holds it.
Every decision below is made from that table.

When someone cannot read something they should, check in this order, because
each one masks the next: `USE CATALOG`, `USE SCHEMA`, the object privilege; then
whether the catalog is bound to particular workspaces and their workspace is not
one of them; then whether the table has a row filter or column mask their
compute cannot evaluate (see below).

## Grant at the lowest level that covers the request

| Request | Grant |
|---|---|
| Read one table | `USE CATALOG`, `USE SCHEMA`, `SELECT` on the table |
| Read every table in a schema, including future ones | `USE CATALOG`, `USE SCHEMA` and `SELECT` on the schema |
| Change rows of a table | `MODIFY` on the table, plus the usage privileges |
| Create tables in a schema | `USE CATALOG`, `USE SCHEMA` and `CREATE TABLE` on the schema |
| See what exists, without data | `BROWSE` on the catalog |

```sql
GRANT USE CATALOG ON CATALOG main TO `data-analysts`;
GRANT USE SCHEMA ON SCHEMA main.sales TO `data-analysts`;
GRANT SELECT ON TABLE main.sales.orders TO `data-analysts`;
```

Before proposing a grant on a schema or catalog, list what it reaches today and
say that it also reaches everything created there later. Then let the user
choose; that is a trade between convenience and exposure that only they can
make. Keep direct `MODIFY` on production tables to the service principals that
load them. A person who needs to change production data should go through the
pipeline. The fine-grained `INSERT`, `UPDATE` and `DELETE` privileges are in
Beta; `MODIFY` covers all three.

## Revoking

Find every path first. A principal reaches an object through any of these:

- a direct grant on the object;
- a grant on its schema or catalog, which `INHERITED_FROM` names;
- a grant to any group they belong to, including through nested groups;
- ownership of the object;
- `MANAGE` on the object, its schema or its catalog, which lets its holder
  grant themselves `SELECT`.

`INHERITED_FROM` shows only the second kind. An empty `INHERITED_FROM` for one
group says nothing about another group the same person is in, or about an
owner or a `MANAGE` holder. Work out the other paths from the person's group
memberships, the object's owner (`DESCRIBE TABLE EXTENDED`) and `SHOW GRANTS`
on the object, schema and catalog. A caller with `MANAGE` sees only their own
grants in `information_schema`, so the check looks clean for them however many
other grants exist.

Revoke each grant path where it is granted, from the principal it was granted
to:

```sql
REVOKE SELECT ON SCHEMA main.sales FROM `contractors`;
```

When the access comes through a group grant that other members still need,
revoking it removes their access too. The fix is then a change of group
membership, or a narrower group. That decision belongs to the owner of the
group or the data, so present it to them.

Access through ownership is not revoked; it goes only with a transfer, which is
a decision (see below). Access through `MANAGE` goes only when `MANAGE` is
revoked.

`REVOKE` succeeds even when nothing was granted, so a successful statement
proves nothing. Re-check every path in the list above. Then confirm the revoke
the same way as a grant, by a query that must now fail (see
[Verify and report](#verify-and-report)).

## Ownership

Production catalogs, schemas and objects should be owned by groups, not by
people: when the person leaves, nobody else can grant on what they owned.
Ownership drifts to people because the creator becomes the owner, so a table
first created from someone's notebook or under their run-as identity belongs to
them.

```sql
ALTER TABLE main.sales.orders OWNER TO `sales-data-owners`;
```

Before proposing a transfer, check what it changes beyond the owner field. The
new owner gets full control, including drop. The previous owner loses every
privilege that came only from ownership. That includes a job or pipeline
running as that principal, and the readers of views it owned, which read their
tables with the owner's privileges. Present the transfer as a decision with
those effects listed.

## Row filters and column masks

There are two mechanisms, and a table should be governed by one of them:

- **ABAC policies** attach a filter or mask through governed tags on a catalog,
  schema or table, so it applies to every matching table. Higher-level admins
  define them and table owners cannot override them, which is why Databricks
  recommends them for anything beyond a few tables. They need governed tags,
  `MANAGE` where the policy is attached, and serverless compute or Databricks
  Runtime 16.4 or above.
- **Per-table filters and masks** are set on one table by its owner.

If more than one distinct row filter resolves for a user on a table, access is
blocked with an error. Check `SHOW EFFECTIVE POLICIES` and the table's existing
filter before adding one.

A per-table filter or mask is a SQL function. It runs with its owner's rights,
except for user-context functions such as `IS_ACCOUNT_GROUP_MEMBER` and
`SESSION_USER`, which evaluate as the querying user. Test membership with
`is_account_group_member`, since grants are to account groups.

```sql
CREATE FUNCTION main.security.region_filter(region STRING)
RETURN is_account_group_member('sales-admins') OR region = 'EU';

ALTER TABLE main.sales.orders SET ROW FILTER main.security.region_filter ON (region);

CREATE FUNCTION main.security.email_mask(email STRING)
RETURN CASE WHEN is_account_group_member('support') THEN email ELSE '***' END;

ALTER TABLE main.sales.customers ALTER COLUMN email SET MASK main.security.email_mask;
```

A table has at most one row filter and each column at most one mask. Setting
one needs `EXECUTE` on the function, the usage privileges, and ownership of the
table or `MANAGE` and `SELECT` on it. Remove them with
`ALTER TABLE ... DROP ROW FILTER` and `ALTER TABLE ... ALTER COLUMN ... DROP MASK`
before dropping the function. Dropping the function first makes the table
unreadable.

Applying a filter or mask changes who can read the table and how, so list the
consumers first. These are the limits that break existing readers:

- Dedicated access mode compute needs Databricks Runtime 15.4 LTS or above with
  serverless enabled to read the table, and 16.3 or above to write it. Older
  dedicated clusters cannot read it, and runtimes below 12.2 LTS fail.
- Time travel, deep and shallow clones, path-based file access, and access
  through the Iceberg REST or Unity REST APIs are not supported on the table.
  It cannot be shared through Delta Sharing by a provider using OpenSharing.
- A mask cannot apply to a column used by a generated column, and a filter or
  mask cannot be set on a view.

Which columns and rows need restricting in the first place is the question in
[sensitive-data-handling](../SENSITIVE-DATA-HANDLING/SKILL.md).

## External locations

A storage credential is a cloud identity; an external location pairs one with
a storage path. Privileges on the location decide what can be done under that
path: `READ FILES`, `WRITE FILES` (which requires `READ FILES`),
`CREATE EXTERNAL TABLE`, `CREATE EXTERNAL VOLUME` and `CREATE MANAGED STORAGE`.

`READ FILES` and `WRITE FILES` grant access to files, not to tables: everything
under the path, including what lands there later, with no row or column
control. Databricks advises against granting them to end users. Register an
external table or volume on the location and grant on that instead. Grant
`CREATE EXTERNAL TABLE` or `CREATE EXTERNAL VOLUME` to the engineers or service
principal that register them. Direct file access is occasionally justified for
reading; writing files directly rarely is.

```sql
CREATE EXTERNAL LOCATION landing_orders
  URL 's3://acme-landing/orders'
  WITH (STORAGE CREDENTIAL landing_reader);

GRANT CREATE EXTERNAL TABLE ON EXTERNAL LOCATION landing_orders TO `data-engineers`;
```

Creating a location needs `CREATE EXTERNAL LOCATION` on both the metastore and
the storage credential, which metastore admins hold by default. Do not create
tables or volumes at the root of an external location; use a subpath, so the
location can hold more than one of them.

Dropping is not symmetric, and the difference matters before anyone runs a
`DROP`. Dropping an external table removes the metadata and leaves the files.
Dropping a managed table makes it recoverable with `UNDROP` for seven days by
default, after which its files are deleted.

## Verify and report

1. After each write, read the grants again and compare them with the intended
   rows.
2. Confirm access works as the principal it was meant for. Unity Catalog has no
   way for the agent to assume another identity, so ask a member of the target
   group to run a one-row query, or hand the query over. For a revoke, the same
   query, run by the person who should have lost access or a member of the
   revoked group, must fail. An empty `INHERITED_FROM` is not enough. It does
   not show access through another group, ownership or `MANAGE`.
3. To answer "who changed this", query `system.access.audit` for
   `service_name = 'unityCatalog'` and `action_name = 'updatePermissions'`.
4. Report every grant made, every one proposed but not applied, and anything the
   read identity could not see. A statement that was never run is listed as
   such, not as done.
