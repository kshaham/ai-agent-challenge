# Meridian Query Language (MQL)

MQL is Meridian's SQL-like language for querying time series.

## Basic query

    SELECT mean(value) FROM cpu WHERE time > now() - 1h GROUP BY time(5m)

This selects the mean of the `value` field from the `cpu` measurement over the
last hour, grouped into 5-minute buckets.

## Aggregation functions

Meridian supports `mean`, `max`, `min`, `sum`, `count`, and `percentile`. The
`percentile` function takes the field and a percentile between 0 and 100, for
example `percentile(value, 95)`.

## Time ranges

Use `now()` and duration literals such as `1h`, `7d`, or `30d` to express relative
time ranges in the `WHERE` clause.
