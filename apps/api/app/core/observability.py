from __future__ import annotations

import logging

from fastapi import FastAPI
from sqlalchemy.engine import Engine

from apps.api.app.core.config import Settings

logger = logging.getLogger(__name__)
_sentry_initialized = False
_otel_initialized = False
_sentry_error: str | None = None
_otel_error: str | None = None


def configure_observability(app: FastAPI, settings: Settings, engine: Engine) -> None:
    _configure_sentry(settings)
    _configure_opentelemetry(app, settings, engine, service_name=settings.otel_service_name)


def configure_worker_observability(settings: Settings, engine: Engine) -> None:
    _configure_sentry(settings)
    _configure_opentelemetry(
        None, settings, engine, service_name=f"{settings.otel_service_name}-worker"
    )


def _configure_sentry(settings: Settings) -> None:
    global _sentry_initialized, _sentry_error
    if _sentry_initialized or not settings.sentry_dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.app_env,
            release=settings.app_release,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
            send_default_pii=False,
        )
        _sentry_initialized = True
        _sentry_error = None
        logger.info("sentry_initialized")
    except Exception as exc:  # pragma: no cover - depends on optional runtime infra
        _sentry_error = str(exc)
        logger.exception("sentry_initialization_failed")


def _configure_opentelemetry(
    app: FastAPI | None,
    settings: Settings,
    engine: Engine,
    *,
    service_name: str,
) -> None:
    global _otel_initialized, _otel_error
    if _otel_initialized or not settings.otel_enabled:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

        resource_payload = {"service.name": service_name}
        if settings.app_release:
            resource_payload["service.version"] = settings.app_release
        resource = Resource.create(resource_payload)
        provider = TracerProvider(resource=resource)
        exporter = (
            OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
            if settings.otel_exporter_otlp_endpoint
            else ConsoleSpanExporter()
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        if app is not None:
            FastAPIInstrumentor.instrument_app(app)
        SQLAlchemyInstrumentor().instrument(engine=engine)
        _otel_initialized = True
        _otel_error = None
        logger.info("otel_initialized", extra={"service_name": service_name})
    except Exception as exc:  # pragma: no cover - depends on optional runtime infra
        _otel_error = str(exc)
        logger.exception("otel_initialization_failed")


def observability_status(settings: Settings) -> dict[str, object]:
    sentry_required = settings.app_env == "production" and bool(settings.sentry_dsn)
    otel_required = settings.app_env == "production" and settings.otel_enabled
    sentry_ok = not sentry_required or _sentry_initialized
    otel_ok = not otel_required or _otel_initialized
    return {
        "sentry_enabled": bool(settings.sentry_dsn),
        "sentry_initialized": _sentry_initialized,
        "sentry_error": _sentry_error,
        "otel_enabled": settings.otel_enabled,
        "otel_initialized": _otel_initialized,
        "otel_error": _otel_error,
        "observability_ok": sentry_ok and otel_ok,
    }
