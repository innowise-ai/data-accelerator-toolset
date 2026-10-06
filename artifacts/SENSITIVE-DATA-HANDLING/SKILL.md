---
name: sensitive-data-handling
description: Handling personal and sensitive data in a warehouse - classifying columns, deciding what to carry, tokenising so joins survive, keeping it out of logs and lower environments, and making deletion actually delete. Use when a model, pipeline or log touches personal or sensitive data.
---

# Sensitive data in a warehouse

What counts as personal data in your jurisdiction is a question for whoever owns
that decision. This is about what to do once the answer is known, and about the
handful of engineering choices that decide whether a deletion request is a
half-day task or impossible.

The failures here are unlike the rest of this catalog. A wrong join produces
wrong numbers and someone eventually notices. A column carried one layer too far
produces correct numbers and is discovered by an auditor, or by a breach.

Related: [dbt-layer-boundaries](../DBT-LAYER-BOUNDARIES/SKILL.md) for where
layer boundaries sit, [scd2-implementation](../SCD2-IMPLEMENTATION/SKILL.md) for
the history mechanics this artifact constrains, and
[data-incident-tracing](../DATA-INCIDENT-TRACING/SKILL.md) for keeping an
investigation from becoming its own disclosure.

## Find it before deciding anything

```bash
# Column names that usually mean personal data, in schema files and the code that selects them
grep -rniE '(^|[^a-z])(e_?mail|phone|mobile|ssn|nino|passport|dob|birth|address|post_?code|zip|ip_?addr|latitude|longitude|lng|salary|gender|ethnic|full_?name|first_?name|last_?name|surname)' \
  --include=*.yml --include=*.sql --include=*.py .

# Classification that already exists - column tags, meta blocks, masking policies
grep -rniE 'pii|sensitive|classification|masking_policy' --include=*.yml --include=*.sql .
```

The pattern anchors each term to the start of a word part, so `customer_email`
matches and `relation` does not. It searches SQL and Python as well as YAML
because undocumented columns are exactly the ones nobody classified.

Column names lie in both directions. A `customer_ref` holding an email address
is common; so is a `full_name` column that was emptied years ago and never
dropped. Sample the data before trusting the name, and sample it with counts
rather than rows.

Four categories, because they behave differently and only the first is obvious:

| Category | Examples | Why it matters |
|---|---|---|
| **Direct identifier** | email, phone, national id, full name, account number | Identifies one person on its own |
| **Quasi-identifier** | postcode, date of birth, gender, job title, employer | Identifies nobody alone; identifies almost everyone in combination |
| **Sensitive attribute** | health, religion, ethnicity, sexuality, salary, union membership | Harm on disclosure even where identity is not established |
| **Secret** | tokens, keys, passwords | Not a privacy problem. Should never be in a warehouse at all |

**Quasi-identifiers are the ones teams get wrong.** Postcode, date of birth and
gender together identify a large majority of a national population. A table
carrying all three, with the name column dutifully dropped, is not anonymous —
and calling it anonymous in a data catalog is worse than not classifying it,
because it licenses everyone downstream to treat it as safe.

## Decide per column: carry, transform, or drop

The default is **drop**. A column earns its place downstream by a named consumer
needing it, not by having existed upstream.

| What the consumer actually needs | Approach | What you keep, what you lose |
|---|---|---|
| To join or count distinct people | **Tokenise** — a surrogate key from an identity table, or a keyed hash | Joins and cardinality survive; identity does not |
| To contact the person | **Keep raw**, in one narrow table, access-controlled | Everything — so restrict where it lives, not who may query the mart |
| To segment or aggregate | **Generalise** — age band, postcode prefix, region | Analysis survives; re-identification gets much harder |
| Nothing anyone named | **Drop** | Nothing that matters |

**Tokenisation is the one that buys the most.** A stable token for a customer
lets every downstream model join, count and segment exactly as before, while
none of those tables holds an identity. Do it at the first layer you control —
staging, in a dbt project — so nothing after that point ever sees the raw value.

