from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime

from fastapi import UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, object_session

from apps.api.app.common.utils import generate_id, utc_now
from apps.api.app.core.config import Settings
from apps.api.app.core.errors import DomainError
from apps.api.app.db.models import (
    Category,
    Client,
    DataSource,
    DiyPolicy,
    InboundDelivery,
    JobRun,
    Product,
    QualityIssue,
    SalesFact,
    Sku,
    StockSnapshot,
    UploadBatch,
    UploadedRowIssue,
    User,
)
from apps.api.app.db.models import UploadFile as UploadFileModel
from apps.api.app.modules.analytics.service import materialize_analytics
from apps.api.app.modules.catalog.brand import resolve_brand
from apps.api.app.modules.catalog.cost_import import import_sku_costs_from_upload
from apps.api.app.modules.mapping.schemas import MappingFieldResponse, MappingStateResponse
from apps.api.app.modules.mapping.service import (
    build_mapping_fields,
    detect_source_type,
    get_mapping_template,
    list_canonical_fields,
    list_required_fields,
    rank_source_type_candidates,
    resolve_client_by_name_or_alias,
    resolve_sku_by_code_or_alias,
    source_supports_apply,
)
from apps.api.app.modules.uploads.assortment_import import (
    import_assortment_from_upload,
    is_assortment_frame,
)
from apps.api.app.modules.uploads.parsers import (
    build_preview_payload,
    read_upload_payload,
    sanitize_value,
)
from apps.api.app.modules.uploads.schemas import (
    ApplyUploadResponse,
    IssueCountsResponse,
    UploadBatchDetailResponse,
    UploadBatchSummaryResponse,
    UploadDetailResponse,
    UploadFileDetailResponse,
    UploadFileSummaryResponse,
    UploadIssueResponse,
    UploadJobResponse,
    UploadJobRunResponse,
    UploadPreviewResponse,
    UploadReadinessResponse,
    UploadSourceDetectionResponse,
    UploadSourceTypeCandidateResponse,
    UploadValidationSummaryResponse,
)
from apps.api.app.modules.uploads.stock_import import (
    import_warehouse_stock_from_upload,
    is_warehouse_stock_frame,
)
from apps.api.app.modules.uploads.storage import get_object_storage
from apps.api.app.modules.uploads.validation import ValidationIssue, validate_frame

SOURCE_TYPES = {
    "sales",
    "stock",
    "diy_clients",
    "category_structure",
    "inbound",
    "sku_costs",
    "raw_report",
}
BLOCKING_SEVERITIES = {"error", "critical"}
RAW_REPORT_REVIEW_STATUS = "ready_to_review"
AUTO_APPLY_SOURCE_TYPES = {"sku_costs"}


def _normalized_severity(value: str) -> str:
    return {
        "low": "info",
        "medium": "warning",
        "high": "error",
    }.get(value, value)


def _read_frame(settings: Settings, storage_key: str, file_name: str):
    storage = get_object_storage(settings)
    payload = storage.load_upload_bytes(storage_key)
    return read_upload_payload(payload, file_name)


def _transition_batch_status(
    batch: UploadBatch,
    status: str,
    *,
    message: str | None = None,
    error: str | None = None,
) -> None:
    status_payload = dict(batch.status_payload or {})
    history = list(status_payload.get("history", []))
    history.append(
        {
            "status": status,
            "at": utc_now().isoformat(),
            "message": message,
            "error": error,
        }
    )
    batch.status_payload = {
        **status_payload,
        "history": history[-25:],
        "current_status_at": utc_now().isoformat(),
        "last_error": error,
    }
    batch.status = status


def _create_job_run(
    db: Session,
    batch_id: str,
    file_id: str,
    job_name: str,
    queue_name: str = "ingestion",
) -> JobRun:
    job_run = JobRun(
        job_name=job_name,
        queue_name=queue_name,
        status="running",
        payload={"batch_id": batch_id, "file_id": file_id},
        started_at=utc_now(),
    )
    db.add(job_run)
    db.flush()
    return job_run


def _finish_job_run(job_run: JobRun, *, error_message: str | None = None) -> None:
    job_run.finished_at = utc_now()
    if error_message:
        job_run.status = "failed"
        job_run.error_message = error_message
    else:
        job_run.status = "completed"


def _jobs_for_batch(db: Session, batch_id: str) -> list[JobRun]:
    jobs = db.scalars(select(JobRun).order_by(JobRun.created_at.desc())).all()
    return [
        job for job in jobs if job.payload.get("batch_id") == batch_id  # type: ignore[union-attr]
    ]


def _job_to_response(job: JobRun) -> UploadJobRunResponse:
    return UploadJobRunResponse(
        id=job.id,
        job_name=job.job_name,
        queue_name=job.queue_name,
        status=job.status,
        started_at=job.started_at.isoformat() if job.started_at else None,
        finished_at=job.finished_at.isoformat() if job.finished_at else None,
        error_message=job.error_message,
    )


def _issue_counts_from_records(issues: list[UploadedRowIssue]) -> IssueCountsResponse:
    counts = Counter(_normalized_severity(issue.severity) for issue in issues)
    return IssueCountsResponse(
        info=counts.get("info", 0),
        warning=counts.get("warning", 0),
        error=counts.get("error", 0),
        critical=counts.get("critical", 0),
        total=len(issues),
    )


def _validation_issue_counts(payload: dict[str, object]) -> IssueCountsResponse:
    raw_counts = payload.get("issue_counts", {})
    if isinstance(raw_counts, dict):
        return IssueCountsResponse(
            info=int(raw_counts.get("info", raw_counts.get("low", 0))),
            warning=int(raw_counts.get("warning", raw_counts.get("medium", 0))),
            error=int(raw_counts.get("error", raw_counts.get("high", 0))),
            critical=int(raw_counts.get("critical", 0)),
            total=int(raw_counts.get("total", 0)),
        )
    return IssueCountsResponse()


def _serialize_mapping_fields(fields: list[MappingFieldResponse]) -> list[dict[str, object]]:
    return [field.model_dump() for field in fields]


def _active_mapping(fields: list[MappingFieldResponse]) -> dict[str, str]:
    return {field.source: field.canonical for field in fields if field.canonical}


