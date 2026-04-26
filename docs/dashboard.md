# Dashboard

The executive dashboard reads from persisted reserve runs and upload quality metadata. It does not calculate reserve logic inline in controller code.

## Backend endpoints

- `GET /api/dashboard/summary`
- `GET /api/dashboard/top-risk-skus`
- `GET /api/dashboard/exposed-clients`
- `GET /api/dashboard/coverage-distribution`
- `GET /api/dashboard/inbound-vs-shortage`
- `GET /api/dashboard/freshness`
- `GET /api/dashboard/overview`

## Data sources

Dashboard aggregates currently combine:

- latest matching portfolio `ReserveRun`
- persisted `ReserveRow` dataset
- `UploadBatch` freshness
- open `QualityIssue` counters
- inbound timeline from `InboundDelivery`

## Implemented aggregates

### Summary

- tracked SKUs
- active DIY clients
- positions at risk
- total shortage quantity
- inbound quantity within horizon
- average coverage months
- open quality issues
- freshness hours

### Top risk SKUs

- `sku_code`
- `product_name`
- `affected_clients_count`
- `shortage_qty_total`
- `min_coverage_months`
- `worst_status`
- `category_name`

### Exposed clients

- `client_name`
- `positions_tracked`
- `critical_positions`
- `warning_positions`
- `shortage_qty_total`
- `avg_coverage_months`
- `inbound_relief_qty`

### Coverage distribution

Buckets:

- `no_history`
- `under_1m`
- `between_1m_and_target`
- `healthy`
- `overstocked`

### Freshness

Freshness is based on the most recent timestamp between:

- latest reserve run
- latest upload batch

Open quality issues are surfaced alongside freshness so stale or dirty data is visible at the top level.

## Trade-offs

- The dashboard reuses persisted reserve runs instead of recomputing on every widget call.
- Heavy historical trend visualization is intentionally deferred; Phase 3 focuses on operational summaries and drill-down readiness.
- Current implementation uses PostgreSQL/SQLite transactional reads plus persisted reserve outputs. DuckDB/Parquet remain available for later heavier analytics workloads.