There are two ways to make the token, and they differ on the one property that
matters later:

- **A surrogate from an identity table.** One table maps the identifier to a
  randomly generated key; ingestion looks the key up, or creates one for a
  person not seen before. The key cannot be recomputed from the email, so
  deleting the mapping row really does cut the person off from their history.
  This is the shape to use wherever erasure requests apply.
- **A keyed hash** — HMAC-SHA256 of the identifier with a secret key. No table
  to maintain, and two systems that share the key produce the same token. But
  anyone holding the key and an email recomputes the token, so it is
  pseudonymisation, not anonymisation: the tokenised tables are still personal
  data, and no deletion of a lookup row erases anyone.

Three rules apply to either, and skipping one wastes the effort:

- **Never a bare hash.** An unkeyed hash of an email address is reversible by
  anyone with a word list — the value space is small and public. `md5(email)`
  is not pseudonymisation, it is a slower lookup.
- **Keep the key out of the query text.** A key written into SQL is stored in
  dbt's compiled output under `target/`, in the warehouse query history, and in
  every log that echoes statements. Compute the token at ingestion with the key
  from a secrets manager, or call a warehouse function that reads a secret by
  name, so the query mentions the key without containing it.
- **The same token everywhere and on every run.** The same person must produce
  the same token in every table, or joins break. The moment joins break, someone
  restores the raw column to get their report working, and every other control
  becomes decorative.

Generalising has one trap worth naming: bands must be wide enough that the rare
values do not stand out. An age band of 90+ holding four people in one postcode
is not generalised.

## Where it must never arrive

Each of these is a real path that produces no error:

- **Logs and error messages.** `logger.error(f"failed row: {row}")` writes
  personal data into a log system with its own retention, its own access rules
  and no deletion path. Log the key and the failure reason, never the record.
- **Stored test failures.** dbt's `store_failures` writes every failing row into
  an audit schema, and a uniqueness or not-null test on a customer table stores
  exactly the identifiers it was checking. Those tables have no retention of
  their own. Keep them off for tests over personal columns, or point them at a
  schema with the same access rules and a short retention.
- **Orchestrator logs and XCom.** An Airflow task that prints a dataframe, or
  passes a batch of rows through XCom, copies them into the metadata database
  and the task log store, where they stay until someone thinks to purge them.
- **Lower environments.** Copying production into dev is the most common
  disclosure in data teams, and it is usually done in good faith to reproduce a
  bug. See test data below.
- **Test fixtures.** "The first thousand real rows" is a production extract that
  lives in version control forever, replicated to every clone.
- **Incident documents and tickets.** A pasted result set outlives the incident
  by years in a wiki nobody re-reads.
- **Model prompts and agent context.** Pasting rows into a prompt sends them to a
  third party and to whatever retention that party applies. Send the schema, the
  aggregate, or synthetic rows.

## History and deletion: the tension nobody writes down

SCD2 exists to keep every version of every row forever. Erasure requires removing
a person from that history. These are in direct conflict, and the time to resolve
it is when the dimension is designed — not when the first request arrives.

**Design it out.** Key the dimension on a surrogate from an identity table — the
random-key kind described under tokenisation, not a keyed hash. Erasure then
deletes one row from the identity table, and history stays structurally intact:
every surrogate key, every interval and every fact join keeps working. This is
the only approach that stays cheap as the warehouse grows.

Two things this does not do on its own, and both are easy to miss:

- **It does not touch the attributes.** Postcode, date of birth and job title
  sitting on the dimension rows can still single the person out, which is the
  quasi-identifier problem from above. Null or generalise them on that key's
  rows as part of the same request.
- **It does not stop the person coming back.** If the source still holds them,
  the next load finds an unknown identifier and mints a fresh key. Erase in the
  source first, or keep a suppression list the load checks.

