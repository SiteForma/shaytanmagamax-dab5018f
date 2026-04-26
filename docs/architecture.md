# Architecture Overview

`Shaytan Machine` is implemented as a modular monolith:

- `apps/web` keeps the premium MAGAMAX frontend shell and consumes stable REST APIs through a compatibility layer.
- `apps/api` owns the domain model, transactional database access, reserve engine, ingestion orchestration, auth foundation, and dashboard reads.
- `apps/worker` owns async execution boundaries for ingestion/apply and analytics refresh jobs via Dramatiq.
- PostgreSQL is the source of truth for transactional facts and audit records.
- DuckDB + Parquet provide a lightweight analytical layer for future heavier summaries and assistant context assembly.

The backend is intentionally split by domain module, not by technical layer alone. Controllers stay thin; business logic sits in services and the reserve engine.
