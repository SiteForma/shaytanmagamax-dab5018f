from __future__ import annotations

import dramatiq

from apps.api.app.common.utils import utc_now
from apps.api.app.core.config import get_settings
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
            result = process_export_job(db, settings, export_job_id=export_job_id, job_run_id=job_run_id)
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
