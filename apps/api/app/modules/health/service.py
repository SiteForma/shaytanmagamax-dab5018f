from __future__ import annotations

from pathlib import Path

import duckdb
import redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.app.core.config import Settings
from apps.api.app.core.observability import observability_status
from apps.api.app.modules.uploads.storage import get_object_storage


def probe_database(db: Session) -> tuple[bool, str]:
    try:
        db.execute(text("select 1"))
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def probe_redis(settings: Settings) -> tuple[bool, str]:
    if not settings.redis_url:
        return True, "disabled"
    try:
        client = redis.Redis.from_url(settings.redis_url)
        client.ping()
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def probe_object_storage(settings: Settings) -> tuple[bool, str]:
    try:
        return get_object_storage(settings).healthcheck()
    except Exception as exc:
        return False, str(exc)


def probe_analytics(settings: Settings) -> tuple[bool, dict[str, object]]:
    parquet_root = Path(settings.parquet_root)
    duckdb_path = Path(settings.duckdb_path)
    try:
        parquet_root.mkdir(parents=True, exist_ok=True)
        duckdb_path.parent.mkdir(parents=True, exist_ok=True)
        with duckdb.connect(str(duckdb_path)) as conn:
            conn.execute("select 1")
        return True, {
            "duckdb_path": str(duckdb_path),
            "parquet_root": str(parquet_root),
            "parquet_root_exists": parquet_root.exists(),
        }
    except Exception as exc:
        return False, {
            "duckdb_path": str(duckdb_path),
            "parquet_root": str(parquet_root),
            "parquet_root_exists": parquet_root.exists(),
            "error": str(exc),
        }


def collect_readiness(db: Session, settings: Settings) -> dict[str, object]:
    database_ok, database_detail = probe_database(db)
    redis_ok, redis_detail = probe_redis(settings)
    object_storage_ok, object_storage_detail = probe_object_storage(settings)
    analytics_ok, analytics_detail = probe_analytics(settings)
    observability = observability_status(settings)
    configuration_errors = settings.production_startup_errors()
    configuration_ok = not configuration_errors
    ready = (
        database_ok
        and redis_ok
        and object_storage_ok
        and analytics_ok
        and configuration_ok
        and bool(observability["observability_ok"])
    )
    return {
        "status": "ready" if ready else "not_ready",
        "configuration_ok": configuration_ok,
        "configuration_errors": configuration_errors,
        "database": "ok" if database_ok else "error",
        "database_ok": database_ok,
        "database_detail": database_detail,
        "redis_configured": bool(settings.redis_url),
        "redis_ok": redis_ok,
        "redis_detail": redis_detail,
        "object_storage_mode": settings.object_storage_mode,
        "object_storage_ok": object_storage_ok,
        "object_storage_detail": object_storage_detail,
        "analytics_ok": analytics_ok,
        "analytics": analytics_detail,
        "observability": observability,
        "startup_schema_mode": settings.startup_schema_mode,
        "export_async_enabled": settings.export_async_enabled,
    }
