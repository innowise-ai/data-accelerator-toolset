---
name: config-form-schema-alignment
description: Checks that a component's configuration is described the same way in the code that reads it, the JSON Schema that validates it and the UI schema that renders it as a form - fields, required flags, enums, defaults, bounds and conditional visibility. Use when reviewing or changing the configuration of a connector, plugin or job whose settings are edited through a generated form.
---

# Aligning a configuration form with the code behind it

Connectors, plugins and jobs that users configure through a web form usually carry
their configuration three times:

| Source | What it decides | Typical file |
|---|---|---|
| **The code's config type** | What the component actually reads at run time | a Go struct with `json` tags, a pydantic model, a dataclass |
| **The JSON Schema** | What the form shows, what it accepts, what it requires | `schema.json`, `config.schema.json` |
| **The UI schema** | How each field is drawn: widget, order, help text, labels | `uiSchema.json`, `config.ui.json` |

Nothing makes the three agree. Each is edited by hand, often in different changes,
and each mismatch fails in a way nobody sees at the time: the form saves happily, the
component starts happily, and the user's setting quietly does nothing. This artifact
is how to find those mismatches before they ship.

The JSON Schema and UI schema notes assume **react-jsonschema-form (RJSF) v5**, the
renderer most of these forms use. The RJSF specifics are in
[references/rjsf.md](references/rjsf.md). The cross-source checks below hold whatever
renders the form.

## What each mismatch costs

Knowing the consequence is what lets a reviewer rank findings, so it comes first.

- **In the schema, not in the code.** The form offers the field, the user sets it,
  and the component ignores it. This is the worst case: the user believes the
  behaviour is configured and has no way to find out it is not. Typical cause: a
  field renamed in code (`json:"retries"` became `json:"maxRetries"`) but not in the
  schema.
- **In the code, not in the schema.** The component supports a setting no one can
  reach through the form. Users either never get it or hand-edit stored JSON, which
  the next form save overwrites.
- **Required in one, optional in the other.** Required in the schema but not
  validated in code: anything bypassing the form (an API call, a migration) can
  create a config the component then mishandles. Required in code but not in the
  schema: the form saves a config the component rejects at start-up, far from where
  the user made the mistake.
- **Enum values that differ.** The form offers a value the code's `switch` has no
  case for, and it falls through to a default or an error at run time. Or the code
  supports a mode the form never offers.
- **Defaults and bounds enforced in code only.** The code clamps `retries` to 10, the
  form accepts 50. The user sees 50 in the form and gets 10. Silent correction is a
  mismatch between what the user was shown and what runs.
- **A field the UI schema forgets.** It still renders, with a default widget: a
  password in a plain text box, a long query in a single-line input, an enum showing
  raw code values as labels, no help text.

## Where a constraint belongs

**Enforce defaults and bounds in the schema, where the user can see them.** A
`minimum`, `maximum` and `default` in the schema, drawn with a numeric widget, stops
an invalid value at entry. The user learns the limit when they hit it.

Then the code's own defaulting (a `SetDefaults()` method, pydantic defaults) has
one legitimate job: fields that can **arrive empty**, because they are optional, have
no schema default, and need a non-zero runtime value. A clamp in code for a range the
schema already enforces is dead; a clamp for a range the schema does not enforce is
a schema bug, and the fix is to move the bound into the schema.

Keep code-side validation for anything that bypasses the form. It is the backstop,
not the place a user should first learn the rule.

## The configuration is a stored contract

Saved configurations outlive the code that wrote them. Renaming a field breaks every
stored config that used the old name: the component now reads an empty value, and
the form shows the field blank. Treat a rename as add-new, read-both, migrate,
remove-old, across releases.

Where schemas are published with the component (in an artifact registry, a plugin
bundle), a published version is usually immutable. A wrong schema is fixed by
releasing a new version, not by republishing the old one.

## The review

### 1. Build one inventory

List every leaf field from all three sources against a single key, the JSON path:

- **Schema:** every leaf under `properties`, recursing into nested objects, **and**
  every field defined only inside a conditional branch (`dependencies` / `oneOf`,
  `if` / `then` / `else`). Conditional fields are the ones most often missed.
- **Code:** every field of the config type, following nested types, using the
  serialised name (`json` tag, pydantic alias), not the field name in the source.
  Also read the defaulting and validation code, wherever it lives.
- **UI schema:** every field-name key, and every entry in `ui:order`.

Then one row per path:

| Field (JSON path) | Schema | Code | UI schema | Finding |
|---|---|---|---|---|
| `source.host` | string, required | `Host` `validate:"required"` | placeholder + help | aligned |
| `source.retries` | integer, default 3, max 10 | `Retries`, clamp to 10 in `SetDefaults` | `updown` | redundant clamp |
| `archive.path` | in `oneOf` branch only | missing | in `ui:order` | ignored at run time |

The table is the evidence. A finding without a row behind it is a guess.

### 2. Cross-source checks

Walk the table:

1. Fields missing from the code, then fields missing from the schema.
2. `required` in the schema against the code's required validation, both directions.
3. Every `enum` against the values the code handles (a `switch`, a `oneof=`
   validation tag, a `Literal`), both directions.
4. Every schema `default`, `minimum` and `maximum` against the code's defaulting and
   clamping, using [Where a constraint belongs](#where-a-constraint-belongs).
5. Fields with no UI schema entry, then UI schema entries with no schema field (dead
   configuration that does nothing).

### 3. Renderer checks

Run the structure checks in [references/rjsf.md](references/rjsf.md): conditional
fields defined in the right place, no `additionalProperties: false` beside
conditional branches, no `if` / `then` blocks that name properties which do not
exist, and a `ui:order` that covers every field that can appear.

### 4. Usability, last

Only after the above: does every field have help text or a placeholder that says what
to enter? Do enums show human-readable labels? Is a boolean a checkbox and a small
enum a set of radio buttons? These matter, but a form that is pleasant and wrong is
worse than one that is plain and right, so they never outrank a mismatch.

## Reporting

Lead with the cross-source mismatches from step 2, ordered by
[what each costs](#what-each-mismatch-costs), then renderer faults, then usability. For each, give the JSON path, the three sources'
values side by side, and the fix - including which file the fix belongs in.

If all three sources agree, say so in one line and show the inventory table. Do not
pad an aligned form with style suggestions.