def _mapping_state(batch: UploadBatch) -> MappingStateResponse:
    suggestions = [
        MappingFieldResponse(**payload) for payload in batch.mapping_payload.get("suggestions", [])
    ]
    return MappingStateResponse(
        source_type=batch.source_type,
        canonical_fields=list_canonical_fields(batch.source_type),
        required_fields=list_required_fields(batch.source_type),
        supports_apply=source_supports_apply(batch.source_type),
        template_id=batch.mapping_template_id,
        suggestions=suggestions,
        active_mapping=batch.mapping_payload.get("active_mapping", {}),
    )


def _preview_state(file_model: UploadFileModel, batch: UploadBatch) -> UploadPreviewResponse:
    preview = batch.preview_payload or {}
    return UploadPreviewResponse(
        file_id=file_model.id,
        source_type=batch.source_type,
        detected_source_type=batch.detected_source_type or batch.source_type,
        parser=str(preview.get("parser", "unknown")),
        encoding=preview.get("encoding"),  # type: ignore[arg-type]
        headers=[str(header) for header in preview.get("headers", [])],
        sample_rows=preview.get("sample_rows", []),  # type: ignore[arg-type]
        sample_row_count=int(preview.get("sample_row_count", 0)),
        empty_row_count=int(preview.get("empty_row_count", 0)),
    )


def _validation_state(
    batch: UploadBatch, issues: list[UploadedRowIssue]
) -> UploadValidationSummaryResponse:
    payload = batch.validation_payload or {}
    issue_counts = _validation_issue_counts(payload)
    if issue_counts.total == 0 and issues:
        issue_counts = _issue_counts_from_records(issues)
    return UploadValidationSummaryResponse(
        total_rows=batch.total_rows,
        valid_rows=batch.valid_rows,
        failed_rows=batch.failed_rows,
        warnings_count=batch.warning_count,
        issues_count=issue_counts.total,
        issue_counts=issue_counts,
        has_blocking_issues=bool(payload.get("has_blocking_issues", False)),
    )


def _readiness(batch: UploadBatch) -> UploadReadinessResponse:
    validation_payload = batch.validation_payload or {}
    has_blocking_issues = bool(validation_payload.get("has_blocking_issues", False))
    supports_apply = source_supports_apply(batch.source_type)
    detection_payload = dict(batch.mapping_payload.get("source_detection") or {})
    auto_adapter = bool(
        batch.mapping_payload.get("stock_adapter")
        or batch.mapping_payload.get("assortment_adapter")
    )
    source_confirmed = not detection_payload.get("requires_confirmation") or bool(
        detection_payload.get("confirmed")
    )
    return UploadReadinessResponse(
        can_apply=bool(
            supports_apply
            and not auto_adapter
            and batch.status in {"ready_to_apply", "applied_with_warnings", "applied"}
            and not has_blocking_issues
            and source_confirmed
        ),
        can_validate=bool(batch.mapping_payload.get("active_mapping"))
        and batch.source_type not in {"raw_report", "sku_costs"}
        and not auto_adapter
        and source_confirmed,
        can_edit_mapping=batch.status not in {"applying"},
    )


def _source_detection_state(batch: UploadBatch) -> UploadSourceDetectionResponse | None:
    payload = batch.mapping_payload.get("source_detection") if batch.mapping_payload else None
    if not isinstance(payload, dict):
        return None
    candidates = [
        UploadSourceTypeCandidateResponse(
            source_type=str(item.get("source_type", "raw_report")),
            confidence=float(item.get("confidence", 0)),
            matched_fields=[str(field) for field in item.get("matched_fields", [])],
        )
        for item in payload.get("candidates", [])
        if isinstance(item, dict)
    ]
    return UploadSourceDetectionResponse(
        requires_confirmation=bool(payload.get("requires_confirmation", False)),
        confirmed=bool(payload.get("confirmed", False)),
        detected_source_type=str(
            payload.get("detected_source_type") or batch.detected_source_type or batch.source_type
        ),
        selected_source_type=str(payload.get("selected_source_type") or batch.source_type),
        candidates=candidates,
        custom_entity_name=(
            str(payload["custom_entity_name"]) if payload.get("custom_entity_name") else None
        ),
    )


def _file_summary(file_model: UploadFileModel, batch: UploadBatch) -> UploadFileSummaryResponse:
    issues = _issues_for_batch(file_model.batch_id, file_model.id, batch=batch)
    return UploadFileSummaryResponse(
        id=file_model.id,
        batch_id=batch.id,
        file_name=file_model.file_name,
        source_type=batch.source_type,
        detected_source_type=batch.detected_source_type or batch.source_type,
        uploaded_at=batch.created_at.isoformat(),
        status=batch.status,
        size_bytes=file_model.size_bytes,
        mime_type=file_model.content_type,
        checksum=file_model.checksum,
        storage_key=file_model.storage_key,
        parsing_version=batch.parsing_version,
        normalization_version=batch.normalization_version,
        mapping_template_id=batch.mapping_template_id,
        uploaded_by_id=batch.uploaded_by_id,
        total_rows=batch.total_rows,
        applied_rows=batch.applied_rows,
        failed_rows=batch.failed_rows,
        warnings_count=batch.warning_count,
        issue_counts=_issue_counts_from_records(issues),
        duplicate_of_batch_id=batch.duplicate_of_batch_id,
        is_duplicate=batch.duplicate_of_batch_id is not None,
        readiness=_readiness(batch),
        source_detection=_source_detection_state(batch),
    )


def _issues_for_batch(
    batch_id: str,
    file_id: str | None = None,
    *,
    batch: UploadBatch | None = None,
    db: Session | None = None,
) -> list[UploadedRowIssue]:
    if db is None and batch is None:
        raise ValueError("Either db or batch must be provided")
    session = db or object_session(batch)  # type: ignore[arg-type]
    if session is None:
        return []
    query = select(UploadedRowIssue).where(UploadedRowIssue.batch_id == batch_id)
    if file_id:
        query = query.where(UploadedRowIssue.file_id == file_id)
    return session.scalars(
        query.order_by(UploadedRowIssue.row_number, UploadedRowIssue.created_at)
    ).all()


def _legacy_job_from_file(file_summary: UploadFileSummaryResponse) -> UploadJobResponse:
    return UploadJobResponse(
        id=file_summary.batch_id,
        file_name=file_summary.file_name,
        source_type=file_summary.source_type,
        size_bytes=file_summary.size_bytes,
        uploaded_at=file_summary.uploaded_at,
        state=file_summary.status,
        rows=file_summary.total_rows,
        issues=file_summary.issue_counts.total,
    )


