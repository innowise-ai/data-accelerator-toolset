---
name: power-bi-function-impact
description: Judging a DAX user-defined function before it is introduced or changed — one calculation, many callers — and proving each caller still matches the calculation it replaced. Use when a function is about to be added to a semantic model or an existing function's body is about to change.
---

# Judging a function by its callers

A user-defined function is one calculation written once. Every measure that
calls it moves when the function moves. That blast radius is the work. The
elegance of the body is not.

The function is not the business definition of a metric. Definitions stay on
the measure descriptions, which is where
[power-bi-report-faq](../POWER-BI-REPORT-FAQ/SKILL.md) reads them. This skill
does not decide what a metric means, and it does not implement a metric
shape — a year-over-year comparison, a retention figure, or anything else a
caller might compute. If the question is what the number should be, stop and
say so. The question here is whether a function, already specified, is safe
to introduce or to change.

Its neighbours:

- [power-bi-model-diff](../POWER-BI-MODEL-DIFF/SKILL.md) classifies a function
  edit as one change, result-altering for every caller, and stops when the
  caller set is unknown. This skill is the proof that classification asks
  for, before the edit is treated as done.
- [power-bi-model-audit](../POWER-BI-MODEL-AUDIT/SKILL.md) lists the callers
  in this folder. This skill uses that list. It does not repeat the audit.
- [power-bi-report-faq](../POWER-BI-REPORT-FAQ/SKILL.md) will repeat whatever
  description sits on the measure. Moving the definition onto the function,
  or leaving the measure's description behind, makes the FAQ describe a
  calculation the measure no longer is.

Where the function text lives, and how a caller is recognised, is in
[references/callers.md](references/callers.md).

## Quote the function, or stop

Read the function from the project's TMDL. The body you judge is the body
in the file. Do not reconstruct a signature from memory, from a blog, or
from a function you have seen elsewhere. If the model has no function text
you can quote — the file is absent, or the declaration is not something you
can point at — describe the dependency in words and stop. Inventing a
signature in order to continue is how a review approves a function the model
does not contain.

Text an agent wrote is a draft. A generated body is unverified until the
checks below have been done. "The agent added it" is not one of the checks.

## Introducing a function

Introducing a function is safe only when each caller still matches the
inlined calculation it replaced. Prove that, caller by caller.

"It compiles" means the model accepted the syntax. It does not mean the
number is the same. A function can be accepted and still disagree with the
expression it replaced, because the argument is evaluated at a different
moment, or because the body sees a filter the inlined expression did not.

For each caller, compare the value with the function against the value with
the logic written out at that call site. Same grain, same filters, the
slices the visual actually shows, not only the grand total. Two errors
cancel at the total. If you cannot evaluate both, the introduction is
unverified. Say so and stop. Do not fill the gap with a reason they ought to
match.

The measure's description stays where it is. The function does not inherit
the metric's meaning, and a description written on the function is a note to
the person editing it. It is not a substitute for the measure description
the FAQ will read.

## Changing a function

A change to the body is the same proof against the previous body, for every
caller. The callers you can list are the ones in this folder. If other
reports share the model, their callers are invisible from this project. Name
that limit and stop before calling the change safe. A function that is right
for the report in front of you can be wrong for a report you cannot see, and
there is no file here that would tell you.

[power-bi-model-diff](../POWER-BI-MODEL-DIFF/SKILL.md) will classify the edit.
Classification is not the proof. The proof is the comparison at each caller.

## Grain and filter context belong to the caller

A function that is right on its own can be wrong in a visual. The visual
sets the grain and the filters. The function body runs in that context
unless the body itself changes it. A card and a matrix are different
callers even when they call the same function with the same arguments,
because the matrix adds a grain the card does not.

Read the body you quoted and say which filters it removes or adds, and which
it leaves alone. The ones it leaves alone are the caller's, and they are
part of the result. If the declaration in the file says an argument is
computed before the body runs, or that it is evaluated later in the caller's
context, use that: the two see different filters, and mixing them up is how
an isolated example passes and the visual fails. If the file does not say,
do not invent the mode. Describe the call you can see and stop.

## Verify against SQL at the caller's grain

The check outside the model is a SQL query at the caller's grain, with the
filters the visual applies. It has to reproduce the caller's number, not a
cousin of it. A match at a coarser grain is not a match. A match on one
slice is not a match on the page.

This SQL is a test of the function as called. It is not a design for the
warehouse, and it is not a reason to rewrite the function into SQL. If the
warehouse query and the caller disagree, the function is not yet safe,
however clean the body looks.

## Anti-patterns

- Reconstructing a signature that is not in the file. Inventing a body in
  order to continue is how a review approves a function the model does not
  contain.
- Inventing when an argument is evaluated if the declaration does not say.
  The two timings see different filters; mixing them up is how an isolated
  example passes and the visual fails.
- Calling the change safe when other reports share the model. Callers on
  those reports are invisible from this folder, and a function that is
  right here can be wrong there.
- Moving the metric definition onto the function. The FAQ reads the
  measure description; a note on the function is not a substitute, and
  leaving the measure’s description behind makes the FAQ describe a
  calculation the measure no longer is.
