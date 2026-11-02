# The three keywords, and the SQL each one becomes

A reference for [`../SKILL.md`](../SKILL.md). The choice between them is made
there; this is what each one computes and how it is written as a query.

Throughout, *the view's grain* means the dimensions on the sheet's rows,
columns, and anything else that splits the marks. That set is the second half of
every expression below, which is why it is stated before any of them is written.

## What each keyword does to the grain

| Keyword | Computes at | Relationship to the view |
|---|---|---|
| `FIXED` | Exactly the dimensions it names | Ignores the view's dimensions |
| `INCLUDE` | The view's dimensions **plus** those it names | Relative to the view |
| `EXCLUDE` | The view's dimensions **minus** those it names | Relative to the view |

An expression with no dimensions — `{ SUM([Sales]) }` — computes over the whole
table, which is `FIXED` with an empty list and behaves like one.

Two notes that follow from the table rather than from anything Tableau-specific.
`FIXED` is the only one of the three whose meaning can be read off the formula,
which is why it is over-used: it is the one that looks safe. And `FIXED` naming
every dimension already on the sheet is the view's own grain, written in a way
that no longer responds to the dimension filters.

## The result is aggregated a second time

A level-of-detail expression returns a value per its own grain. The view then
has to render one mark per *its* grain, so it aggregates those values again.
Which aggregate is used is a choice on the shelf, and it is part of the metric:

- `SUM` of a per-entity figure adds that figure once per row the view produced
  for the entity. On a sheet split by anything the expression does not name, the
  total is a multiple of the real one.
- `AVG` of a per-entity figure is the unweighted mean of entity totals. That is
  a defensible metric and it is rarely the one the SQL computed, which usually
  divides two sums.
- `MIN` or `MAX` of a per-entity figure is the usual way to carry an attribute
  down to a finer grain without multiplying it, because every row for that
  entity holds the same value.

The query the expression replaces makes this visible as a `GROUP BY`. The sheet
does not, which is why the roll-up belongs in the written assumptions.

## `FIXED` as a query

A subquery at the fixed grain, joined back on the fixed dimensions:

```sql
with per_customer as (
    select customer_id,
           sum(amount) as customer_total   -- the expression's aggregate
    from orders
    where <filters that run before FIXED: extract, data source, context>
    group by customer_id                   -- the expression's dimensions
)
select o.order_month,                      -- the view's dimensions
       sum(c.customer_total) as metric      -- the view's second aggregation
from orders o
join per_customer c on c.customer_id = o.customer_id   -- the join keys
where <the dimension filters, which FIXED did not see>
group by o.order_month;
```

Three parts of that skeleton are the translation, and all three are easy to drop:

- The `where` inside the subquery holds only the filters that run before the
  expression. Moving a dimension filter in there reproduces a context filter,
  which is a different workbook.
- The join keys are the fixed dimensions, all of them. A missing key spreads the
  subquery's value across more rows than it belongs to; the individual rows look
  plausible and the total is too high.
- The outer aggregate is whichever roll-up the sheet uses. `sum` here is not a
  default — it is a claim about the shelf.

## `INCLUDE` as a query

The view's dimensions plus the included ones, aggregated once more at the view's
grain:

```sql
with finer as (
    select region, product_id,             -- view dimensions + INCLUDE dimensions
           sum(amount) as amount_at_finer_grain
    from orders
    where <extract, data source, context, and the dimension filters>
    group by region, product_id
)
select region,                             -- back to the view's grain
       avg(amount_at_finer_grain) as metric
from finer
group by region;
```

`INCLUDE` exists for this shape: an average of per-product totals within a
region, which is not the average of the region's rows. The outer aggregate is
the whole point of the expression, so writing it down is not optional.

Unlike `FIXED`, the dimension filters belong in the inner query here, because
`INCLUDE` is evaluated after them.

## `EXCLUDE` as a query

The view's dimensions minus the excluded ones, joined back to the view's grain:

```sql
with coarser as (
    select region,                         -- view dimensions minus EXCLUDE dimensions
           sum(amount) as region_total
    from orders
    where <extract, data source, context, and the dimension filters>
    group by region
)
select o.region, o.order_month,            -- the view's grain
       sum(o.amount) / min(c.region_total) as share_of_region
from orders o
join coarser c on c.region = o.region
where <the same dimension filters>
group by o.region, o.order_month;
```

The usual purpose is a share or an index: a part over a total that is deliberately
coarser than the sheet. `min` carries the region total down without multiplying
it, which is the same trick as `MIN` on the shelf.

## Nesting, and where to stop

A level-of-detail expression can contain another, and the inner one's grain is
not the outer one's. This is expressible in SQL as a subquery over a subquery,
and the translation is mechanical, but the number of grains that have to be
stated grows with it.

Two nested grains plus a view grain plus filter positions is about the point
where a reviewer cannot hold the whole thing, and where a translated query stops
being evidence of anything. When a metric needs that much nesting, the useful
answer is usually that the shape belongs in a model the warehouse computes once,
not in a workbook calculation — which is a recommendation to hand back, not
something to resolve by writing a longer expression.