def _legacy_detail(detail: UploadFileDetailResponse) -> UploadDetailResponse:
    return UploadDetailResponse(
        job=_legacy_job_from_file(detail.file),
        mapping_fields=detail.mapping.suggestions,
        issues=detail.issues_preview,
    )


def _get_file_and_batch(db: Session, file_id: str) -> tuple[UploadFileModel, UploadBatch]:
    file_model = db.get(UploadFileModel, file_id)
    if file_model is None:
        raise DomainError(code="upload_file_not_found", message="Файл загрузки не найден")
    batch = db.get(UploadBatch, file_model.batch_id)
    if batch is None:
        raise DomainError(code="upload_batch_not_found", message="Пакет загрузки не найден")
    return file_model, batch


def _get_file_and_batch_by_batch_id(
    db: Session, batch_id: str
) -> tuple[UploadFileModel, UploadBatch]:
    batch = db.get(UploadBatch, batch_id)
    if batch is None or not batch.files:
        raise DomainError(code="upload_batch_not_found", message="Пакет загрузки не найден")
    return batch.files[0], batch


def _duplicate_batch_id(db: Session, checksum: str, current_batch_id: str) -> str | None:
    duplicate = db.scalars(
        select(UploadBatch)
        .where(UploadBatch.checksum == checksum, UploadBatch.id != current_batch_id)
        .order_by(UploadBatch.created_at.desc())
    ).first()
    return duplicate.id if duplicate else None


def _slugify_source_name(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ]+", "_", value.strip().lower())
    normalized = normalized.strip("_")
    return normalized or "custom_report"


def _create_custom_data_source(db: Session, name: str) -> DataSource:
    base_code = f"custom_{_slugify_source_name(name)}"
    code = base_code[:56]
    suffix = 1
    while db.scalar(select(func.count()).select_from(DataSource).where(DataSource.code == code)):
        suffix += 1
        code = f"{base_code[:50]}_{suffix}"
    data_source = DataSource(
        code=code,
        name=name.strip(),
        source_type="raw_report",
        parsing_version="v1",
        normalization_version="v1",
    )
    db.add(data_source)
    db.flush()
    return data_source


def _persist_uploaded_issue(
    db: Session,
    batch: UploadBatch,
    file_model: UploadFileModel,
    issue: ValidationIssue,
) -> UploadedRowIssue:
    record = UploadedRowIssue(
        batch_id=batch.id,
        file_id=file_model.id,
        row_number=issue.row_number,
        field_name=issue.field_name,
        code=issue.code,
        severity=issue.severity,
        message=issue.message,
        raw_payload=issue.raw_payload,
    )
    db.add(record)
    return record


def _serialize_uploaded_issue(issue: UploadedRowIssue) -> UploadIssueResponse:
    return UploadIssueResponse(
        id=issue.id,
        row_number=issue.row_number,
        field_name=issue.field_name,
        code=issue.code,
        severity=issue.severity,
        message=issue.message,
        raw_payload=issue.raw_payload,
    )


def _refresh_quality_issues(
    db: Session,
    batch: UploadBatch,
    file_model: UploadFileModel,
    issues: list[ValidationIssue],
) -> None:
    db.execute(
        delete(QualityIssue).where(
            QualityIssue.batch_id == batch.id,
            QualityIssue.file_id == file_model.id,
        )
    )
    for issue in issues:
        severity = issue.severity
        db.add(
            QualityIssue(
                batch_id=batch.id,
                file_id=file_model.id,
                issue_type=issue.code,
                severity=severity,
                entity_type=batch.source_type,
                entity_ref=str(issue.row_number),
                description=issue.message,
                source_label=file_model.file_name,
            )
        )


def _validation_payload_from_issues(
    batch: UploadBatch,
    issues: list[ValidationIssue],
    valid_rows: int,
    failed_rows: int,
    warning_count: int,
) -> dict[str, object]:
    counts = Counter(issue.severity for issue in issues)
    has_blocking_issues = counts.get("error", 0) > 0 or counts.get("critical", 0) > 0
    return {
        "validated_at": utc_now().isoformat(),
        "valid_rows": valid_rows,
        "failed_rows": failed_rows,
        "warning_count": warning_count,
        "has_blocking_issues": has_blocking_issues,
        "issue_counts": {
            "info": counts.get("info", 0),
            "warning": counts.get("warning", 0),
            "error": counts.get("error", 0),
            "critical": counts.get("critical", 0),
            "total": len(issues),
        },
        "source_type": batch.source_type,
    }


def _maybe_duplicate_issue(batch: UploadBatch) -> list[ValidationIssue]:
    if not batch.duplicate_of_batch_id:
        return []
    return [
        ValidationIssue(
            row_number=0,
            field_name=None,
            code="duplicate_upload",
            severity="warning",
            message=f"Загрузка дублирует ранее полученный пакет {batch.duplicate_of_batch_id}",
            raw_payload={"duplicate_of_batch_id": batch.duplicate_of_batch_id},
        )
    ]


