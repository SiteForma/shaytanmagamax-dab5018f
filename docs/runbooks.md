# Runbooks

## Failed upload processing

1. Open `/uploads` and inspect the file lifecycle state.
2. Open `/mapping` if the file is stuck in `mapping_required`.
3. Check `/quality` for blocking issues.
4. Open `/admin` and inspect recent jobs and audit events.
5. If validation/apply failed and the job is retryable, use admin retry.

## Failed export job

1. Open `/admin` and inspect the export jobs panel.
2. Check status and `error_message`.
3. Inspect the linked `generate_export` job in the jobs panel.
4. Verify `EXPORT_ROOT` exists and is writable.
5. If async exports are enabled, confirm worker and Redis are healthy.
6. Confirm the user still has `exports:download`.
7. Use admin retry for the failed export job when the error is infrastructural and retry-safe.

## Worker / queue incident

1. Open `/admin` and filter jobs by queue: `ingestion`, `analytics`, `exports`.
2. Check whether failures are isolated to one queue or systemic.
3. Verify the worker process is running through `dramatiq apps.worker.worker_app.tasks`.
4. Verify Redis reachability from the API and worker hosts.
5. If only exports are blocked, check `EXPORT_ASYNC_ENABLED` and export backlog counters.
6. Use retry only after the infrastructure fault is removed.

## Reserve run debugging

1. Reproduce the calculation from `/reserve`.
2. Inspect the persisted run and row explanation payloads.
3. Check current stock, inbound, DIY policy, and recent uploads.
4. Use `/admin/audit-events` filtered by `reserve.run_created`.
5. If the output looks stale, inspect freshness on `/admin`.

## Stale data investigation

1. Open `/admin` freshness panel.
2. Check last sales ingest, stock snapshot, inbound update, and reserve refresh.
3. Inspect failed/pending jobs.
4. Verify recent uploads reached `applied` or `applied_with_warnings`.
5. If analytics are stale, retry `refresh_analytics` if available.

## Staging / production posture check

1. Run `make compose-up`.
2. Run `make migrate-staging`.
3. Run `make seed-staging` only for local/staging fixture data, never for real production.
4. Start API with `make api-staging`.
5. Start worker with `make worker-staging`.
6. Check `curl -f http://127.0.0.1:8011/api/health/ready`.
7. Open `/admin` and inspect environment warnings.
8. Confirm `Schema mode` is `migrations_only`.
9. Confirm `Export async` is enabled for large artifacts.
10. Confirm `Sentry` and `OpenTelemetry` are initialized in non-local environments.
11. Confirm worker queues are listed and the worker process is live.

If readiness is `not_ready`, inspect these fields first:

- `configuration_errors`
- `redis_ok`
- `object_storage_ok`
- `analytics_ok`
- `observability.sentry_initialized`
- `observability.otel_initialized`

## Permission issue debugging

1. Confirm the user role on `/admin`.
2. Inspect the capability list for that user.
3. Reproduce the action and capture the returned `request_id`.
4. Search `/admin/audit-events` for `auth.permission_denied`.
5. If the user needs broader access, change the role from the admin panel.

## Object storage issue basics

1. Verify `OBJECT_STORAGE_MODE`.
2. For local mode, check `LOCAL_OBJECT_STORAGE_ROOT`.
3. For S3 mode, check endpoint, bucket, and credentials.
4. Validate that uploaded objects and export artifacts are actually present.

## Worker backlog basics

1. Open `/admin` and inspect pending/failed jobs counts.
2. Verify Redis connectivity and worker process status.
3. Separate whether backlog is in `ingestion`, `analytics`, or `exports`.
4. Retry only supported safe jobs.
5. If upload lifecycle is blocked, inspect audit events plus the specific upload file detail.
6. If export backlog grows, lower sync usage and confirm `EXPORT_ASYNC_ENABLED=true`.
