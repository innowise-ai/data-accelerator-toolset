---
name: sensitive-data-handling
description: Handling personal and sensitive data in a warehouse - classifying columns, deciding what to carry, tokenising so joins survive, keeping it out of logs and lower environments, and making deletion actually delete.
---

# Sensitive data in a warehouse

What counts as personal data in your jurisdiction is a question for whoever owns
that decision. This is about what to do once the answer is known, and about the
handful of engineering choices that decide whether a deletion request is a
half-day task or impossible.

The failures here are unlike the rest of this catalog. A wrong join produces
wrong numbers and someone eventually notices. A column carried one layer too far
produces correct numbers and is discovered by an auditor, or by a breach.

Related: [dbt-project-conventions](../DBT-PROJECT-CONVENTIONS/SKILL.md) for where
layer boundaries sit, [scd2-implementation](../SCD2-IMPLEMENTATION/SKILL.md) for
the history mechanics this artifact constrains, and
[data-incident-debugging](../DATA-INCIDENT-DEBUGGING/SKILL.md) for keeping an
investigation from becoming its own disclosure.

## Find it before deciding anything

```bash
grep -riE "email|phone|ssn|nino|passport|dob|birth|address|postcode|zip|ip_addr|lat|lon|salary|gender|ethnic" models/ --include=*.yml
ls policies/ tags/ 2>/dev/null          # existing classification, if any
```

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
| To join or count distinct people | **Tokenise** — deterministic hash with a secret salt | Joins and cardinality survive; identity does not |
| To contact the person | **Keep raw**, in one narrow table, access-controlled | Everything — so restrict where it lives, not who may query the mart |
| To segment or aggregate | **Generalise** — age band, postcode prefix, region | Analysis survives; re-identification gets much harder |
| Nothing anyone named | **Drop** | Nothing that matters |

**Tokenisation is the one that buys the most.** A deterministic token for a
customer lets every downstream model join, count and segment exactly as before,
while none of those tables holds an identity. Identity stays in one place, and
that one place is what a deletion request has to touch.

Two rules make it work, and skipping either wastes the effort:

- **Salt it, and keep the salt out of the warehouse.** An unsalted hash of an
  email address is reversible by anyone with a word list — the value space is
  small and public. `md5(email)` is not pseudonymisation, it is a slower lookup.
- **Deterministic across tables and across runs.** The same person must produce
  the same token everywhere, or joins break. The moment joins break, someone
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

**Design it out.** If the dimension holds a token and the attributes that changed,
and identity lives in one lookup table, then erasure deletes one row from the
lookup and history stays structurally intact. Every downstream join keeps
working. This is the only approach that stays cheap as the warehouse grows.

**If identity is already in the dimension**, deletion must not simply remove the
rows — that leaves gaps in validity intervals and breaks every invariant that
artifact asserts. Null the identifying attributes in place and keep the interval
skeleton, so the history of *what changed when* survives while the person does
not.

**Deletion is not deletion while a copy survives.** Check every one of these
before reporting a request complete:

| Copy | Typical default |
|---|---|
| Time travel | 1-90 days, silently retaining the pre-deletion version |
| Fail-safe / backups | 7 days, often not addressable by you at all |
| Downstream marts | Rebuilt on their own schedule, not yours |
| Exports and extracts | Files in object storage nobody tracks |
| Lower environments | The copy from six months ago |

Retention is a privacy setting, not a cost setting, and it is usually configured
by someone who was thinking only about cost.

## Access belongs to the layer, not the query

Grant on marts. Do not grant on raw or staging, where the untransformed columns
still sit. If everyone can read staging, every control applied in the mart layer
is advisory.

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
- **Masked** — real structure, tokenised identities, using the *same*
  deterministic function as production so joins behave identically.

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
- Hashing an identifier with no salt and calling it anonymised
- Non-deterministic masking, which breaks joins and gets reverted within a week
- Treating a table as anonymous once the name column is dropped, while postcode
  and date of birth remain
- Designing an SCD2 dimension around an identifier, then meeting erasure later
- Reporting a deletion complete without checking time travel and downstream copies
- Granting pipeline service accounts blanket read because it was quicker
- Pasting real rows into a ticket, a document, or a model prompt