def _run_parse_stage(
    db: Session,
    settings: Settings,
    batch: UploadBatch,
    file_model: UploadFileModel,
    source_type_hint: str | None = None,
    *,
    require_source_confirmation: bool = False,
    custom_entity_name: str | None = None,
) -> None:
    _transition_batch_status(batch, "parsing", message="Разбираем загруженный файл")
    job_run = _create_job_run(db, batch.id, file_model.id, "parse_upload")
    db.flush()
    try:
        parse_result = _read_frame(settings, file_model.storage_key, file_model.file_name)
        frame = parse_result.frame
        source_candidates = rank_source_type_candidates([str(column) for column in frame.columns])
        detected_source_type = detect_source_type(
            [str(column) for column in frame.columns], source_type_hint
        )
        if source_type_hint is None and is_warehouse_stock_frame(frame):
            detected_source_type = "stock"
            source_candidates = [
                {
                    "source_type": "stock",
                    "confidence": 0.98,
                    "matched_fields": ["sku_code", "product_name", "stock_free", "warehouse_name"],
                },
                *[
                    candidate
                    for candidate in source_candidates
                    if candidate.get("source_type") != "stock"
                ],
            ][:5]
        elif source_type_hint is None and is_assortment_frame(frame, file_model.file_name):
            detected_source_type = "category_structure"
            source_candidates = [
                {
                    "source_type": "category_structure",
                    "confidence": 0.98,
                    "matched_fields": ["sku_code", "product_name", "category_hierarchy"],
                },
                *[
                    candidate
                    for candidate in source_candidates
                    if candidate.get("source_type") != "category_structure"
                ],
            ][:5]
        batch.source_type = detected_source_type
        batch.detected_source_type = detected_source_type
        file_model.source_type = detected_source_type
        batch.total_rows = len(frame.index)
        batch.checksum = file_model.checksum
        batch.duplicate_of_batch_id = _duplicate_batch_id(db, file_model.checksum, batch.id)

        template_mapping: dict[str, str] | None = None
        if batch.mapping_template_id:
            template = get_mapping_template(db, batch.mapping_template_id)
            template_mapping = {rule.source_header: rule.canonical_field for rule in template.rules}

        suggestions = build_mapping_fields(
            frame, detected_source_type, template_mapping=template_mapping
        )
        active_mapping = _active_mapping(suggestions)
        required_fields = set(list_required_fields(detected_source_type))
        missing_required = required_fields - set(active_mapping.values())

        preview_payload = build_preview_payload(frame)
        batch.preview_payload = {
            **preview_payload,
            "parser": parse_result.parser,
            "encoding": parse_result.encoding,
        }
        batch.mapping_payload = {
            "suggestions": _serialize_mapping_fields(suggestions),
            "active_mapping": active_mapping,
            "required_fields": sorted(required_fields),
            "source_detection": {
                "requires_confirmation": (
                    require_source_confirmation
                    and detected_source_type not in AUTO_APPLY_SOURCE_TYPES
                ),
                "confirmed": (
                    not require_source_confirmation
                    or detected_source_type in AUTO_APPLY_SOURCE_TYPES
                ),
                "detected_source_type": detected_source_type,
                "selected_source_type": detected_source_type,
                "candidates": source_candidates,
                "custom_entity_name": custom_entity_name,
            },
        }
        db.execute(delete(UploadedRowIssue).where(UploadedRowIssue.batch_id == batch.id))
        _refresh_quality_issues(db, batch, file_model, [])
        if detected_source_type == "sku_costs":
            import_sku_costs_from_upload(
                db,
                get_object_storage(settings),
                file_model.id,
                commit=False,
            )
        elif detected_source_type == "stock" and is_warehouse_stock_frame(frame):
            import_warehouse_stock_from_upload(
                db,
                get_object_storage(settings),
                file_model.id,
                commit=False,
            )
        elif detected_source_type == "category_structure" and is_assortment_frame(
            frame, file_model.file_name
        ):
            import_assortment_from_upload(
                db,
                get_object_storage(settings),
                file_model.id,
                commit=False,
            )
        elif require_source_confirmation:
            batch.validation_payload = {
                "validated_at": None,
                "valid_rows": 0,
                "failed_rows": 0,
                "warning_count": 0,
                "has_blocking_issues": False,
                "issue_counts": {"info": 0, "warning": 0, "error": 0, "critical": 0, "total": 0},
                "source_type": detected_source_type,
            }
            batch.valid_rows = 0
            batch.failed_rows = 0
            batch.warning_count = 0
            batch.issue_count = 0
            _transition_batch_status(
                batch,
                "source_confirmation_required",
                message="Тип данных распознан автоматически и ожидает подтверждения",
            )
        elif detected_source_type == "raw_report":
            batch.validation_payload = {
                "validated_at": utc_now().isoformat(),
                "valid_rows": batch.total_rows,
                "failed_rows": 0,
                "warning_count": 0,
                "has_blocking_issues": False,
                "issue_counts": {"info": 0, "warning": 0, "error": 0, "critical": 0, "total": 0},
                "source_type": detected_source_type,
            }
            _transition_batch_status(
                batch, RAW_REPORT_REVIEW_STATUS, message="Сырой отчёт готов к просмотру"
            )
        elif missing_required:
            missing_issues = [
                ValidationIssue(
                    row_number=0,
                    field_name=field_name,
                    code="mapping_required",
                    severity="error",
                    message="Обязательное каноническое поле не сопоставлено",
                    raw_payload=None,
                )
                for field_name in sorted(missing_required)
            ]
            for issue in missing_issues:
                _persist_uploaded_issue(db, batch, file_model, issue)
            _refresh_quality_issues(db, batch, file_model, missing_issues)
            batch.valid_rows = 0
            batch.failed_rows = 0
            batch.warning_count = 0
            batch.issue_count = len(missing_issues)
            batch.validation_payload = _validation_payload_from_issues(
                batch,
                missing_issues,
                valid_rows=0,
                failed_rows=0,
                warning_count=0,
            )
            _transition_batch_status(
                batch, "mapping_required", message="Не хватает обязательных канонических полей"
            )
        else:
            _transition_batch_status(
                batch, "validating", message="Запускаем автопроверку сопоставленной загрузки"
            )
        _finish_job_run(job_run)
        db.commit()
    except Exception as exc:
        _finish_job_run(job_run, error_message=str(exc))
        _transition_batch_status(batch, "failed", error=str(exc))
        db.commit()
        raise


def validate_upload_file(
    db: Session,
    settings: Settings,
    file_id: str,
) -> UploadFileDetailResponse:
    file_model, batch = _get_file_and_batch(db, file_id)
    if batch.source_type == "raw_report":
        return get_upload_file_detail(db, file_id)

    mapping = batch.mapping_payload.get("active_mapping", {})
    if not mapping:
        raise DomainError(
            code="mapping_required", message="Для загрузки не настроено сопоставление"
        )

    _transition_batch_status(batch, "validating", message="Проверяем сопоставленную загрузку")
    job_run = _create_job_run(db, batch.id, file_model.id, "validate_upload")
    db.flush()
    try:
        parse_result = _read_frame(settings, file_model.storage_key, file_model.file_name)
        validation_result = validate_frame(parse_result.frame, batch.source_type, mapping)
        issues = _maybe_duplicate_issue(batch) + validation_result.issues

        db.execute(delete(UploadedRowIssue).where(UploadedRowIssue.batch_id == batch.id))
        for issue in issues:
            _persist_uploaded_issue(db, batch, file_model, issue)
        _refresh_quality_issues(db, batch, file_model, issues)

        batch.valid_rows = validation_result.valid_rows
        batch.failed_rows = validation_result.failed_rows
        batch.warning_count = validation_result.warning_count + (
            1 if batch.duplicate_of_batch_id else 0
        )
        batch.issue_count = len(issues)
        batch.validation_payload = _validation_payload_from_issues(
            batch,
            issues,
            valid_rows=validation_result.valid_rows,
            failed_rows=validation_result.failed_rows,
            warning_count=batch.warning_count,
        )
        if batch.validation_payload.get("has_blocking_issues"):
            _transition_batch_status(batch, "issues_found", message="Найдены проблемы проверки")
        else:
            _transition_batch_status(
                batch, "ready_to_apply", message="Загрузка готова к применению"
            )
        _finish_job_run(job_run)
        db.commit()
        return get_upload_file_detail(db, file_id)
    except Exception as exc:
        _finish_job_run(job_run, error_message=str(exc))
        _transition_batch_status(batch, "failed", error=str(exc))
        db.commit()
        raise


