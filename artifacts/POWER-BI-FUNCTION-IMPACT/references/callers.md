# Reading a function and its callers

Written for the judgement in [`../SKILL.md`](../SKILL.md).

The function text is `definition/functions.tmdl` in the semantic-model
folder of the Power BI Project. Quote what is there. If the file is absent,
this model has no user-defined function to judge. Say so and stop. Do not
write a signature so the rest of the task has something to hold.

A `.pbix` does not contain this file in a form you can trust. If that is the
only input, stop. Do not invent an export. If the model is only
`model.bim`, stop; do not convert it.

## What a caller is

A caller is an expression in this folder that invokes the function's name:

- a measure
- a calculated column
- a calculation item
- another function

A description, an annotation, or a visual title that mentions the name is
not a caller. Search the TMDL and the report's queries. The report can call
a function from a visual calculation or a report-level measure; those call
sites count, and they are easy to miss if you only read `functions.tmdl`.

The caller list from this folder is incomplete when other reports use the
model. Say that before judging a change safe. There is no file in this
project that lists those reports.

## What to quote

Quote the body and the parameter list as the file writes them. Keep the
measure descriptions out of the quote. They are not part of the function,
and they are not updated by a change to the body.

If the declaration states when an argument is evaluated — before the body,
or later in the caller's filter context — that statement is part of what you
quote, because it decides which filters the argument sees. If it states
nothing, do not add a mode. The absence is the stop condition for any claim
about when the argument is computed.

## The comparison

For each caller, the thing you compare is:

1. The caller's value with the function.
2. The caller's value with the logic written out in place of the call, at
   that call site.
3. A SQL query at that same grain and those same filters.

All three have to agree on the slices the visual shows. Agreement at the
total only is a failed comparison. If any of the three cannot be run, the
result is "unverified", not a softer version of "safe".

An agent-written body is a draft until this comparison has been done. The
file will not tell you the body was generated. If this session wrote it, it
has not been accepted.
