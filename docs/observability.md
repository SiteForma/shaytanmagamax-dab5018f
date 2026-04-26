# Observability

## Structured logging

Backend logging настраивается через `apps/api/app/core/logging.py`.

Каждая запись лога несёт:

- timestamp
- level
- logger
- message
- request id из request context
- trace id
- job id для worker/job execution path

## Correlation и traceability

API middleware добавляет `X-Request-Id` в каждый request/response.
Также прокидывается `X-Trace-Id`, а для фоновых задач создаётся job-bound trace context.

Этот id используется в:

- error envelopes
- audit events
- backend logs

Дополнительно по доменным операциям используются:

- upload file ids
- upload batch ids
- reserve run ids
- export job ids
- assistant session/message ids
- job run ids

Это позволяет связать:

- API request
- audit event
- export job
- worker execution
- failed retry path

## Sentry

Реальная интеграция включается через:

- `SENTRY_DSN`
- `SENTRY_TRACES_SAMPLE_RATE`
- `APP_RELEASE`

Sentry инициализируется и для API, и для worker-процесса, но только если DSN задан.
В production отсутствие DSN блокирует startup config validation.

## OpenTelemetry

OpenTelemetry включается через:

- `OTEL_ENABLED`
- `OTEL_SERVICE_NAME`
- `OTEL_EXPORTER_OTLP_ENDPOINT`
- `APP_RELEASE`

Поведение:

- API получает FastAPI + SQLAlchemy instrumentation
- worker получает отдельный service name с суффиксом `-worker`
- если OTLP endpoint не задан, используется console exporter для локальной отладки
- в production `OTEL_ENABLED=true` и `OTEL_EXPORTER_OTLP_ENDPOINT` обязательны

Локальный staging-like stack включает OpenTelemetry Collector:

- OTLP HTTP: `http://localhost:14318/v1/traces`
- OTLP gRPC: `localhost:14317`

Если Sentry или OTel включены, но runtime-зависимости не установлены, readiness становится `not_ready`, а причина видна в `observability` блоке `/api/health/ready`.

## Error envelopes

Все доменные и HTTP ошибки возвращаются в стабильном JSON envelope:

- `code`
- `message`
- `request_id`
- `details`

Неожиданные исключения нормализуются в `internal_error` и не раскрывают stack trace клиенту.

## Operational visibility

Сейчас отдельно наблюдаемы:

- API errors
- upload/validation/apply failures
- reserve failures
- export failures
- assistant/provider failures
- permission denials
- job backlog через admin surface
- deployment posture warnings через admin health details

## Extension points

Следующий слой можно добавить без рефакторинга архитектуры:

- metrics emission
- latency histograms
- production Sentry project/DSN and release management
- distributed trace propagation outside одного процесса