def _get_or_create_product(
    db: Session, product_name: str | None, brand: str | None = None
) -> Product | None:
    if not product_name:
        return None
    brand = brand or resolve_brand(None, product_name)
    existing = db.scalars(select(Product).where(Product.name == product_name)).first()
    if existing:
        existing.brand = brand
        return existing
    product = Product(name=product_name, brand=brand)
    db.add(product)
    db.flush()
    return product


def _get_or_create_sku(
    db: Session,
    sku_code: str,
    product_name: str | None = None,
    category: Category | None = None,
) -> Sku:
    existing = resolve_sku_by_code_or_alias(db, sku_code)
    if existing:
        if product_name and not existing.name:
            existing.name = product_name
        if category is not None:
            existing.category_id = category.id
        if product_name:
            existing.brand = resolve_brand(existing.brand, product_name, sku_code)
        return existing
    brand = resolve_brand(None, product_name, sku_code)
    product = _get_or_create_product(db, product_name, brand=brand)
    sku = Sku(
        article=sku_code,
        name=product_name or sku_code,
        product_id=product.id if product else None,
        category_id=category.id if category else None,
        brand=brand,
        unit="pcs",
        active=True,
    )
    db.add(sku)
    db.flush()
    return sku


def _get_or_create_client(
    db: Session,
    client_name: str,
    *,
    region: str = "Unknown",
    client_group: str = "DIY",
) -> Client:
    existing = resolve_client_by_name_or_alias(db, client_name)
    if existing:
        return existing
    code = f"client_{generate_id('code')[-6:]}"
    client = Client(
        code=code,
        name=client_name,
        region=region,
        client_group=client_group,
        network_type=client_group,
        is_active=True,
    )
    db.add(client)
    db.flush()
    return client


def _category_by_path(db: Session, path: str) -> Category | None:
    return db.scalars(select(Category).where(Category.path == path)).first()


def _get_or_create_category_hierarchy(
    db: Session,
    level_1: str | None,
    level_2: str | None = None,
    level_3: str | None = None,
) -> Category | None:
    parent: Category | None = None
    path_parts: list[str] = []
    for level, name in enumerate([level_1, level_2, level_3]):
        if not name:
            continue
        path_parts.append(name)
        path = " / ".join(path_parts)
        existing = _category_by_path(db, path)
        if existing:
            parent = existing
            continue
        category = Category(
            code=normalize_code(path),
            name=name,
            parent_id=parent.id if parent else None,
            level=level + 1,
            path=path,
        )
        db.add(category)
        db.flush()
        parent = category
    return parent


def normalize_code(value: str) -> str:
    return value.lower().replace(" / ", "_").replace(" ", "_").replace("-", "_").replace("__", "_")


def _apply_sales_row(
    db: Session,
    batch: UploadBatch,
    row: dict[str, object],
) -> None:
    client_name = str(row["client_name"])
    sku_code = str(row["sku_code"])
    client = resolve_client_by_name_or_alias(db, client_name)
    sku = resolve_sku_by_code_or_alias(db, sku_code)
    if client is None:
        raise DomainError(code="unmatched_client", message=f"Клиент «{client_name}» не сопоставлен")
    if sku is None:
        raise DomainError(code="unmatched_sku", message=f"SKU «{sku_code}» не сопоставлен")
    period_date = row.get("period_date")
    if not isinstance(period_date, (datetime, date)):
        raise DomainError(code="invalid_date", message="Некорректная дата периода продаж")
    existing = db.scalars(
        select(SalesFact).where(
            SalesFact.client_id == client.id,
            SalesFact.sku_id == sku.id,
            SalesFact.period_month == period_date,
        )
    ).first()
    if existing:
        existing.quantity = float(row["quantity"])
        existing.revenue_amount = row.get("revenue")  # type: ignore[assignment]
        existing.source_batch_id = batch.id
        return
    db.add(
        SalesFact(
            source_batch_id=batch.id,
            client_id=client.id,
            sku_id=sku.id,
            category_id=sku.category_id,
            period_month=period_date,
            quantity=float(row["quantity"]),
            revenue_amount=row.get("revenue"),  # type: ignore[arg-type]
        )
    )


def _apply_stock_row(db: Session, batch: UploadBatch, row: dict[str, object]) -> None:
    sku = resolve_sku_by_code_or_alias(db, str(row["sku_code"]))
    if sku is None:
        raise DomainError(code="unmatched_sku", message=f"SKU «{row['sku_code']}» не сопоставлен")
    snapshot_date = row.get("snapshot_date")
    if not isinstance(snapshot_date, (datetime, date)):
        raise DomainError(code="invalid_date", message="Некорректная дата снимка склада")
    db.add(
        StockSnapshot(
            source_batch_id=batch.id,
            sku_id=sku.id,
            warehouse_code=str(row.get("warehouse_name") or "UNKNOWN"),
            snapshot_at=datetime.combine(
                snapshot_date, datetime.min.time(), tzinfo=utc_now().tzinfo
            ),
            free_stock_qty=float(row.get("stock_free") or 0),
            reserved_like_qty=max(
                float(row.get("stock_total") or 0) - float(row.get("stock_free") or 0), 0
            ),
        )
    )


def _apply_inbound_row(
    db: Session, batch: UploadBatch, row_index: int, row: dict[str, object]
) -> None:
    sku = resolve_sku_by_code_or_alias(db, str(row["sku_code"]))
    if sku is None:
        raise DomainError(code="unmatched_sku", message=f"SKU «{row['sku_code']}» не сопоставлен")
    external_ref = str(row.get("source_row_id") or f"{batch.id}:{row_index}")
    existing = db.scalars(
        select(InboundDelivery).where(InboundDelivery.external_ref == external_ref)
    ).first()
    if existing:
        existing.sku_id = sku.id
        existing.quantity = float(row["quantity"])
        existing.eta_date = row["eta_date"]  # type: ignore[assignment]
        existing.status = str(row["status"])
        existing.source_batch_id = batch.id
        return
    db.add(
        InboundDelivery(
            source_batch_id=batch.id,
            external_ref=external_ref,
            sku_id=sku.id,
            quantity=float(row["quantity"]),
            eta_date=row["eta_date"],  # type: ignore[arg-type]
            status=str(row["status"]),
            affected_client_ids=[],
            reserve_impact_qty=0,
        )
    )


