# Shaytan Machine

MAGAMAX internal analytics platform for reserve coverage, stock risk, inbound visibility, ingestion traceability, and future assistant workflows.

## Repo layout

- `apps/web` — premium React + Vite frontend shell, progressively integrated with real API endpoints
- `apps/api` — FastAPI modular monolith with domain services, reserve engine, ingestion foundation, auth, and analytics materialization
- `apps/worker` — Dramatiq worker entrypoints for ingestion and analytics refresh jobs
- `packages/shared-types` — shared TypeScript domain types
- `packages/shared-contracts` — shared API contract helpers
- `infrastructure/docker` — local Postgres, Redis, MinIO stack
- `infrastructure/scripts` — seed/bootstrap helpers
- `data/sample` — sample source files
- `data/fixtures` — test fixtures
- `docs` — architecture and product docs

## Quick start

```bash
cp .env.example .env
make install
make compose-up
make migrate
make seed
make api
make worker
make web
```

Frontend runs on `http://127.0.0.1:8090`, API on `http://127.0.0.1:8000`.
The local Docker stack maps Postgres/Redis/MinIO to non-conflicting host ports:
`15432`, `16379`, `19000`, and MinIO console `19001`.

For the local premium shell, the frontend uses `X-Dev-User: user_admin` in development so protected write endpoints work without adding a temporary login screen.

## Local roles

The seed now creates four local users with role-aware capabilities:

- `admin@magamax.local` — `admin`
- `operator@magamax.local` — `operator`
- `analyst@magamax.local` — `analyst`
- `viewer@magamax.local` — `viewer`

The admin and operator roles can open the operational admin surface at `http://127.0.0.1:8090/admin`. The admin role can also manage user roles.

## Phase 6 additions

- role/capability-aware backend authorization
- audit trail for critical mutations and operational actions
- export subsystem for reserve, stock coverage, dashboard top-risk, and quality issues
- admin/operator APIs and UI for users, jobs, exports, freshness, and audit events
- request-id-based error envelopes and stricter production route protection

## Operational posture

- `make worker` now runs the real Dramatiq worker entrypoint for `ingestion`, `analytics`, and `exports`
- long-running export jobs can be queued and later retried from `/admin`
- production should run with `APP_ENV=production` and `STARTUP_SCHEMA_MODE=migrations_only`
- production schema changes should be applied only through Alembic migrations
- FastAPI startup no longer performs implicit schema creation; run `make migrate` or `make migrate-staging`
- staging-like local posture is available through `.env.staging.example`, `make api-staging`, and `make worker-staging`
- Sentry and OpenTelemetry are real runtime integrations, but require the declared observability packages to be installed and real production DSN/OTLP values to be supplied
