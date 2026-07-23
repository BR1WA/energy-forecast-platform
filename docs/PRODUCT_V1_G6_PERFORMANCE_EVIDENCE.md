# Product V1 G6 performance evidence

**Measured:** 2026-07-23
**Database:** isolated PostgreSQL 16 container
**Fixture:** 20,000 one-minute readings, 600 forecasts (half 24-point and half
168-point), 1,000 alerts, one owned site and primary meter
**Method:** one warm-up followed by 12 measured executions; SQLAlchemy statement
events counted database round trips. The repeatable harness is
`backend/scripts/measure_g6_performance.py`.

| Surface | p50 ms | p95 ms | Queries |
|---|---:|---:|---:|
| Forecast history before composite index | 5.83 | 6.98 | 2 |
| Dashboard batch | 41.24 | 42.97 | 10 |
| Consumption 30-day range | 536.13 | 564.91 | 8 |
| Raw readings page (200) | 16.55 | 18.46 | 3 |
| Reports summary | 44.65 | 96.07 | 6 |
| Forecast history after composite index | 4.91 | 7.42 | 2 |
| Alert worker pass | 10.63 | 11.58 | 8 |
| Complete account ZIP export | 696.37 | 733.22 | 14 |

The raw-reading endpoint is cursor-paginated and capped at 200 rows. Consumption
range processing uses `yield_per(1000)`, account readings use `yield_per(1000)`,
forecast export uses `yield_per(200)`, and the archive spills beyond 8 MiB instead
of retaining an unbounded byte buffer. Reports now calculate the exact all-time
forecast count while loading at most 500 recent prediction arrays for peak
statistics. A dashboard request does not enumerate forecast history; the 168-point
rows in this fixture did not materially affect its bounded latest-forecast query.

`EXPLAIN (ANALYZE, BUFFERS)` evidence:

- With the fixture's final statistics, the 20,000-row reading range used
  `ix_smart_meter_readings_meter_id` followed by a sort; PostgreSQL execution time
  was 12.429 ms. An earlier run selected the existing unique meter/timestamp index,
  so no additional speculative reading index was added.
- Before the composite forecast index, history used a sequential scan and sort
  (0.222 ms execution for 20 rows). After migration it used a backward index-only
  scan on `ix_forecasts_user_created` (0.089 ms execution).
- The migration also adds `ix_alerts_user_created` for the measured recent-alert
  ordering pattern. No aggregation table was added.

The forecast endpoint's wall-clock p95 varied upward in this local run despite the
improved database plan, so this evidence does not claim a latency gain. It does show
bounded query counts, bounded result materialization, and removal of the sequential
history scan.

These are controlled single-machine measurements, not production SLOs. Re-run the
harness on the deployment hardware before setting an external latency commitment.
