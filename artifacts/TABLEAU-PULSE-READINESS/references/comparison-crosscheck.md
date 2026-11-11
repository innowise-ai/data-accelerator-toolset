# Recomputing the comparison an insight claims

A reference for [`../SKILL.md`](../SKILL.md). An insight is a sentence about a
period against another period. The check is that comparison, run independently,
not a rereading of the sentence.

Write the query from the metric definition — the measure, the time column, the
filters, the grain — not from the insight's wording. A query transcribed from
the insight reproduces whatever the definition selected, agrees with it, and
proves nothing.

Match the connection. An extract is a copy as of its last refresh; a live
connection is the warehouse at the moment of the check. Comparing an extract
insight against a live warehouse query is two different populations.

## The comparison in SQL

The skeleton is the same for every insight. Fill the placeholders from the
definition you wrote down, not from what the sentence sounds like.

```sql
with series as (
    select date_trunc('<grain>', <the time column the definition names>) as period,
           <the aggregation the definition names>(<the measure>)         as value
    from <the table the definition names>
    where <every filter in force: data source, extract, metric>
      and <the time column> >= <start of the previous period>
      and <the time column> <  <end of this period>
    group by 1
)
select this_period.period,
       this_period.value                                              as this_value,
       prior.period                                                   as prior_period,
       prior.value                                                    as prior_value,
       this_period.value - prior.value                                as delta,
       (this_period.value - prior.value)
         / nullif(prior.value, 0)                                     as relative_delta
from series this_period
left join series prior
  on prior.period = <the previous period at the same grain>
order by 1;
```

What "the previous period" is belongs in the written comparison. A calendar
month against the month before it is not the same as a trailing thirty days
against the thirty days before that, and a year-to-date against the same
span last year is a third thing. Pulse's comparison is one of those; write
down which before running the query.

A partial current period compared with a complete previous one is the usual
way a correct metric produces a misleading insight. If this month is twelve
days old, the previous month in the join above is thirty-odd days of activity.
Either restrict the previous period to the same number of days, or state that
the insight is about an incomplete period. The query will not decide this;
the definition has to.

## What to compare, besides the headline

- **The two period values, not only the direction.** An insight that says
  "up" when the real figure is up can still be about the wrong population.
- **The row count in each period.** A metric counting entities that is
  counting events matches on totals and not on counts.
- **A breakdown you allow**, if the insight names a segment as the driver.
  The segment's contribution has to be recomputed at the same grain; summing
  a fan-out dimension here is the same grain error the skill refuses in the
  definition.
- **Null and zero denominators**, when the measure is a ratio. A period with
  no activity is null or zero depending on the definition, and Pulse will
  still produce a sentence about it.

Keep the query. It is the regression test for that metric, and it is the
fastest answer the next time an insight is questioned.

If you cannot fill a placeholder — the time column is unknown, the filters
cannot be listed, the aggregation is a guess — do not run a plausible query.
The insight is unchecked, and the missing placeholder is the finding.
