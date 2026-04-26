from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from apps.api.app.api.dependencies import get_settings_dependency, require_capability
from apps.api.app.common.pagination import paginated_response
from apps.api.app.common.schemas import PaginatedResponse
from apps.api.app.core.config import Settings
from apps.api.app.core.errors import DomainError
from apps.api.app.db.models import User
from apps.api.app.db.session import get_db
from apps.api.app.modules.audit.service import record_audit_event
from apps.api.app.modules.exports.schemas import (
    ClientExposureExportRequest,
    DashboardTopRiskExportRequest,
    DiyExposureReportPackExportRequest,
    ExportJobListResponse,
    ExportJobResponse,
    QualityIssuesExportRequest,
    StockCoverageExportRequest,
)
from apps.api.app.modules.exports.service import (
    export_client_exposure,
    export_dashboard_top_risk,
    export_diy_exposure_report_pack,
    export_download_path,
    export_quality_issues,
    export_reserve_run,
    export_stock_coverage,
    get_export_job,
    list_export_jobs_page,
    serialize_export_job,
)

router = APIRouter(prefix="/exports", tags=["exports"])


@router.post("/reserve-runs/{run_id}", response_model=ExportJobResponse)
def export_reserve_run_route(
    run_id: str,
    format: str = Query(default="xlsx", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    current_user: User = Depends(require_capability("exports", "generate")),
) -> ExportJobResponse:
    job = export_reserve_run(
        db,
        settings,
        run_id=run_id,
        export_format=format,  # type: ignore[arg-type]
        current_user=current_user,
    )
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="exports.generate",
        target_type="export_job",
        target_id=job.id,
        context={"export_type": job.export_type, "format": job.format, "run_id": run_id},
    )
    db.commit()
    return job


@router.post("/stock-coverage", response_model=ExportJobResponse)
def export_stock_coverage_route(
    payload: StockCoverageExportRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    current_user: User = Depends(require_capability("exports", "generate")),
) -> ExportJobResponse:
    job = export_stock_coverage(db, settings, payload=payload, current_user=current_user)
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="exports.generate",
        target_type="export_job",
        target_id=job.id,
        context={"export_type": job.export_type, "filters": payload.model_dump(mode="json", by_alias=True)},
    )
    db.commit()
    return job


@router.post("/dashboard/top-risk", response_model=ExportJobResponse)
def export_dashboard_top_risk_route(
    payload: DashboardTopRiskExportRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    current_user: User = Depends(require_capability("exports", "generate")),
) -> ExportJobResponse:
    job = export_dashboard_top_risk(db, settings, payload=payload, current_user=current_user)
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="exports.generate",
        target_type="export_job",
        target_id=job.id,
        context={"export_type": job.export_type},
    )
    db.commit()
    return job


@router.post("/quality/issues", response_model=ExportJobResponse)
def export_quality_issues_route(
    payload: QualityIssuesExportRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    current_user: User = Depends(require_capability("exports", "generate")),
) -> ExportJobResponse:
    job = export_quality_issues(db, settings, payload=payload, current_user=current_user)
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="exports.generate",
        target_type="export_job",
        target_id=job.id,
        context={"export_type": job.export_type, "filters": payload.model_dump(mode="json", by_alias=True)},
    )
    db.commit()
    return job


@router.post("/clients/exposure", response_model=ExportJobResponse)
def export_client_exposure_route(
    payload: ClientExposureExportRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    current_user: User = Depends(require_capability("exports", "generate")),
) -> ExportJobResponse:
    job = export_client_exposure(db, settings, payload=payload, current_user=current_user)
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="exports.generate",
        target_type="export_job",
        target_id=job.id,
        context={"export_type": job.export_type, "filters": payload.model_dump(mode="json", by_alias=True)},
    )
    db.commit()
    return job


@router.post("/report-packs/diy-exposure", response_model=ExportJobResponse)
def export_diy_exposure_report_pack_route(
    payload: DiyExposureReportPackExportRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    current_user: User = Depends(require_capability("exports", "generate")),
) -> ExportJobResponse:
    job = export_diy_exposure_report_pack(db, settings, payload=payload, current_user=current_user)
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="exports.generate",
        target_type="export_job",
        target_id=job.id,
        context={"export_type": job.export_type, "filters": payload.model_dump(mode="json", by_alias=True)},
    )
    db.commit()
    return job


@router.get("/jobs", response_model=PaginatedResponse[ExportJobResponse])
def list_export_jobs_route(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_capability("exports", "download")),
) -> ExportJobListResponse:
    items, total = list_export_jobs_page(
        db,
        current_user=current_user,
        status=status,
        page=page,
        page_size=page_size,
    )
    return ExportJobListResponse.model_validate(
        paginated_response(items, total=total, page=page, page_size=page_size)
    )


@router.get("/jobs/{job_id}", response_model=ExportJobResponse)
def get_export_job_route(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_capability("exports", "download")),
) -> ExportJobResponse:
    job = get_export_job(db, job_id)
    if "admin" not in {role.role.code for role in current_user.roles} and job.requested_by_id != current_user.id:
        raise DomainError(
            code="export_access_denied",
            message="Недостаточно прав для просмотра этого экспорта",
            status_code=403,
        )
    return serialize_export_job(job)


@router.get("/jobs/{job_id}/download")
def download_export_job_route(
    job_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    current_user: User = Depends(require_capability("exports", "download")),
) -> FileResponse:
    path = export_download_path(db, settings, job_id=job_id, current_user=current_user)
    job = get_export_job(db, job_id)
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="exports.download",
        target_type="export_job",
        target_id=job_id,
        context={"file_name": job.file_name},
    )
    db.commit()
    return FileResponse(path, filename=job.file_name or path.name)