A keyed hash cannot be designed out this way. Its token is recomputable from the
identifier, so deleting a lookup row erases nothing. History keyed on it has to
be cleaned like the case below, with the token itself counted as an identifying
attribute and overwritten with a random value everywhere it appears.

**If identity is already in the dimension**, do not simply delete the person's
rows. Deleting every version of a key leaves the interval checks in
scd2-implementation passing — the key just vanishes — but every fact row that
references those surrogate keys loses its dimension, so inner joins silently drop
the facts and totals shift with no error. Deleting only some versions leaves
gaps in the history. Null the identifying attributes on every version instead,
and keep the surrogate keys and interval skeleton, so the history of *what
changed when* survives while the person does not. Erase the source first here
too: otherwise the next merge sees the attributes "changed" back and opens a new
version with the identity restored.

**Deletion is not deletion while a copy survives.** Check every one of these
before reporting a request complete:

| Copy | Typical default |
|---|---|
| Time travel | Snowflake 1 day, up to 90; BigQuery 7 days. Silently keeps the pre-deletion version |
| Fail-safe / backups | 7 days after time travel on both, and not addressable by you at all |
| Downstream marts | Rebuilt on their own schedule, not yours |
| Exports and extracts | Files in object storage nobody tracks |
| Lower environments | The copy from six months ago |

Retention is a privacy setting, not a cost setting, and it is usually configured
by someone who was thinking only about cost.

## Access belongs to the layer, not the query

Grant on marts. Do not grant on raw or staging, where the untransformed columns
still sit. If everyone can read staging, every control applied in the mart layer
is advisory. The staging example in dbt-layer-boundaries carries `email` and
`full_name` straight through, which is right for showing the staging rule and
only safe while staging stays ungranted. Where tokenising in staging is an
option, take it, and the question of who can read staging mostly goes away.

Where the warehouse supports row and column level policies, they are worth more
than a mart-shaped copy for each audience — one table, one definition, different
visibility. Where it does not, a restricted view over a restricted base table is
the usual shape.

Service accounts need the same treatment as people, and usually receive less.
A pipeline account with blanket read is the widest hole in most warehouses,
because nobody reviews it after it works.

## Test data: generate or mask, never sample

Sampling production and calling it test data moves the problem rather than
solving it. Two approaches that work:

- **Synthetic** — generated rows matching the schema and the shapes that matter
  (nulls, duplicates, boundary dates). Best for unit tests, and it can live in
  the repository.
- **Masked** — real structure, tokenised identities, with one tokenisation
  applied consistently across every table so joins behave identically. Give the
  environment a key of its own: a production key copied into dev puts the means
  of re-identification exactly where the controls are weakest.

Masking that is not deterministic across tables produces a dataset where nothing
joins, which fails the first time someone tries to reproduce a real bug — and
that is precisely when the production copy reappears.

## When you cannot decide, say so

A column you are unsure about is a question for whoever owns data protection, and
the cost of asking is a comment on a pull request. Guessing costs a disclosure
that cannot be undone. Name the column, say what you think it is, and let the
decision be made by the person who is accountable for it.

## Anti-patterns

- `select *` through a staging layer, carrying identifiers into marts nobody
  meant to expose
- Logging the row on error rather than the key
- Copying production into a lower environment to reproduce a bug
- Test fixtures built from real rows
- Hashing an identifier with no key and calling it anonymised
- Writing the hashing key into SQL, where compiled output and query history keep it
- Deleting the lookup row for a keyed-hash token and calling the person erased
- Non-deterministic masking, which breaks joins and gets reverted within a week
- Treating a table as anonymous once the name column is dropped, while postcode
  and date of birth remain
- Designing an SCD2 dimension around an identifier, then meeting erasure later
- Reporting a deletion complete without checking time travel and downstream copies
- Granting pipeline service accounts blanket read because it was quicker
- Pasting real rows into a ticket, a document, or a model prompt
