# react-jsonschema-form (RJSF v5) structure checks

RJSF reads the JSON Schema (draft-07 by default, validated with Ajv) and a separate
UI schema. Each check below is a way a form can look right in the file and render or
validate wrongly in the browser.

## Conditional fields live only in the conditional branch

RJSF renders every property under the top-level `properties`, always. A field meant
to appear only when a trigger has a certain value must be defined **only** inside the
conditional branch. If it is also in `properties`, it is always visible and the
condition does nothing.

RJSF 5 supports two forms of condition. Pick one per form and use it consistently:

```json
{
  "properties": {
    "connectionType": { "type": "string", "enum": ["sftp", "s3"] }
  },
  "dependencies": {
    "connectionType": {
      "oneOf": [
        {
          "properties": {
            "connectionType": { "const": "sftp" },
            "host": { "type": "string", "title": "Host", "minLength": 1 }
          },
          "required": ["host"]
        },
        {
          "properties": {
            "connectionType": { "const": "s3" },
            "bucket": { "type": "string", "title": "Bucket", "minLength": 1 }
          },
          "required": ["bucket"]
        }
      ]
    }
  }
}
```

The alternative is `if` / `then` / `else` (or an `allOf` of them). Both work.

Check, for each condition:

- Every branch pins the trigger with `const` (or a one-value `enum`). RJSF picks the
  branch the current data validates against; without the pin, several branches can
  match, and the form shows the wrong fields or none.
- There is a branch for every trigger value that should reveal something.
- Each conditional field is a **full** definition: `type`, `title`, `description`,
  and any custom-widget keys the platform uses. A stub such as
  `{ "type": "string", "minLength": 1 }` renders as a bare text box with no label.
- Nested objects with their own conditions follow the same rule inside the nested
  object.

## No `additionalProperties: false` beside conditional branches

In draft-07, `additionalProperties` looks only at the `properties` and
`patternProperties` **next to it**. A field defined only inside a `dependencies` or
`then` branch counts as additional, so `additionalProperties: false` rejects every
config where the condition is met. The form refuses to submit, or a back end
validating with the same schema rejects the saved config.

Either leave `additionalProperties` out of objects that have conditional branches, or
move to a draft where `unevaluatedProperties` exists and the renderer supports it.

## No conditions that point at nothing

An `if` that tests a property that does not exist is never true, so its `then`
never applies. A `then` or a branch whose `required` names a property defined nowhere
in the schema makes every config that meets the condition invalid. Both are usually
left over from a rename. Check
every property name used inside a condition against the inventory.

## `ui:order` covers every field that can appear

When `ui:order` is present, RJSF requires it to name every property in the rendered
schema, unless the list contains the `"*"` wildcard for "everything else". A missing
one stops the form rendering with an error along the lines of *uiSchema order list
does not contain property*. Conditional fields make this easy to miss: the form
renders until the user picks the trigger value that reveals the unlisted field, then
breaks.

So `ui:order` must list conditional fields too, ideally immediately after their
trigger so they appear next to it. Names in `ui:order` that are not currently in the
schema are ignored, so listing a conditional field that is hidden is safe. A nested
object gets its own `ui:order` inside its UI schema entry.

## The UI schema is RJSF's format, not a custom one

The UI schema is a flat object keyed by field name, with `ui:`-prefixed keys:
`ui:order`, `ui:widget`, `ui:placeholder`, `ui:help`, `ui:options`. Flag:

- A wrapper such as `{ "ui": { "fields": [...] } }`. RJSF ignores it entirely.
- Visibility keys such as `conditionalOn`. RJSF has none; visibility comes from the
  schema's conditions.
- `"type": "select"` and similar inside the UI schema. Widgets are chosen with
  `ui:widget`; `type` belongs to the JSON Schema.

## Widgets that match the type

| Schema | Widget |
|---|---|
| `boolean` | `checkbox` |
| `enum` with 2-4 values | `radio`, with `ui:options: { "inline": true }` |
| larger `enum` | `select` |
| `integer` with bounds | `updown` |
| multi-line `string` | `textarea` |
| secret `string` | `password` |

An `enum` whose values are codes (`"sftp"`, `"s3"`) needs readable labels: `oneOf`
entries with `const` and `title` in the schema, or `ui:enumNames` in the UI schema.
The schema-level `enumNames` keyword is the older, deprecated form.
