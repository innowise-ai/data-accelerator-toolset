# Cross-checking each shape in SQL

Supporting detail for [`../SKILL.md`](../SKILL.md). One query per shape, written to
be the independent second implementation that the Tableau calculation has to agree
with.

Two rules about using them:

**Write the query from the metric definition, not from the Tableau calculation.**
A query transcribed from the calculation carries the same misunderstanding into
both implementations, matches perfectly, and proves nothing. The entire value is
that the two paths are independent.

**Match the filter and parameter state.** A view at its defaults is a different
query from the one below unless the defaults are written into the `where` clause.
Most apparent disagreements are this.

The queries are skeletons in plain SQL. Adapt the date functions to the engine;
the shape is the part that matters.

## Cohort retention
The anchor is computed per entity over the whole history, which is the point — it
must not depend on the reporting window.

```sql
with anchor as (
    select entity_id,
           min(event_date) as cohort_date
    from events
    where <the population the definition names>
    group by entity_id
),
activity as (
    select a.entity_id,
           date_trunc('month', a.cohort_date)                               as cohort_month,
           date_diff('month', date_trunc('month', a.cohort_date),
                              date_trunc('month', e.event_date))            as period_index
    from anchor a
    join events e on e.entity_id = a.entity_id
    where <the population the definition names>
)
select cohort_month,
       period_index,
       count(distinct entity_id) as retained
from activity
group by 1, 2
order by 1, 2;
```

What to compare: the cohort sizes at `period_index = 0` first. If those disagree,
nothing else is worth comparing — the anchor differs, which usually means the
Tableau implementation let a filter re-anchor the cohort.

## Funnel

Entities, not events, and the furthest stage each one reached.

```sql
with reached as (
    select entity_id,
           max(stage_rank) as furthest_stage
    from events
    where <the population>
    group by entity_id
)
select s.stage_rank,
       s.stage_name,
       count(r.entity_id) as entities
from stages s
left join reached r on r.furthest_stage >= s.stage_rank
group by 1, 2
order by 1;
```

What to compare: the count at the first stage against a plain distinct count of
entities in the population. They must be equal, and when they are not the
implementation is counting events.

## Period over period

The date spine is the whole reason for the left join. Without it, a missing period
is absent rather than zero, and that is the defect this check exists to catch.

```sql
with spine as (
    select distinct date_trunc('month', calendar_date) as period
from calendar
    where calendar_date between <range>
),
actuals as (
    select date_trunc('month', <the date the definition names>) as period,
           sum(<measure>)                                       as value
    from facts
    where <the population>
    group by 1
)
select sp.period,
       a.value,
       lag(a.value) over (order by sp.period) as prior_period_value
from spine sp
left join actuals a on a.period = sp.period
order by sp.period;
```

What to compare: a period that has no rows in `actuals`. The query returns it with
a null value and still aligns the following period's comparison correctly. A
positional offset in Tableau does not, and the difference appears only here.

## Rolling average

```sql
select period,
       avg(value) over (order by period
                        rows between 2 preceding and current row) as rolling_3,
       count(value) over (order by period
                          rows between 2 preceding and current row) as points_in_window
from <the spine-joined series above>
order by period;
```

`points_in_window` is the part worth keeping. It makes the partial windows at the
start explicit, so the comparison shows whether Tableau is suppressing them,
averaging fewer points, or quietly doing something else.

## Ranking

```sql
select entity_id,
       sum(<measure>)                                  as value,
       rank() over (order by sum(<measure>) desc)      as position
from facts
where <the population, as the definition states it>
group by entity_id
order by position;
```

What to compare: run it twice, once with the dashboard's filter in the `where`
clause and once without. The two rank orders differ, and which one matches the
Tableau view tells you whether the filter is being applied before the ranking or
after it. That is the question the implementation has to answer deliberately.

## Pareto and share of total
```sql
with totals as (
    select entity_id, sum(<measure>) as value
    from facts
    where <the population>
    group by entity_id
)
select entity_id,
       value,
       sum(value) over (order by value desc rows unbounded preceding)
         / sum(value) over ()                                            as cumulative_share
from totals
order by value desc;
```

What to compare: the denominator. `sum(value) over ()` is the total of everything
the query returned, which is also what Tableau's share-of-total gives by default.
If the definition says the share is of the whole population rather than of the
filtered view, both implementations need changing, and this is where that gets
noticed.

## What to compare, for every shape

- the value at two or more levels of aggregation, since offsetting errors cancel
  in a total and separate underneath it
- a row or entity count alongside the value, which catches a metric counting the
  wrong thing while totalling correctly
- the first period, the last period, and one period with no data
- the same view filtered and unfiltered

Keep whichever query ends up agreeing. It is the regression test for that
calculation, and it is the fastest answer available the next time the number is
questioned.
