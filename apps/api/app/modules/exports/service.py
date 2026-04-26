from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.app.common.pagination import page_offset
from apps.api.app.common.utils import utc_now
from apps.api.app.core.config import Settings
from apps.api.app.core.errors import DomainError
from apps.api.app.db.models import Client, ExportJob, JobRun, User
from apps.api.app.modules.access.service import role_codes_for_user
from apps.api.app.modules.dashboard.service import (
    get_exposed_clients,
    get_freshness,
    get_top_risk_skus,
)
from apps.api.app.modules.exports.schemas import (
    ClientExposureExportRequest,
    DashboardTopRiskExportRequest,
    DiyExposureReportPackExportRequest,
    ExportFormat,
    ExportJobResponse,
    QualityIssuesExportRequest,
    StockCoverageExportRequest,
)
from apps.api.app.modules.quality.service import list_quality_issues
from apps.api.app.modules.reserve.service import get_run_detail, get_run_rows
from apps.api.app.modules.stock.service import get_stock_coverage

logger = logging.getLogger(__name__)
ASYNC_ONLY_EXPORT_TYPES = {"diy_exposure_report_pack"}


@dataclass(slots=True)
class ExportSheet:
    name: str
    columns: list[str]
    rows: list[dict[str, Any]]


@dataclass(slots=True)
class ExportPlan:
    export_type: str
    export_format: ExportFormat
    base_name: str
    filters_payload: dict[str, Any]
    summary_payload: dict[str, Any]
    metadata: dict[str, Any]
    sheets: list[ExportSheet]

    @property
    def row_count(self) -> int:
        return sum(len(sheet.rows) for sheet in self.sheets)


def _safe_name(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-zА-Яа-я._-]+", "_", value.strip())
    return normalized.strip("._") or "export"


def _safe_sheet_name(value: str) -> str:
    return _safe_name(value)[:31] or "sheet"


def _export_dir(settings: Settings) -> Path:
    root = Path(settings.export_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _payload_value(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return default


def serialize_export_job(job: ExportJob) -> ExportJobResponse:
    return ExportJobResponse(
        id=job.id,
        exportType=job.export_type,
        status=job.status,
        format=job.format,  # type: ignore[arg-type]
        fileName=job.file_name,
        rowCount=job.row_count,
        requestedById=job.requested_by_id,
        requestedAt=job.created_at.isoformat(),
        completedAt=job.completed_at.isoformat() if job.completed_at else None,
        errorMessage=job.error_message,
        filtersPayload=dict(job.filters_payload or {}),
        summaryPayload=dict(job.summary_payload or {}),
        downloadUrl=f"/api/exports/jobs/{job.id}/download" if job.storage_key and job.status == "completed" else None,
        canDownload=bool(job.storage_key and job.status == "completed"),
    )


def list_export_jobs(db: Session, *, current_user: User, status: str | None = None) -> list[ExportJobResponse]:
    rows = db.scalars(select(ExportJob).order_by(ExportJob.created_at.desc())).all()
    if "admin" not in role_codes_for_user(current_user):
        rows = [row for row in rows if row.requested_by_id == current_user.id]
    if status:
        rows = [row for row in rows if row.status == status]
    return [serialize_export_job(row) for row in rows]


def list_export_jobs_page(
    db: Session,
    *,
    current_user: User,
    status: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[ExportJobResponse], int]:
    stmt = select(ExportJob)
    if "admin" not in role_codes_for_user(current_user):
        stmt = stmt.where(ExportJob.requested_by_id == current_user.id)
    if status:
        stmt = stmt.where(ExportJob.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(ExportJob.created_at.desc())
        .offset(page_offset(page, page_size))
        .limit(page_size)
    ).all()
    return ( [serialize_export_job(row) for row in rows], int(total))


def get_export_job(db: Session, job_id: str) -> ExportJob:
    job = db.get(ExportJob, job_id)
    if job is None:
        raise DomainError(code="export_not_found", message="Экспорт не найден", status_code=404)
    return job


def _assert_download_access(job: ExportJob, current_user: User) -> None:
    if "admin" in role_codes_for_user(current_user):
        return
    if job.requested_by_id != current_user.id:
        raise DomainError(
            code="export_access_denied",
            message="Недостаточно прав для скачивания этого экспорта",
            status_code=403,
        )


def export_download_path(db: Session, settings: Settings, *, job_id: str, current_user: User) -> Path:
    job = get_export_job(db, job_id)
    _assert_download_access(job, current_user)
    if not job.storage_key or job.status != "completed":
        raise DomainError(code="export_not_ready", message="Экспорт ещё не готов", status_code=409)
    path = _export_dir(settings) / job.storage_key
    if not path.exists():
        raise DomainError(code="export_missing", message="Файл экспорта не найден", status_code=404)
    job.download_count += 1
    db.add(job)
    db.commit()
    return path


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in columns})


