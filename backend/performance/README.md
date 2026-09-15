# Performance Testing

This directory contains deterministic PostgreSQL storage query-plan tooling.

## Layout

- `query_plans/`: deterministic PostgreSQL seed data, public storage method discovery, real
  SQLAlchemy runtime SQL capture, EXPLAIN runner, thresholds, and report rendering.
- `reports/`: generated query-plan reports.
- `../scripts/`: shell entrypoints used by Make targets.

## Public API Smoke Coverage

Deterministic public read-path coverage lives in the backend integration test suite. It exercises
the real Litestar routes, middleware, Dishka providers, response schemas, and PostgreSQL storages
with seeded published content:

```bash
make test-backend-integration
```

This is a functional wiring and contract check. It intentionally does not impose HTTP throughput or
latency thresholds.

## Query Plan Checks

Use the query-plan harness when changing PostgreSQL storages, query shapes, seed-sensitive indexes,
or performance thresholds. It starts or reuses the test database, migrates it, clears the
benchmarked tables, seeds a deterministic selected-profile dataset, discovers every public async
`*DatabaseStorage` method under PostgreSQL storages, runs registered deterministic scenarios for
those methods, captures the SQL actually emitted through SQLAlchemy engine events, then runs:

```sql
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON)
```

```bash
make query-plans-realistic
make query-plans-stress
```

`realistic` is the required regression gate on `main`; `stress` is a manual capacity diagnostic.
Both use three EXPLAIN runs, keep about 80% of articles published, and place deterministic full-text
matches in 1% of articles. Every matching article is published. The harness runs `VACUUM ANALYZE`
after seeding and before measuring plans.

The EXPLAIN session uses an explicit `work_mem` budget (`16MB` for `realistic`, `64MB` for
`stress`) so temp-block findings are reproducible instead of depending on the PostgreSQL host
default. Any temp read or write block remains blocking after that profile budget is applied.

Local `stress` runs start an isolated disk-backed PostgreSQL container on port `55433` by default
and remove it on exit; this avoids the intentionally RAM-backed general test database running out
of space. Override that port with `QUERY_PLANS_STRESS_DB_PORT`. GitHub Actions reuses its dedicated
job service instead. `realistic` continues to start or reuse the normal test database.

| Domain volumes | `realistic` | `stress` |
|---|---:|---:|
| Users / auth sessions | 100 / 500 | 10k / 50k |
| Article folders / articles | 20 / 5k | 200 / 200k |
| Tags / article-tag links | 500 / 20k | 30k / 500k |
| Daily analytics / reactions | 100k / 10k | 2m / 500k |
| Matrix items / resources / links | 10k / 5k / 25k | 200k / 200k / 500k |
| Queued questions / Agent audit events | 5k / 10k | 50k / 250k |
| Matrix sheets × sections × subsections | 20 × 8 × 12 | 20 × 8 × 12 |

The gate fails when a discovered public storage method has no scenario, a scenario captures no SQL,
or the plan uses temp blocks. Missing configured indexes and forbidden sequential scans block at
relation cardinalities of 1,000 rows or more and are observations below that boundary. `realistic`
also blocks on its absolute latency SLA; `stress` reports SLA overruns as observations while keeping
plan-shape and temp-block checks strict. Mutating statements are explained in rollback-only
transactions, and statements from the same storage scenario are replayed as a group so dependent
ORM flush/selectinload/merge SQL remains explainable.

The absolute query-group ceilings remain 25/250/150/250/100/300 ms. Until a calibrated baseline is
committed, `realistic` uses those ceilings directly. To prepare the relative gate, download exactly
five `realistic` `summary.json` artifacts produced from the same GitHub SHA, then run:

```bash
make query-plans-baseline-candidate \
  QUERY_PLAN_BASELINE_SOURCE_SHA=<sha> \
  QUERY_PLAN_BASELINE_OUTPUT=performance/query_plans/realistic-baseline.json \
  QUERY_PLAN_BASELINE_SUMMARY_1=/tmp/run-1/summary.json \
  QUERY_PLAN_BASELINE_SUMMARY_2=/tmp/run-2/summary.json \
  QUERY_PLAN_BASELINE_SUMMARY_3=/tmp/run-3/summary.json \
  QUERY_PLAN_BASELINE_SUMMARY_4=/tmp/run-4/summary.json \
  QUERY_PLAN_BASELINE_SUMMARY_5=/tmp/run-5/summary.json
```

The candidate generator rejects non-`realistic` samples, any sample count other than five, and
different query sets. It stores profile, source SHA, sample count, and the median of the five warm
medians for each query. Once committed, the effective `realistic` threshold becomes
`min(SLA, max(2 × baseline, baseline + 20 ms))`; missing or stale query names then fail the run.

Reports are written to `backend/performance/reports/query-plans/<timestamp>/`:

- `summary.md`
- `summary.json`
- one directory per query with `compiled.sql`, `params.json`, and `explain-run-*.json`

`summary.md` and `summary.json` include the full relation-cardinality map, timing mode, storage
coverage, scenario-to-method metadata, captured SQL counts, warm median EXPLAIN timings, SLA,
baseline, effective threshold, overrun flag, and separate blocking findings and observations.

## Useful Environment Values

- `PERFORMANCE_REPORT_DIR`: report output directory, relative to `backend/` when using Make.

## Additional Details

The query-plan Make targets prepare the backend uv environment and test PostgreSQL, then write
timestamped reports.

References:
