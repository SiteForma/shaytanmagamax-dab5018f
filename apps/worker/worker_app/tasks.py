from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import boto3
import dramatiq

from apps.api.app.common.utils import utc_now
from apps.api.app.core.config import Settings, get_settings
from apps.api.app.core.request_context import bind_job_context, reset_context
from apps.api.app.db.models import JobRun
from apps.api.app.db.session import SessionLocal
from apps.api.app.modules.analytics.service import materialize_analytics
from apps.api.app.modules.inbound.service import sync_inbound_google_sheet
from apps.api.app.modules.uploads.service import (
    apply_upload,
    suggest_upload_mapping,
    validate_upload_file,
)
from apps.worker.worker_app import broker as _broker  # noqa: F401

DUCKDB_BACKUP_PREFIX = "backups/duckdb/"
DUCKDB_BACKUP_RETENTION_DAYS = 7


@dramatiq.actor(queue_name="ingestion")
def process_upload_batch(batch_id: str) -> dict[str, object]:
    tokens = bind_job_context(job_id=f"upload_batch:{batch_id}")
    settings = get_settings()
    try:
        with SessionLocal() as db:
            result = apply_upload(db, settings, batch_id)
            return result.model_dump()
    finally:
        reset_context(tokens)


@dramatiq.actor(queue_name="ingestion")
def suggest_upload_mapping_job(file_id: str) -> dict[str, object]:
    tokens = bind_job_context(job_id=f"suggest_mapping:{file_id}")
    settings = get_settings()
    try:
        with SessionLocal() as db:
            result = suggest_upload_mapping(db, settings, file_id)
            return result.model_dump()
    finally:
        reset_context(tokens)


@dramatiq.actor(queue_name="ingestion")
def validate_upload_file_job(file_id: str) -> dict[str, object]:
    tokens = bind_job_context(job_id=f"validate_upload:{file_id}")
    settings = get_settings()
    try:
        with SessionLocal() as db:
            result = validate_upload_file(db, settings, file_id)
            return result.model_dump()
    finally:
        reset_context(tokens)


@dramatiq.actor(queue_name="analytics")
def refresh_analytics() -> dict[str, str]:
    tokens = bind_job_context(job_id="refresh_analytics")
    settings = get_settings()
    try:
        with SessionLocal() as db:
            materialize_analytics(db, settings)
        return {"status": "ok"}
    finally:
        reset_context(tokens)


@dramatiq.actor(queue_name="exports")
def generate_export_job(export_job_id: str, job_run_id: str | None = None) -> dict[str, object]:
    from apps.api.app.modules.exports.service import process_export_job

    tokens = bind_job_context(job_id=job_run_id or export_job_id)
    settings = get_settings()
    try:
        with SessionLocal() as db:
            result = process_export_job(
                db, settings, export_job_id=export_job_id, job_run_id=job_run_id
            )
            return result.model_dump()
    finally:
        reset_context(tokens)


@dramatiq.actor(queue_name="inbound")
def sync_inbound_google_sheet_job() -> dict[str, object]:
    tokens = bind_job_context(job_id="sync_inbound_google_sheet")
    settings = get_settings()
    try:
        with SessionLocal() as db:
            job_run = JobRun(
                job_name="sync_inbound_google_sheet",
                queue_name="inbound",
                status="running",
                started_at=utc_now(),
            )
            db.add(job_run)
            db.commit()
            try:
                result = sync_inbound_google_sheet(db, settings)
                refreshed = db.get(JobRun, job_run.id)
                if refreshed is not None:
                    refreshed.status = "completed"
                    refreshed.finished_at = utc_now()
                    refreshed.payload = result.model_dump()
                    db.commit()
                return result.model_dump()
            except Exception as exc:
                refreshed = db.get(JobRun, job_run.id)
                if refreshed is not None:
                    refreshed.status = "failed"
                    refreshed.finished_at = utc_now()
                    refreshed.error_message = str(exc)
                    db.commit()
                raise
    finally:
        reset_context(tokens)


def _should_backup_duckdb(settings: Settings) -> bool:
    return settings.object_storage_mode != "local" or bool(settings.local_object_storage_root)


def _s3_client(settings: Settings) -> Any:
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )


def _upload_duckdb_backup(settings: Settings, source_path: Path, object_key: str) -> None:
    if settings.object_storage_mode == "local":
        destination = Path(settings.local_object_storage_root) / object_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        return

    with source_path.open("rb") as backup_file:
        _s3_client(settings).put_object(
            Bucket=settings.s3_bucket,
            Key=object_key,
            Body=backup_file,
        )


def _cleanup_local_duckdb_backups(settings: Settings, cutoff_seconds: float) -> int:
    backup_root = Path(settings.local_object_storage_root) / DUCKDB_BACKUP_PREFIX
    if not backup_root.exists():
        return 0
    deleted = 0
    for backup_path in backup_root.glob("*.duckdb"):
        if backup_path.stat().st_mtime < cutoff_seconds:
            backup_path.unlink()
            deleted += 1
    return deleted


def _cleanup_s3_duckdb_backups(settings: Settings, cutoff: datetime) -> int:
    client = _s3_client(settings)
    deleted = 0
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.s3_bucket, Prefix=DUCKDB_BACKUP_PREFIX):
        objects = [
            {"Key": item["Key"]}
            for item in page.get("Contents", [])
            if item.get("LastModified") is not None and item["LastModified"] < cutoff
        ]
        if not objects:
            continue
        client.delete_objects(Bucket=settings.s3_bucket, Delete={"Objects": objects})
        deleted += len(objects)
    return deleted


def _cleanup_duckdb_backups(settings: Settings) -> int:
    cutoff = utc_now() - timedelta(days=DUCKDB_BACKUP_RETENTION_DAYS)
    if settings.object_storage_mode == "local":
        return _cleanup_local_duckdb_backups(settings, cutoff.timestamp())
    return _cleanup_s3_duckdb_backups(settings, cutoff)


@dramatiq.actor(queue_name="maintenance")
def backup_duckdb() -> dict[str, object]:
    tokens = bind_job_context(job_id="backup_duckdb")
    settings = get_settings()
    try:
        if not _should_backup_duckdb(settings):
            return {"status": "skipped", "reason": "object_storage_not_configured"}

        duckdb_path = Path(settings.duckdb_path)
        if not duckdb_path.exists():
            return {"status": "skipped", "reason": "duckdb_missing", "path": str(duckdb_path)}

        timestamp = utc_now().strftime("%Y-%m-%d_%H-%M")
        object_key = f"{DUCKDB_BACKUP_PREFIX}{timestamp}.duckdb"
        temp_dir = Path(settings.export_root) / "tmp" / "duckdb-backups"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / f"{timestamp}.duckdb"

        shutil.copy2(duckdb_path, temp_path)
        try:
            _upload_duckdb_backup(settings, temp_path, object_key)
        finally:
            temp_path.unlink(missing_ok=True)

        deleted = _cleanup_duckdb_backups(settings)
        return {"status": "ok", "storage_key": object_key, "deleted_old_backups": deleted}
    finally:
        reset_context(tokens)