def _write_xlsx(path: Path, *, sheets: list[ExportSheet], metadata: dict[str, Any]) -> None:
    book = Workbook()
    meta_sheet = book.active
    meta_sheet.title = "meta"
    meta_sheet.append(["Поле", "Значение"])
    for key, value in metadata.items():
        meta_sheet.append([key, value if not isinstance(value, (dict, list)) else str(value)])

    for sheet in sheets:
        data_sheet = book.create_sheet(title=_safe_sheet_name(sheet.name))
        data_sheet.append(sheet.columns)
        for row in sheet.rows:
            data_sheet.append([row.get(column) for column in sheet.columns])
    book.save(path)


def _create_export_job_run(db: Session, export_job_id: str, *, status: str) -> JobRun:
    job_run = JobRun(
        job_name="generate_export",
        queue_name="exports",
        status=status,
        payload={"export_job_id": export_job_id},
        started_at=utc_now() if status == "running" else None,
    )
    db.add(job_run)
    db.flush()
    return job_run


def _start_export_job_run(job_run: JobRun) -> None:
    job_run.status = "running"
    job_run.started_at = utc_now()
    job_run.error_message = None


def _finish_export_job_run(job_run: JobRun, *, error_message: str | None = None) -> None:
    job_run.finished_at = utc_now()
    if error_message:
        job_run.status = "failed"
        job_run.error_message = error_message
    else:
        job_run.status = "completed"


def _enqueue_export_job(settings: Settings, export_job_id: str, job_run_id: str) -> bool:
    if settings.app_env == "test":
        return False
    try:
        from apps.worker.worker_app.tasks import generate_export_job

        generate_export_job.send(export_job_id, job_run_id)
        return True
    except Exception:
        logger.exception("export_job_enqueue_failed", extra={"job_id": job_run_id})
        return False


def _should_run_async(settings: Settings, *, export_type: str, estimated_rows: int) -> bool:
    return settings.export_async_enabled and (
        export_type in ASYNC_ONLY_EXPORT_TYPES
        or estimated_rows >= settings.export_async_row_threshold
    )


def _create_export_job(
    db: Session,
    *,
    current_user: User,
    export_type: str,
    export_format: ExportFormat,
    filters_payload: dict[str, Any],
    summary_payload: dict[str, Any],
    status: str,
) -> ExportJob:
    job = ExportJob(
        requested_by_id=current_user.id,
        export_type=export_type,
        status=status,
        format=export_format,
        filters_payload=filters_payload,
        summary_payload=summary_payload,
    )
    db.add(job)
    db.flush()
    return job


def _build_reserve_run_plan(db: Session, job: ExportJob) -> ExportPlan:
    run_id = str(_payload_value(job.filters_payload, "run_id"))
    detail = get_run_detail(db, run_id)
    if detail is None:
        raise DomainError(code="reserve_run_not_found", message="Расчёт резерва не найден", status_code=404)
    rows = get_run_rows(db, run_id)
    export_rows = [
        {
            "Клиент": row.client_name,
            "Артикул": row.article,
            "Товар": row.product_name,
            "Категория": row.category,
            "Спрос в месяц": row.demand_per_month,
            "Горизонт резерва": row.reserve_months,
            "Коэффициент безопасности": row.safety_factor,
            "Целевой резерв": row.target_reserve_qty,
            "Свободный остаток": row.free_stock,
            "Поставка в горизонте": row.inbound_within_horizon,
            "Доступно": row.available_qty,
            "Дефицит": row.shortage_qty,
            "Покрытие месяцев": row.coverage_months,
            "Статус": row.status,
            "Причина статуса": row.status_reason,
            "Fallback": row.fallback_level,
            "Окно базы": row.basis_window_used,
        }
        for row in rows
    ]
    columns = list(export_rows[0].keys()) if export_rows else ["Клиент", "Артикул", "Товар"]
    return ExportPlan(
        export_type="reserve_run",
        export_format=job.format,  # type: ignore[arg-type]
        base_name=f"reserve_run_{run_id}",
        filters_payload={"run_id": run_id},
        summary_payload={"run_id": run_id, "row_count": len(export_rows)},
        metadata={
            "run_id": run_id,
            "reserve_months": detail.run.reserve_months,
            "safety_factor": detail.run.safety_factor,
            "demand_strategy": detail.run.demand_strategy,
            "summary_payload": detail.run.summary_payload,
        },
        sheets=[ExportSheet(name="reserve_rows", columns=columns, rows=export_rows)],
    )