def _apply_diy_client_row(db: Session, row: dict[str, object]) -> None:
    client = _get_or_create_client(
        db,
        str(row["client_name"]),
        region=str(row.get("region") or "Unknown"),
        client_group="DIY",
    )
    policy = db.scalars(select(DiyPolicy).where(DiyPolicy.client_id == client.id)).first()
    if policy is None:
        policy = DiyPolicy(client_id=client.id)
        db.add(policy)
    policy.reserve_months = int(row.get("reserve_months") or 3)
    policy.safety_factor = float(row.get("safety_factor") or 1.1)
    policy.priority_level = int(row.get("priority") or 1)


def _apply_category_row(db: Session, row: dict[str, object]) -> None:
    category = _get_or_create_category_hierarchy(
        db,
        row.get("category_level_1"),  # type: ignore[arg-type]
        row.get("category_level_2"),  # type: ignore[arg-type]
        row.get("category_level_3"),  # type: ignore[arg-type]
    )
    sku_code = row.get("sku_code")
    if sku_code:
        sku = _get_or_create_sku(
            db,
            str(sku_code),
            product_name=row.get("product_name"),  # type: ignore[arg-type]
            category=category,
        )
        if category is not None:
            sku.category_id = category.id


def _apply_normalized_row(
    db: Session,
    batch: UploadBatch,
    row_index: int,
    row: dict[str, object],
) -> None:
    if batch.source_type == "sales":
        _apply_sales_row(db, batch, row)
        return
    if batch.source_type == "stock":
        _apply_stock_row(db, batch, row)
        return
    if batch.source_type == "inbound":
        _apply_inbound_row(db, batch, row_index, row)
        return
    if batch.source_type == "diy_clients":
        _apply_diy_client_row(db, row)
        return
    if batch.source_type == "category_structure":
        _apply_category_row(db, row)
        return
    raise DomainError(
        code="apply_not_supported", message="Для этого типа источника применение недоступно"
    )


def list_upload_files(
    db: Session,
    *,
    status: str | None = None,
    source_type: str | None = None,
) -> list[UploadFileSummaryResponse]:
    files = db.scalars(select(UploadFileModel).order_by(UploadFileModel.created_at.desc())).all()
    items: list[UploadFileSummaryResponse] = []
    for file_model in files:
        batch = db.get(UploadBatch, file_model.batch_id)
        if batch is None:
            continue
        if status and batch.status != status:
            continue
        if source_type and batch.source_type != source_type:
            continue
        items.append(_file_summary(file_model, batch))
    return items


def list_upload_files_page(
    db: Session,
    *,
    status: str | None = None,
    source_type: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[UploadFileSummaryResponse], int]:
    stmt = select(UploadFileModel, UploadBatch).join(
        UploadBatch, UploadBatch.id == UploadFileModel.batch_id
    )
    if status:
        stmt = stmt.where(UploadBatch.status == status)
    if source_type:
        stmt = stmt.where(UploadBatch.source_type == source_type)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(UploadFileModel.created_at.desc())
        .offset(max(page - 1, 0) * page_size)
        .limit(page_size)
    ).all()
    return ([_file_summary(file_model, batch) for file_model, batch in rows], int(total))


def get_upload_file_detail(db: Session, file_id: str) -> UploadFileDetailResponse:
    file_model, batch = _get_file_and_batch(db, file_id)
    issues = _issues_for_batch(batch.id, file_model.id, db=db)
    return UploadFileDetailResponse(
        file=_file_summary(file_model, batch),
        preview=_preview_state(file_model, batch),
        mapping=_mapping_state(batch),
        validation=_validation_state(batch, issues),
        jobs=[_job_to_response(job) for job in _jobs_for_batch(db, batch.id)],
        issues_preview=[
            UploadIssueResponse(
                id=issue.id,
                row_number=issue.row_number,
                field_name=issue.field_name,
                code=issue.code,
                severity=issue.severity,
                message=issue.message,
                raw_payload=issue.raw_payload,
            )
            for issue in issues[:20]
        ],
    )


def get_upload_preview(db: Session, file_id: str) -> UploadPreviewResponse:
    file_model, batch = _get_file_and_batch(db, file_id)
    return _preview_state(file_model, batch)


def get_upload_mapping_state(db: Session, file_id: str) -> MappingStateResponse:
    _, batch = _get_file_and_batch(db, file_id)
    return _mapping_state(batch)


def suggest_upload_mapping(
    db: Session,
    settings: Settings,
    file_id: str,
    *,
    template_id: str | None = None,
) -> UploadFileDetailResponse:
    file_model, batch = _get_file_and_batch(db, file_id)
    parse_result = _read_frame(settings, file_model.storage_key, file_model.file_name)
    template_mapping: dict[str, str] | None = None
    if template_id:
        template = get_mapping_template(db, template_id)
        batch.mapping_template_id = template.id
        template_mapping = {rule.source_header: rule.canonical_field for rule in template.rules}
    suggestions = build_mapping_fields(
        parse_result.frame, batch.source_type, template_mapping=template_mapping
    )
    batch.mapping_payload = {
        "suggestions": _serialize_mapping_fields(suggestions),
        "active_mapping": _active_mapping(suggestions),
        "required_fields": list_required_fields(batch.source_type),
    }
    missing_required = set(list_required_fields(batch.source_type)) - set(
        batch.mapping_payload["active_mapping"].values()
    )
    next_status = (
        RAW_REPORT_REVIEW_STATUS
        if batch.source_type == "raw_report"
        else "mapping_required" if missing_required else "validating"
    )
    _transition_batch_status(batch, next_status, message="Подсказки по сопоставлению обновлены")
    db.commit()
    if not missing_required and batch.source_type != "raw_report":
        return validate_upload_file(db, settings, file_id)
    return get_upload_file_detail(db, file_id)


