from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from apps.api.app.api.dependencies import get_settings_dependency, require_capability
from apps.api.app.common.pagination import paginated_response
from apps.api.app.common.schemas import PaginatedResponse
from apps.api.app.core.config import Settings
from apps.api.app.db.models import User
from apps.api.app.db.session import get_db
from apps.api.app.modules.audit.service import record_audit_event
from apps.api.app.modules.mapping.schemas import MappingStateResponse, MappingUpdateRequest
from apps.api.app.modules.uploads.schemas import (
    ApplyUploadResponse,
    UploadBatchDetailResponse,
    UploadBatchSummaryResponse,
    UploadDetailResponse,
    UploadFileDetailResponse,
    UploadFileSummaryResponse,
    UploadIssueResponse,
    UploadJobResponse,
    UploadPreviewResponse,
)
from apps.api.app.modules.uploads.service import (
    apply_upload,
    apply_upload_file,
    create_upload,
    create_upload_file,
    get_upload_batch_detail,
    get_upload_detail,
    get_upload_file_detail,
    get_upload_mapping_state,
    get_upload_preview,
    list_upload_batches_page,
    list_upload_file_issues_page,
    list_upload_files_page,
    list_upload_jobs,
    save_upload_mapping,
    suggest_upload_mapping,
    update_mapping,
    validate_upload_file,
)

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.get("/files", response_model=PaginatedResponse[UploadFileSummaryResponse])
def list_upload_files_route(
    status: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedResponse[UploadFileSummaryResponse]:
    items, total = list_upload_files_page(
        db,
        status=status,
        source_type=source_type,
        page=page,
        page_size=page_size,
    )
    return paginated_response(items, total=total, page=page, page_size=page_size)


@router.post("/files", response_model=UploadFileDetailResponse)
def create_upload_file_route(
    source_type: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    current_user: User = Depends(require_capability("uploads", "write")),
) -> UploadFileDetailResponse:
    detail = create_upload_file(
        db, settings, current_user=current_user, file=file, source_type=source_type
    )
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="uploads.file_uploaded",
        target_type="upload_file",
        target_id=detail.file.id,
        context={"source_type": detail.file.source_type, "status": detail.file.status},
    )
    db.commit()
    return detail


@router.get("/files/{file_id}", response_model=UploadFileDetailResponse)
def get_upload_file_detail_route(
    file_id: str, db: Session = Depends(get_db)
) -> UploadFileDetailResponse:
    return get_upload_file_detail(db, file_id)


@router.get("/files/{file_id}/preview", response_model=UploadPreviewResponse)
def get_upload_preview_route(
    file_id: str, db: Session = Depends(get_db)
) -> UploadPreviewResponse:
    return get_upload_preview(db, file_id)


@router.post("/files/{file_id}/mapping/suggest", response_model=UploadFileDetailResponse)
def suggest_upload_mapping_route(
    file_id: str,
    template_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    current_user: User = Depends(require_capability("uploads", "write")),
) -> UploadFileDetailResponse:
    detail = suggest_upload_mapping(db, settings, file_id, template_id=template_id)
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="uploads.mapping_suggested",
        target_type="upload_file",
        target_id=file_id,
        context={"template_id": template_id, "status": detail.file.status},
    )
    db.commit()
    return detail


@router.get("/files/{file_id}/mapping", response_model=MappingStateResponse)
def get_upload_mapping_route(
    file_id: str, db: Session = Depends(get_db)
) -> MappingStateResponse:
    return get_upload_mapping_state(db, file_id)


@router.post("/files/{file_id}/mapping", response_model=UploadFileDetailResponse)
def save_upload_mapping_route(
    file_id: str,
    payload: MappingUpdateRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    current_user: User = Depends(require_capability("uploads", "write")),
) -> UploadFileDetailResponse:
    detail = save_upload_mapping(
        db,
        settings,
        file_id,
        mappings=payload.mappings,
        template_id=payload.template_id,
    )
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="uploads.mapping_saved",
        target_type="upload_file",
        target_id=file_id,
        context={"template_id": payload.template_id, "mapped_fields": sorted(payload.mappings.keys())},
    )
    db.commit()
    return detail