def _build_stock_coverage_plan(db: Session, job: ExportJob) -> ExportPlan:
    rows = get_stock_coverage(
        db,
        category=_payload_value(job.filters_payload, "category"),
        risk=str(_payload_value(job.filters_payload, "risk", default="all")),
        search=_payload_value(job.filters_payload, "search"),
        sort_by=str(_payload_value(job.filters_payload, "sortBy", "sort_by", default="shortage_qty_total")),
        sort_dir=str(_payload_value(job.filters_payload, "sortDir", "sort_dir", default="desc")),
    )
    export_rows = [
        {
            "Артикул": row.article,
            "Товар": row.product_name,
            "Категория": row.category_name,
            "Склад": row.warehouse,
            "Свободно": row.free,
            "Резерв-подобно": row.reserved_like,
            "Спрос в месяц": row.demand_per_month,
            "Покрытие месяцев": row.coverage_months,
            "Дефицит": row.shortage_qty_total,
            "Клиентов затронуто": row.affected_clients_count,
            "Худший статус": row.worst_status,
            "Поставка в горизонте": row.inbound_qty_within_horizon,
        }
        for row in rows
    ]
    columns = list(export_rows[0].keys()) if export_rows else ["Артикул", "Товар"]
    return ExportPlan(
        export_type="stock_coverage",
        export_format=job.format,  # type: ignore[arg-type]
        base_name="stock_coverage",
        filters_payload=dict(job.filters_payload or {}),
        summary_payload={"row_count": len(export_rows)},
        metadata=dict(job.filters_payload or {}),
        sheets=[ExportSheet(name="stock_coverage", columns=columns, rows=export_rows)],
    )


def _build_dashboard_top_risk_plan(db: Session, job: ExportJob) -> ExportPlan:
    rows = get_top_risk_skus(db)
    export_rows = [
        {
            "Артикул": row.sku_code,
            "Товар": row.product_name,
            "Категория": row.category_name,
            "Клиентов затронуто": row.affected_clients_count,
            "Дефицит": row.shortage_qty_total,
            "Минимальное покрытие": row.min_coverage_months,
            "Худший статус": row.worst_status,
        }
        for row in rows
    ]
    columns = list(export_rows[0].keys()) if export_rows else ["Артикул", "Товар"]
    return ExportPlan(
        export_type="dashboard_top_risk",
        export_format=job.format,  # type: ignore[arg-type]
        base_name="dashboard_top_risk",
        filters_payload=dict(job.filters_payload or {}),
        summary_payload={"row_count": len(export_rows)},
        metadata={"section": "top_risk_skus"},
        sheets=[ExportSheet(name="top_risk_skus", columns=columns, rows=export_rows)],
    )


def _build_quality_issues_plan(db: Session, job: ExportJob) -> ExportPlan:
    rows = list_quality_issues(
        db,
        severity=_payload_value(job.filters_payload, "severity"),
        issue_type=_payload_value(job.filters_payload, "type"),
        search=_payload_value(job.filters_payload, "search"),
        sort_by=str(_payload_value(job.filters_payload, "sortBy", "sort_by", default="detected_at")),
        sort_dir=str(_payload_value(job.filters_payload, "sortDir", "sort_dir", default="desc")),
    )
    export_rows = [
        {
            "Тип": row.type,
            "Важность": row.severity,
            "Сущность": row.entity,
            "Описание": row.description,
            "Источник": row.source,
            "Обнаружено": row.detected_at,
        }
        for row in rows
    ]
    columns = list(export_rows[0].keys()) if export_rows else ["Тип", "Описание"]
    return ExportPlan(
        export_type="quality_issues",
        export_format=job.format,  # type: ignore[arg-type]
        base_name="quality_issues",
        filters_payload=dict(job.filters_payload or {}),
        summary_payload={"row_count": len(export_rows)},
        metadata=dict(job.filters_payload or {}),
        sheets=[ExportSheet(name="quality_issues", columns=columns, rows=export_rows)],
    )


