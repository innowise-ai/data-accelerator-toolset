---
name: kpi-definition-building
description: Turning a business request for a metric into a definition precise enough to implement twice and get the same number - population, grain, which date, re-aggregation, edge cases, and the decisions that have to be asked for rather than chosen. Use when a KPI or metric has been requested in words and has to be built, or when two reports disagree about one. Not for writing column descriptions for a model that already exists.
---

# Writing a KPI definition

A metric described in a sentence is almost never implementable, and the gap does
not show up as a question. It shows up months later as two dashboards with two
    10|numbers, a meeting about which is right, and the discovery that both are correct
under different readings of the same four words.

"Active customers", "on-time delivery rate", "revenue per account" each hide
between five and fifteen decisions. The job here is to surface them, get the ones
that are business decisions decided by the business, and write the result down in a
form that can be implemented and checked.

**The test for a finished definition:** two people who have never spoken could
implement it from the text alone and get the same number. Not "is it documented"
    20|— documentation describes something that exists. This is the specification that
comes first, and if it leaves a choice open, the choice will be made silently and
differently by every implementer.

Its neighbours in this catalog:

- [dbt-model-descriptions](../DBT-MODEL-DESCRIPTIONS/SKILL.md) writes the text for
  a column that already exists, in the model's YAML. This decides what the metric
  *is*, before there is a column; the description is downstream of it and should
  quote it rather than restate it.
    30|- [requirements-brainstorming](../REQUIREMENTS-BRAINSTORMING/SKILL.md) is the
  general version of working out what is needed before building. This is the
  metric-shaped case, where the under-specification is unusually easy to miss
  because the request sounds concrete.
- [tableau-dashboard-faq](../TABLEAU-DASHBOARD-FAQ/SKILL.md) collects the
  definitions a report already carries, for its readers. If that work turns up a
  metric with no definition anywhere, this is what produces one.

Implementing a settled definition as a Tableau calculation, with the query that
has to agree with it, is in [references/tableau.md](references/tableau.md).

    40|## The questions a definition has to answer

Not a form to fill in. Each of these is a place where two reasonable people
diverge, which is why leaving one implicit produces a disagreement rather than an
error.

**Population.** Which entities count, and — more importantly — which are
deliberately excluded. Test accounts, internal orders, staff purchases, cancelled
records, soft-deleted rows, a pilot region. Exclusions are where definitions
differ most and where they are written down least, because at the time they feel
obvious.

    50|**Event or state.** Is the metric counting things that happened in a period, or
things that were true at a moment? "Active customers" is usually a state and gets
built as an event count, or the reverse. This decision determines everything about
the date logic, so it comes before the date question rather than after it.

**Grain.** One row per what, in the computation. And separately, the grain it is
reported at — per day, per week, per customer, per region. The two are different
and conflating them is how a metric becomes impossible to drill into.

**Which date.** Almost every fact carries several: when it happened, when it was
recorded, when it takes effect, when it was posted. They differ by hours or by
    60|weeks, and the choice moves numbers across period boundaries. Name the column,
not the concept.

**Late data and restatement.** Given the chosen date, does a figure for last
Tuesday change when data arrives on Thursday? Both answers are defensible and
they are different metrics. If history is allowed to move, say by how much and
for how long; if it is frozen, say what happens to the late records. This is the
question most likely to be skipped and most likely to cause an argument, because
nobody notices until a number someone screenshotted stops matching.

**Time zone and the day boundary.** Which zone defines "a day". For anything
    70|reported weekly or by fiscal period, also the week start and the fiscal calendar.

**Units.** Currency, and for multi-currency figures which rate and as of when —
transaction date, period end, or a fixed budget rate. Also the scale: a metric in
thousands and the same metric in units look identical in a table.

**Numerator and denominator**, for any rate or ratio. Specifically: is the
denominator filtered the same way as the numerator? Almost always the hidden
defect — "on-time deliveries / deliveries" where the numerator excludes
cancellations and the denominator does not. And what the metric is when the
denominator is zero: zero, null, or undefined and suppressed. Each produces a
    80|different average downstream.

**Re-aggregation.** Can the metric be summed across periods, averaged, or
neither? This is the question dashboards break on. A ratio is a ratio of totals,
not an average of ratios, so a weekly rate cannot be averaged into a monthly one —
and a dashboard with a date filter on it will do exactly that unless the
definition says what the correct roll-up is.

**Deduplication.** What makes two records the same thing, and which one wins.

**Nulls.** Excluded from the calculation, or treated as zero. These give different
averages and the same totals, which is why the difference survives review.
    90|
**Thresholds.** If the definition contains a cut-off — within two days, over 500,
at least three visits — say whether the comparison is inclusive, and against which
clock: calendar days, business days, or the customer's local time.

## Do not invent the business rule

Some of the above are technical and you can settle them. Others are statements
about how the business works — what counts as active, whether a refund reverses a
sale or sits beside it, whether a cancelled order ever counted — and those are not
yours to choose, however plausible the choice.

   100|The failure here is specific and worth naming because it does not look like a
failure. A confident, well-formed definition arrives, it is implemented, it goes
on a dashboard, and within a quarter it is the definition of record. Nobody
remembers it was a guess, and the business is now reporting on a rule it never
agreed to.

So when the request is ambiguous, do not resolve it in the draft. Write the
readings out, say what each implies for the number, recommend one with a reason,
and get an answer:

   110|> "Delivered on time" could mean against the originally promised date or against
> the most recently revised one. On last quarter's data these differ by about
> eleven points. Which one is the commitment being measured?

Then record the answer, who gave it and when, next to the definition. A decision
without an owner gets re-litigated, and the second answer is not always the first
one.

Ask in a batch where you can. A list of six specific questions gets answered;
six separate messages over a week get one reply.

## Write the edge cases as cases
   120|
A definition becomes checkable when it carries worked examples: a short list of
situations with the answer the metric should give.

Pick the boundary ones, which are the ones implementations disagree about: a
refund issued after the period closed, a customer who churned and returned, an
order with no lines, a record whose event date and recorded date fall in different
months, a duplicate arriving from a second system, a value exactly on a threshold.

Three or four of these are worth more than another paragraph of prose. They turn
the definition into something an implementation can be tested against, and they
   130|flush out disagreement while it is still cheap — half the time, writing the cases
is what reveals that the rule nobody questioned has two readings.

## Make two implementations agree

A definition is settled when the same number comes out of two independent paths:
the report that presents it, and a query against the warehouse written directly
from the definition text.

This is worth the effort for a reason beyond catching mistakes. When the two
disagree, the useful conclusion is usually not that one is wrong — it is that the
   140|definition is incomplete, and the disagreement points at exactly which clause is
missing. Resolving the difference is how the specification gets finished.

Compare at more than one level. Matching totals are weak evidence, because two
offsetting errors cancel in an aggregate; break the comparison down by the
dimension the metric is reported across, and check a count of rows alongside the
value.

## A definition has an owner and a version

Metrics change: a rule is revised, an exclusion is added, a threshold moves. When
that happens there is a decision to make, and it is a business decision rather
   150|than a technical one: does history get restated under the new rule, or does the
new definition start from a date and leave past figures as they were?

Either is fine. Silently doing the first is not, because someone's saved report
stops matching and the conclusion they draw is that the data cannot be trusted.
Keep the old definition's text, say when it changed and why, and make the change
visible wherever the number is read.
