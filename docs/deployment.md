# Deployment

## Modes

The product currently supports three clear postures:

- `development`
- `test`
- `production`

## Required environment variables

Core:

- `APP_ENV`
- `APP_RELEASE`
- `DATABASE_URL`
- `JWT_SECRET`
- `CORS_ORIGINS`
- `STARTUP_SCHEMA_MODE`

Analytics and storage:

- `DUCKDB_PATH`
- `PARQUET_ROOT`
- `OBJECT_STORAGE_MODE`
- `LOCAL_OBJECT_STORAGE_ROOT` or S3-compatible settings
- `EXPORT_ROOT`
- `EXPORT_ASYNC_ENABLED`
- `EXPORT_ASYNC_ROW_THRESHOLD`
- `INBOUND_GOOGLE_SHEET_ID`
- `INBOUND_GOOGLE_SHEET_GID`
- optional `INBOUND_GOOGLE_SHEET_EXPORT_URL`
- `INBOUND_GOOGLE_SHEET_SYNC_HOUR_MOSCOW`

Assistant:

- `ASSISTANT_PROVIDER`
- `ASSISTANT_LLM_ENABLED`
- optional OpenAI-compatible settings if enabled

Observability:

- optional `SENTRY_DSN`
- optional `SENTRY_TRACES_SAMPLE_RATE`
- optional `OTEL_ENABLED`
- optional `OTEL_SERVICE_NAME`
- optional `OTEL_EXPORTER_OTLP_ENDPOINT`

## Production-like recommendations

- disable dev auth fallback and require real sessions
- set a real `JWT_SECRET`
- use Postgres rather than SQLite
- point object storage to S3-compatible infrastructure
- keep `EXPORT_ROOT` on durable storage if using local mode
- configure CORS to the deployed frontend origin only
- rotate assistant/provider secrets outside the repo
- enable async export flow for large artifacts
- run a dedicated worker process for `ingestion`, `analytics` and `exports`
- run `python -m apps.worker.worker_app.scheduler` if daily Google Sheet inbound sync is enabled
- enable Sentry and OpenTelemetry before daily production operations
- keep FastAPI runtime migrations-only: application startup must not create or mutate schema

## Staging / production posture

Recommended staging-like baseline:

- `APP_ENV=production`
- `STARTUP_SCHEMA_MODE=migrations_only`
- `STARTUP_SEED_SAMPLE_DATA=false`
- `STARTUP_MATERIALIZE_ANALYTICS=false`
- `EXPORT_ASYNC_ENABLED=true`
- `SENTRY_DSN` configured
- `OTEL_ENABLED=true`
- `OTEL_EXPORTER_OTLP_ENDPOINT` configured
- `OBJECT_STORAGE_MODE=s3`
- worker process running continuously

Local staging-like ports from `infrastructure/docker/docker-compose.yml`:

- Postgres: `localhost:15432`
- Redis: `localhost:16379`
- MinIO S3: `localhost:19000`
- MinIO console: `localhost:19001`
- OTLP HTTP collector: `localhost:14318`

Recommended production runtime commands:

```bash
alembic upgrade head
uvicorn apps.api.app.main:app --host 0.0.0.0 --port 8000
dramatiq apps.worker.worker_app.tasks
python -m apps.worker.worker_app.scheduler
```

Local staging-like verification:

```bash
make compose-up
make migrate-staging
make seed-staging
make api-staging
make worker-staging
curl -f http://127.0.0.1:8011/api/health/ready
```

## Startup validation

Settings are centralized in `apps/api/app/core/config.py`.

The app now boots through FastAPI lifespan initialization without implicit schema creation.
Optional seed/materialization startup switches are non-production only and should stay disabled in staging/production.

Для production:

1. выставить `APP_ENV=production`
2. выставить `STARTUP_SCHEMA_MODE=migrations_only`
3. применять схему только через Alembic, например `alembic upgrade head`
4. не использовать implicit `create_all`

Это означает, что production boot больше не должен модифицировать схему автоматически.

## Production config validation

`Settings.validate_for_startup()` blocks production startup when unsafe settings are detected:

- `APP_DEBUG=true`
- SQLite `DATABASE_URL`
- default or short `JWT_SECRET`
- local default dev admin credentials
- non-`migrations_only` schema mode
- startup seed/materialization enabled
- missing Redis
- sync-only exports
- non-S3 object storage
- missing Sentry DSN
- disabled OpenTelemetry or missing OTLP endpoint
- missing `APP_RELEASE`