def _build_client_exposure_plan(db: Session, job: ExportJob) -> ExportPlan:
    rows = get_exposed_clients(db)
    export_rows = [
        {
            "Клиент": row.client_name,
            "Позиций под контролем": row.positions_tracked,
            "Критичных позиций": row.critical_positions,
            "Позиции внимания": row.warning_positions,
            "Суммарный дефицит": row.shortage_qty_total,
            "Среднее покрытие": row.avg_coverage_months,
            "Ожидаемое входящее облегчение": row.inbound_relief_qty,
        }
        for row in rows
    ]
    columns = list(export_rows[0].keys()) if export_rows else ["Клиент", "Суммарный дефицит"]
    return ExportPlan(
        export_type="client_exposure",
        export_format=job.format,  # type: ignore[arg-type]
        base_name="diy_client_exposure",
        filters_payload=dict(job.filters_payload or {}),
        summary_payload={"row_count": len(export_rows)},
        metadata={"section": "exposed_clients"},
        sheets=[ExportSheet(name="client_exposure", columns=columns, rows=export_rows)],
    )


def _build_diy_report_pack_plan(db: Session, job: ExportJob) -> ExportPlan:
    if job.format != "xlsx":
        raise DomainError(
            code="report_pack_format_not_supported",
            message="Report pack доступен только в формате XLSX",
            status_code=409,
        )
    clients = get_exposed_clients(db)
    top_risk = get_top_risk_skus(db)
    freshness = get_freshness(db)

    clients_rows = [
        {
            "Клиент": row.client_name,
            "Позиций": row.positions_tracked,
            "Критичных": row.critical_positions,
            "Внимание": row.warning_positions,
            "Дефицит": row.shortage_qty_total,
            "Покрытие": row.avg_coverage_months,
            "Облегчение поставками": row.inbound_relief_qty,
        }
        for row in clients
    ]
    risk_rows = [
        {
            "Артикул": row.sku_code,
            "Товар": row.product_name,
            "Категория": row.category_name,
            "Клиентов затронуто": row.affected_clients_count,
            "Дефицит": row.shortage_qty_total,
            "Мин. покрытие": row.min_coverage_months,
            "Статус": row.worst_status,
        }
        for row in top_risk
    ]
    freshness_rows = [
        {"Метрика": "Последняя загрузка", "Значение": freshness.last_upload_at},
        {"Метрика": "Последний расчёт резерва", "Значение": freshness.last_reserve_run_at},
        {"Метрика": "Открытых quality issues", "Значение": freshness.open_quality_issues},
        {"Метрика": "Freshness hours", "Значение": freshness.freshness_hours},
        {"Метрика": "Latest run id", "Значение": freshness.latest_run_id},
    ]
    return ExportPlan(
        export_type="diy_exposure_report_pack",
        export_format="xlsx",
        base_name="diy_exposure_report_pack",
        filters_payload=dict(job.filters_payload or {}),
        summary_payload={
            "clients_count": len(clients_rows),
            "top_risk_count": len(risk_rows),
        },
        metadata={"section": "diy_exposure_report_pack"},
        sheets=[
            ExportSheet(
                name="exposed_clients",
                columns=list(clients_rows[0].keys()) if clients_rows else ["Клиент"],
                rows=clients_rows,
            ),
            ExportSheet(
                name="top_risk_skus",
                columns=list(risk_rows[0].keys()) if risk_rows else ["Артикул"],
                rows=risk_rows,
            ),
            ExportSheet(
                name="freshness",
                columns=["Метрика", "Значение"],
                rows=freshness_rows,
            ),
        ],
    )


def _build_export_plan(db: Session, job: ExportJob) -> ExportPlan:
    if job.export_type == "reserve_run":
        return _build_reserve_run_plan(db, job)
    if job.export_type == "stock_coverage":
        return _build_stock_coverage_plan(db, job)
    if job.export_type == "dashboard_top_risk":
        return _build_dashboard_top_risk_plan(db, job)
    if job.export_type == "quality_issues":
        return _build_quality_issues_plan(db, job)
    if job.export_type == "client_exposure":
        return _build_client_exposure_plan(db, job)
    if job.export_type == "diy_exposure_report_pack":
        return _build_diy_report_pack_plan(db, job)
    raise DomainError(
        code="export_type_not_supported",
        message="Тип экспорта не поддержан",
        status_code=409,
    )