def save_upload_mapping(
    db: Session,
    settings: Settings,
    file_id: str,
    *,
    mappings: dict[str, str],
    template_id: str | None = None,
) -> UploadFileDetailResponse:
    file_model, batch = _get_file_and_batch(db, file_id)
    parse_result = _read_frame(settings, file_model.storage_key, file_model.file_name)
    required_fields = set(list_required_fields(batch.source_type))
    suggestions: list[MappingFieldResponse] = []
    for column in parse_result.frame.columns:
        source_field = str(column)
        canonical = mappings.get(source_field, "")
        suggestions.append(
            MappingFieldResponse(
                source=source_field,
                canonical=canonical,
                confidence=1.0 if canonical else 0.0,
                status="ok" if canonical else "missing",
                sample=(
                    None if parse_result.frame.empty else str(parse_result.frame.iloc[0][column])
                ),
                required=canonical in required_fields if canonical else False,
            )
        )
    batch.mapping_template_id = template_id
    batch.mapping_payload = {
        "suggestions": _serialize_mapping_fields(suggestions),
        "active_mapping": _active_mapping(suggestions),
        "required_fields": sorted(required_fields),
    }
    missing_required = required_fields - set(batch.mapping_payload["active_mapping"].values())
    next_status = (
        RAW_REPORT_REVIEW_STATUS
        if batch.source_type == "raw_report"
        else "mapping_required" if missing_required else "validating"
    )
    _transition_batch_status(batch, next_status, message="Сопоставление обновлено")
    db.commit()
    if missing_required or batch.source_type == "raw_report":
        return get_upload_file_detail(db, file_id)
    return validate_upload_file(db, settings, file_id)


def list_upload_file_issues(
    db: Session,
    file_id: str,
    *,
    severity: str | None = None,
) -> list[UploadIssueResponse]:
    file_model, batch = _get_file_and_batch(db, file_id)
    issues = _issues_for_batch(batch.id, file_model.id, db=db)
    if severity:
        issues = [issue for issue in issues if issue.severity == severity]
    return [_serialize_uploaded_issue(issue) for issue in issues]


def list_upload_file_issues_page(
    db: Session,
    file_id: str,
    *,
    severity: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[UploadIssueResponse], int]:
    file_model, batch = _get_file_and_batch(db, file_id)
    stmt = select(UploadedRowIssue).where(
        UploadedRowIssue.batch_id == batch.id,
        UploadedRowIssue.file_id == file_model.id,
    )
    if severity:
        stmt = stmt.where(UploadedRowIssue.severity == severity)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    issues = db.scalars(
        stmt.order_by(UploadedRowIssue.row_number, UploadedRowIssue.created_at)
        .offset(max(page - 1, 0) * page_size)
        .limit(page_size)
    ).all()
    return ([_serialize_uploaded_issue(issue) for issue in issues], int(total))


def apply_upload_file(
    db: Session,
    settings: Settings,
    file_id: str,
) -> ApplyUploadResponse:
    file_model, batch = _get_file_and_batch(db, file_id)
    if not source_supports_apply(batch.source_type):
        raise DomainError(
            code="apply_not_supported", message="Для этого типа источника применение недоступно"
        )

    detail = validate_upload_file(db, settings, file_id)
    if detail.validation.has_blocking_issues:
        raise DomainError(
            code="blocking_issues", message="Загрузка содержит блокирующие проблемы проверки"
        )

    _transition_batch_status(batch, "applying", message="Применяем нормализованные данные")
    job_run = _create_job_run(db, batch.id, file_model.id, "apply_upload")
    db.flush()
    try:
        parse_result = _read_frame(settings, file_model.storage_key, file_model.file_name)
        validation_result = validate_frame(
            parse_result.frame,
            batch.source_type,
            batch.mapping_payload.get("active_mapping", {}),
        )

        db.execute(delete(SalesFact).where(SalesFact.source_batch_id == batch.id))
        db.execute(delete(StockSnapshot).where(StockSnapshot.source_batch_id == batch.id))
        db.execute(delete(InboundDelivery).where(InboundDelivery.source_batch_id == batch.id))

        applied_rows = 0
        apply_issues: list[ValidationIssue] = []
        for index, normalized_row in enumerate(validation_result.normalized_rows):
            try:
                _apply_normalized_row(db, batch, index, normalized_row)
                applied_rows += 1
            except DomainError as exc:
                apply_issues.append(
                    ValidationIssue(
                        row_number=index + 2,
                        field_name=None,
                        code=exc.code,
                        severity="error",
                        message=exc.message,
                        raw_payload={
                            key: sanitize_value(value) for key, value in normalized_row.items()
                        },
                    )
                )

        persisted_issues = _maybe_duplicate_issue(batch) + validation_result.issues + apply_issues
        db.execute(delete(UploadedRowIssue).where(UploadedRowIssue.batch_id == batch.id))
        for issue in persisted_issues:
            _persist_uploaded_issue(db, batch, file_model, issue)
        _refresh_quality_issues(db, batch, file_model, persisted_issues)

        batch.applied_rows = applied_rows
        batch.failed_rows = max(batch.total_rows - applied_rows, 0)
        batch.warning_count = sum(issue.severity == "warning" for issue in persisted_issues)
        batch.issue_count = len(persisted_issues)
        batch.valid_rows = max(batch.total_rows - batch.failed_rows, 0)
        batch.validation_payload = _validation_payload_from_issues(
            batch,
            persisted_issues,
            valid_rows=batch.valid_rows,
            failed_rows=batch.failed_rows,
            warning_count=batch.warning_count,
        )

        if applied_rows == 0 and persisted_issues:
            _transition_batch_status(batch, "failed", error="Не удалось применить ни одной строки")
        elif batch.warning_count or any(
            issue.severity in BLOCKING_SEVERITIES for issue in apply_issues
        ):
            _transition_batch_status(
                batch,
                "applied_with_warnings",
                message="Загрузка применена с предупреждениями",
            )
        else:
            _transition_batch_status(batch, "applied", message="Загрузка успешно применена")

        _finish_job_run(job_run)
        analytics_job = _create_job_run(
            db, batch.id, file_model.id, "refresh_analytics", queue_name="analytics"
        )
        materialize_analytics(db, settings)
        _finish_job_run(analytics_job)
        db.commit()

        return ApplyUploadResponse(
            file_id=file_model.id,
            batch_id=batch.id,
            status=batch.status,
            applied_rows=batch.applied_rows,
            failed_rows=batch.failed_rows,
            warnings_count=batch.warning_count,
            issue_counts=_validation_issue_counts(batch.validation_payload),
        )
    except Exception as exc:
        _finish_job_run(job_run, error_message=str(exc))
        _transition_batch_status(batch, "failed", error=str(exc))
        db.commit()
        raise