@router.post("/files/{file_id}/validate", response_model=UploadFileDetailResponse)
def validate_upload_route(
    file_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    current_user: User = Depends(require_capability("uploads", "write")),
) -> UploadFileDetailResponse:
    detail = validate_upload_file(db, settings, file_id)
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="uploads.validated",
        target_type="upload_file",
        target_id=file_id,
        context={"status": detail.file.status, "issues": detail.validation.issue_counts.model_dump(mode="json")},
    )
    db.commit()
    return detail


@router.get("/files/{file_id}/issues", response_model=PaginatedResponse[UploadIssueResponse])
def list_upload_issues_route(
    file_id: str,
    severity: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
) -> PaginatedResponse[UploadIssueResponse]:
    items, total = list_upload_file_issues_page(
        db,
        file_id,
        severity=severity,
        page=page,
        page_size=page_size,
    )
    return paginated_response(items, total=total, page=page, page_size=page_size)


@router.post("/files/{file_id}/apply", response_model=ApplyUploadResponse)
def apply_upload_file_route(
    file_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    current_user: User = Depends(require_capability("uploads", "apply")),
) -> ApplyUploadResponse:
    result = apply_upload_file(db, settings, file_id)
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="uploads.applied",
        target_type="upload_file",
        target_id=file_id,
        context=result.model_dump(mode="json"),
    )
    db.commit()
    return result


@router.get("/batches", response_model=PaginatedResponse[UploadBatchSummaryResponse])
def list_upload_batches_route(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedResponse[UploadBatchSummaryResponse]:
    items, total = list_upload_batches_page(db, page=page, page_size=page_size)
    return paginated_response(items, total=total, page=page, page_size=page_size)


@router.get("/batches/{batch_id}", response_model=UploadBatchDetailResponse)
def get_upload_batch_detail_route(
    batch_id: str, db: Session = Depends(get_db)
) -> UploadBatchDetailResponse:
    return get_upload_batch_detail(db, batch_id)


@router.get("", response_model=list[UploadJobResponse])
def list_upload_jobs_route(db: Session = Depends(get_db)) -> list[UploadJobResponse]:
    return list_upload_jobs(db)


@router.post("", response_model=UploadDetailResponse)
def create_upload_route(
    source_type: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    current_user: User = Depends(require_capability("uploads", "write")),
) -> UploadDetailResponse:
    detail = create_upload(
        db, settings, current_user=current_user, file=file, source_type=source_type
    )
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="uploads.batch_uploaded",
        target_type="upload_batch",
        target_id=detail.job.id,
        context={"source_type": detail.job.source_type, "status": detail.job.state},
    )
    db.commit()
    return detail


@router.get("/{batch_id}", response_model=UploadDetailResponse)
def get_upload_detail_route(batch_id: str, db: Session = Depends(get_db)) -> UploadDetailResponse:
    detail = get_upload_detail(db, batch_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Upload batch not found")
    return detail


@router.post("/{batch_id}/map", response_model=UploadDetailResponse)
def update_mapping_route(
    batch_id: str,
    payload: MappingUpdateRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    current_user: User = Depends(require_capability("uploads", "write")),
) -> UploadDetailResponse:
    detail = update_mapping(db, settings, batch_id=batch_id, mappings=payload.mappings)
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="uploads.batch_mapping_saved",
        target_type="upload_batch",
        target_id=batch_id,
        context={"mapped_fields": sorted(payload.mappings.keys())},
    )
    db.commit()
    return detail


@router.post("/{batch_id}/apply", response_model=ApplyUploadResponse)
def apply_upload_route(
    batch_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    current_user: User = Depends(require_capability("uploads", "apply")),
) -> ApplyUploadResponse:
    result = apply_upload(db, settings, batch_id=batch_id)
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="uploads.batch_applied",
        target_type="upload_batch",
        target_id=batch_id,
        context=result.model_dump(mode="json"),
    )
    db.commit()
    return result