def _persist_export_artifact(
    db: Session,
    settings: Settings,
    *,
    current_user: User | None,
    job: ExportJob,
    plan: ExportPlan,
) -> None:
    extension = "xlsx" if plan.export_format == "xlsx" else "csv"
    file_name = f"{_safe_name(plan.base_name)}.{extension}"
    storage_key = f"{job.id}_{file_name}"
    path = _export_dir(settings) / storage_key
    if plan.export_format == "xlsx":
        _write_xlsx(
            path,
            sheets=plan.sheets,
            metadata={
                "generated_at": utc_now().isoformat(),
                "generated_by": current_user.email if current_user else job.requested_by_id,
                "export_type": plan.export_type,
                **plan.metadata,
            },
        )
    else:
        if len(plan.sheets) != 1:
            raise DomainError(
                code="multi_sheet_csv_not_supported",
                message="CSV недоступен для мультилистового экспорта",
                status_code=409,
            )
        _write_csv(path, plan.sheets[0].columns, plan.sheets[0].rows)
    job.file_name = file_name
    job.storage_key = storage_key
    job.row_count = plan.row_count
    job.completed_at = utc_now()
    job.summary_payload = {**plan.summary_payload, "file_name": file_name}


def process_export_job(
    db: Session,
    settings: Settings,
    *,
    export_job_id: str,
    job_run_id: str | None = None,
) -> ExportJobResponse:
    job = get_export_job(db, export_job_id)
    current_user = db.get(User, job.requested_by_id) if job.requested_by_id else None
    job_run = db.get(JobRun, job_run_id) if job_run_id else None
    if job_run is None:
        job_run = _create_export_job_run(db, export_job_id, status="running")
    elif job_run.status != "running":
        _start_export_job_run(job_run)

    try:
        job.status = "running"
        job.error_message = None
        db.add(job)
        db.add(job_run)
        db.flush()

        plan = _build_export_plan(db, job)
        _persist_export_artifact(db, settings, current_user=current_user, job=job, plan=plan)
        job.status = "completed"
        _finish_export_job_run(job_run)
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        _finish_export_job_run(job_run, error_message=str(exc))
        logger.exception("export_job_failed", extra={"job_id": job_run.id})
    db.add(job)
    db.add(job_run)
    db.commit()
    db.refresh(job)
    return serialize_export_job(job)


def retry_export_job(db: Session, settings: Settings, *, export_job_id: str) -> JobRun:
    job = get_export_job(db, export_job_id)
    estimated_rows = int(
        _payload_value(
            dict(job.summary_payload or {}),
            "estimated_rows",
            "row_count",
            default=job.row_count or settings.export_async_row_threshold,
        )
    )
    run_async = _should_run_async(settings, export_type=job.export_type, estimated_rows=estimated_rows)
    job.status = "queued" if run_async else "running"
    job.error_message = None
    job.completed_at = None
    job.file_name = None
    job.storage_key = None
    job.download_count = 0
    db.add(job)
    job_run = _create_export_job_run(db, job.id, status="queued" if run_async else "running")
    db.commit()
    db.refresh(job_run)
    if run_async and _enqueue_export_job(settings, job.id, job_run.id):
        return job_run
    process_export_job(db, settings, export_job_id=job.id, job_run_id=job_run.id)
    refreshed = db.get(JobRun, job_run.id)
    assert refreshed is not None
    return refreshed


def _dispatch_export_job(
    db: Session,
    settings: Settings,
    *,
    current_user: User,
    export_type: str,
    export_format: ExportFormat,
    filters_payload: dict[str, Any],
    summary_payload: dict[str, Any],
    estimated_rows: int,
) -> ExportJobResponse:
    run_async = _should_run_async(settings, export_type=export_type, estimated_rows=estimated_rows)
    job = _create_export_job(
        db,
        current_user=current_user,
        export_type=export_type,
        export_format=export_format,
        filters_payload=filters_payload,
        summary_payload=summary_payload,
        status="queued" if run_async else "running",
    )
    job_run = _create_export_job_run(db, job.id, status="queued" if run_async else "running")
    db.commit()
    db.refresh(job)
    if run_async and _enqueue_export_job(settings, job.id, job_run.id):
        return serialize_export_job(job)
    return process_export_job(db, settings, export_job_id=job.id, job_run_id=job_run.id)