def list_upload_batches(db: Session) -> list[UploadBatchSummaryResponse]:
    return list_upload_batches_page(db, page=1, page_size=10_000)[0]


def list_upload_batches_page(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[UploadBatchSummaryResponse], int]:
    stmt = select(UploadBatch).order_by(UploadBatch.created_at.desc())
    total = db.scalar(select(func.count()).select_from(UploadBatch)) or 0
    batches = db.scalars(stmt.offset(max(page - 1, 0) * page_size).limit(page_size)).all()
    summaries: list[UploadBatchSummaryResponse] = []
    for batch in batches:
        issues = _issues_for_batch(batch.id, db=db)
        summaries.append(
            UploadBatchSummaryResponse(
                id=batch.id,
                source_type=batch.source_type,
                status=batch.status,
                uploaded_at=batch.created_at.isoformat(),
                file_count=len(batch.files),
                total_rows=batch.total_rows,
                issue_counts=_issue_counts_from_records(issues),
            )
        )
    return summaries, int(total)


def get_upload_batch_detail(db: Session, batch_id: str) -> UploadBatchDetailResponse:
    batch = db.get(UploadBatch, batch_id)
    if batch is None:
        raise DomainError(code="upload_batch_not_found", message="Пакет загрузки не найден")
    issues = _issues_for_batch(batch.id, db=db)
    return UploadBatchDetailResponse(
        batch=UploadBatchSummaryResponse(
            id=batch.id,
            source_type=batch.source_type,
            status=batch.status,
            uploaded_at=batch.created_at.isoformat(),
            file_count=len(batch.files),
            total_rows=batch.total_rows,
            issue_counts=_issue_counts_from_records(issues),
        ),
        files=[_file_summary(file_model, batch) for file_model in batch.files],
        jobs=[_job_to_response(job) for job in _jobs_for_batch(db, batch.id)],
    )


def create_upload_file(
    db: Session,
    settings: Settings,
    current_user: User,
    file: UploadFile,
    source_type: str | None = None,
) -> UploadFileDetailResponse:
    if file.filename is None:
        raise DomainError(code="invalid_file", message="Нужно имя файла")
    requested_source_type = source_type or "raw_report"
    if requested_source_type not in SOURCE_TYPES:
        raise DomainError(code="unsupported_source_type", message="Неподдерживаемый тип источника")

    storage = get_object_storage(settings)
    stored = storage.save_upload(file)

    batch = UploadBatch(
        source_type=requested_source_type,
        detected_source_type=requested_source_type,
        status="uploaded",
        uploaded_by_id=current_user.id,
        checksum=stored.checksum,
        total_rows=0,
        valid_rows=0,
        applied_rows=0,
        failed_rows=0,
        warning_count=0,
        issue_count=0,
        mapping_payload={},
        preview_payload={},
        validation_payload={},
        status_payload={"history": [{"status": "uploaded", "at": utc_now().isoformat()}]},
    )
    db.add(batch)
    db.flush()
    file_model = UploadFileModel(
        id=generate_id("file"),
        batch_id=batch.id,
        file_name=file.filename,
        source_type=requested_source_type,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
        checksum=stored.checksum,
        storage_key=stored.storage_key,
    )
    db.add(file_model)
    db.commit()

    _run_parse_stage(
        db,
        settings,
        batch,
        file_model,
        source_type_hint=source_type,
        require_source_confirmation=source_type is None,
    )
    if batch.status == "validating":
        return validate_upload_file(db, settings, file_model.id)
    return get_upload_file_detail(db, file_model.id)


def confirm_upload_source_type(
    db: Session,
    settings: Settings,
    file_id: str,
    *,
    source_type: str,
    new_entity_name: str | None = None,
) -> UploadFileDetailResponse:
    file_model, batch = _get_file_and_batch(db, file_id)
    selected_source_type = source_type
    custom_entity_name = None
    if new_entity_name and new_entity_name.strip():
        data_source = _create_custom_data_source(db, new_entity_name.strip())
        selected_source_type = data_source.source_type
        custom_entity_name = data_source.name
    elif selected_source_type not in SOURCE_TYPES:
        raise DomainError(code="unsupported_source_type", message="Неподдерживаемый тип источника")

    _run_parse_stage(
        db,
        settings,
        batch,
        file_model,
        source_type_hint=selected_source_type,
        require_source_confirmation=False,
        custom_entity_name=custom_entity_name,
    )
    if batch.status == "validating":
        return validate_upload_file(db, settings, file_id)
    return get_upload_file_detail(db, file_id)


def apply_mapping_template_to_upload(
    db: Session,
    settings: Settings,
    file_id: str,
    template_id: str,
) -> UploadFileDetailResponse:
    template = get_mapping_template(db, template_id)
    mappings = {rule.source_header: rule.canonical_field for rule in template.rules}
    return save_upload_mapping(
        db,
        settings,
        file_id,
        mappings=mappings,
        template_id=template.id,
    )


def list_upload_jobs(db: Session) -> list[UploadJobResponse]:
    return [_legacy_job_from_file(item) for item in list_upload_files(db)]


def get_upload_detail(db: Session, batch_id: str) -> UploadDetailResponse | None:
    try:
        file_model, _ = _get_file_and_batch_by_batch_id(db, batch_id)
    except DomainError:
        return None
    return _legacy_detail(get_upload_file_detail(db, file_model.id))


def create_upload(
    db: Session,
    settings: Settings,
    current_user: User,
    file: UploadFile,
    source_type: str | None = None,
) -> UploadDetailResponse:
    return _legacy_detail(create_upload_file(db, settings, current_user, file, source_type))


def update_mapping(
    db: Session,
    settings: Settings,
    batch_id: str,
    mappings: dict[str, str],
) -> UploadDetailResponse:
    file_model, _ = _get_file_and_batch_by_batch_id(db, batch_id)
    return _legacy_detail(
        save_upload_mapping(db, settings, file_model.id, mappings=mappings, template_id=None)
    )


def apply_upload(db: Session, settings: Settings, batch_id: str) -> ApplyUploadResponse:
    file_model, _ = _get_file_and_batch_by_batch_id(db, batch_id)
    return apply_upload_file(db, settings, file_model.id)
