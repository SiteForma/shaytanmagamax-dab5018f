from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.app.api.dependencies import get_settings_dependency, require_capability
from apps.api.app.common.pagination import paginated_response
from apps.api.app.common.schemas import PaginatedResponse
from apps.api.app.core.config import Settings
from apps.api.app.db.models import User
from apps.api.app.db.session import get_db
from apps.api.app.modules.admin.schemas import (
    AdminHealthDetailsResponse,
    AdminJobResponse,
    AdminSystemFreshnessResponse,
    AdminUserResponse,
    AdminUserRoleUpdateRequest,
)
from apps.api.app.modules.admin.service import (
    get_admin_health_details,
    get_admin_job,
    get_admin_system_freshness,
    list_admin_audit_events_page,
    list_admin_jobs_page,
    list_admin_users,
    retry_admin_job,
    update_admin_user_role,
)
from apps.api.app.modules.audit.schemas import AuditEventResponse
from apps.api.app.modules.audit.service import record_audit_event

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserResponse])
def list_admin_users_route(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_capability("admin", "read")),
) -> list[AdminUserResponse]:
    return list_admin_users(db)


@router.patch("/users/{user_id}/role", response_model=AdminUserResponse)
def update_admin_user_role_route(
    user_id: str,
    payload: AdminUserRoleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_capability("admin", "manage-users")),
) -> AdminUserResponse:
    user = update_admin_user_role(db, user_id=user_id, role_code=payload.role)
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="admin.user_role_changed",
        target_type="user",
        target_id=user_id,
        context={"role": payload.role},
    )
    db.commit()
    return user


@router.get("/audit-events", response_model=PaginatedResponse[AuditEventResponse])
def list_admin_audit_events_route(
    action: str | None = Query(default=None),
    target_type: str | None = Query(default=None, alias="targetType"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_capability("admin", "read")),
):
    items, total = list_admin_audit_events_page(
        db,
        action=action,
        target_type=target_type,
        page=page,
        page_size=page_size,
    )
    return paginated_response(items, total=total, page=page, page_size=page_size)


@router.get("/jobs", response_model=PaginatedResponse[AdminJobResponse])
def list_admin_jobs_route(
    status: str | None = Query(default=None),
    queue_name: str | None = Query(default=None, alias="queueName"),
    job_name: str | None = Query(default=None, alias="jobName"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_capability("admin", "read")),
):
    items, total = list_admin_jobs_page(
        db,
        status=status,
        queue_name=queue_name,
        job_name=job_name,
        page=page,
        page_size=page_size,
    )
    return paginated_response(items, total=total, page=page, page_size=page_size)


@router.get("/jobs/{job_id}", response_model=AdminJobResponse)
def get_admin_job_route(
    job_id: str,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_capability("admin", "read")),
) -> AdminJobResponse:
    return get_admin_job(db, job_id)


@router.post("/jobs/{job_id}/retry", response_model=AdminJobResponse)
def retry_admin_job_route(
    job_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    current_user: User = Depends(require_capability("admin", "read")),
) -> AdminJobResponse:
    job = retry_admin_job(db, settings, job_id=job_id)
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="admin.job_retry",
        target_type="job_run",
        target_id=job_id,
        context={"retried_job_name": job.job_name},
    )
    db.commit()
    return job


@router.get("/system/freshness", response_model=AdminSystemFreshnessResponse)
def admin_system_freshness_route(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_capability("admin", "read")),
) -> AdminSystemFreshnessResponse:
    return get_admin_system_freshness(db)


@router.get("/system/health-details", response_model=AdminHealthDetailsResponse)
def admin_health_details_route(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    _current_user: User = Depends(require_capability("admin", "read")),
) -> AdminHealthDetailsResponse:
    return get_admin_health_details(db, settings)