def export_reserve_run(
    db: Session,
    settings: Settings,
    *,
    run_id: str,
    export_format: ExportFormat,
    current_user: User,
) -> ExportJobResponse:
    detail = get_run_detail(db, run_id)
    if detail is None:
        raise DomainError(code="reserve_run_not_found", message="Расчёт резерва не найден", status_code=404)
    return _dispatch_export_job(
        db,
        settings,
        current_user=current_user,
        export_type="reserve_run",
        export_format=export_format,
        filters_payload={"run_id": run_id},
        summary_payload={"run_id": run_id, "row_count": detail.run.row_count},
        estimated_rows=detail.run.row_count,
    )


def export_stock_coverage(
    db: Session,
    settings: Settings,
    *,
    payload: StockCoverageExportRequest,
    current_user: User,
) -> ExportJobResponse:
    estimated_rows = len(
        get_stock_coverage(
            db,
            category=payload.category,
            risk=payload.risk,
            search=payload.search,
            sort_by=payload.sort_by,
            sort_dir=payload.sort_dir,
        )
    )
    return _dispatch_export_job(
        db,
        settings,
        current_user=current_user,
        export_type="stock_coverage",
        export_format=payload.format,
        filters_payload=payload.model_dump(mode="json", by_alias=True),
        summary_payload={"estimated_rows": estimated_rows},
        estimated_rows=estimated_rows,
    )


def export_dashboard_top_risk(
    db: Session,
    settings: Settings,
    *,
    payload: DashboardTopRiskExportRequest,
    current_user: User,
) -> ExportJobResponse:
    estimated_rows = len(get_top_risk_skus(db))
    return _dispatch_export_job(
        db,
        settings,
        current_user=current_user,
        export_type="dashboard_top_risk",
        export_format=payload.format,
        filters_payload=payload.model_dump(mode="json", by_alias=True),
        summary_payload={"estimated_rows": estimated_rows},
        estimated_rows=estimated_rows,
    )


def export_quality_issues(
    db: Session,
    settings: Settings,
    *,
    payload: QualityIssuesExportRequest,
    current_user: User,
) -> ExportJobResponse:
    estimated_rows = len(
        list_quality_issues(
            db,
            severity=payload.severity,
            issue_type=payload.type,
            search=payload.search,
            sort_by=payload.sort_by,
            sort_dir=payload.sort_dir,
        )
    )
    return _dispatch_export_job(
        db,
        settings,
        current_user=current_user,
        export_type="quality_issues",
        export_format=payload.format,
        filters_payload=payload.model_dump(mode="json", by_alias=True),
        summary_payload={"estimated_rows": estimated_rows},
        estimated_rows=estimated_rows,
    )


def export_client_exposure(
    db: Session,
    settings: Settings,
    *,
    payload: ClientExposureExportRequest,
    current_user: User,
) -> ExportJobResponse:
    estimated_rows = int(db.scalar(select(func.count()).select_from(Client)) or 0)
    return _dispatch_export_job(
        db,
        settings,
        current_user=current_user,
        export_type="client_exposure",
        export_format=payload.format,
        filters_payload=payload.model_dump(mode="json", by_alias=True),
        summary_payload={"estimated_rows": estimated_rows},
        estimated_rows=estimated_rows,
    )


def export_diy_exposure_report_pack(
    db: Session,
    settings: Settings,
    *,
    payload: DiyExposureReportPackExportRequest,
    current_user: User,
) -> ExportJobResponse:
    if payload.format != "xlsx":
        raise DomainError(
            code="report_pack_format_not_supported",
            message="Report pack доступен только в формате XLSX",
            status_code=409,
        )
    estimated_rows = int(db.scalar(select(func.count()).select_from(Client)) or 0) + len(get_top_risk_skus(db))
    return _dispatch_export_job(
        db,
        settings,
        current_user=current_user,
        export_type="diy_exposure_report_pack",
        export_format="xlsx",
        filters_payload=payload.model_dump(mode="json", by_alias=True),
        summary_payload={"estimated_rows": estimated_rows},
        estimated_rows=estimated_rows,
    )
