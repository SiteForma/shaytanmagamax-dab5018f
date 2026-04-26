from __future__ import annotations

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload

from apps.api.app.core.config import Settings
from apps.api.app.core.errors import DomainError
from apps.api.app.db.models import (
    ExportJob,
    JobRun,
    QualityIssue,
    Role,
    UploadBatch,
    User,
    UserRole,
)
from apps.api.app.modules.access.service import resolve_user_capabilities
from apps.api.app.modules.admin.schemas import (
    AdminHealthDetailsResponse,
    AdminJobResponse,
    AdminSystemFreshnessResponse,
    AdminUserResponse,
)
from apps.api.app.modules.analytics.service import materialize_analytics
from apps.api.app.modules.audit.schemas import AuditEventResponse
from apps.api.app.modules.audit.service import list_audit_events, list_audit_events_page
from apps.api.app.modules.dashboard.service import get_freshness
from apps.api.app.modules.exports.service import retry_export_job
from apps.api.app.modules.health.service import collect_readiness
from apps.api.app.modules.uploads.service import apply_upload_file, validate_upload_file


def list_admin_users(db: Session) -> list[AdminUserResponse]:
    rows = (
        db.scalars(
            select(User)
            .options(joinedload(User.roles).joinedload(UserRole.role))
            .order_by(User.created_at.desc())
        )
        .unique()
        .all()
    )
    return [
        AdminUserResponse(
            id=user.id,
            email=user.email,
            fullName=user.full_name,
            isActive=user.is_active,
            roles=[assignment.role.code for assignment in user.roles],
            capabilities=resolve_user_capabilities(db, user),
            createdAt=user.created_at.isoformat(),
        )
        for user in rows
    ]


def update_admin_user_role(db: Session, *, user_id: str, role_code: str) -> AdminUserResponse:
    user = db.scalar(
        select(User)
        .options(joinedload(User.roles).joinedload(UserRole.role))
        .where(User.id == user_id)
    )
    if user is None:
        raise DomainError(code="user_not_found", message="Пользователь не найден", status_code=404)
    role = db.scalar(select(Role).where(Role.code == role_code))
    if role is None:
        raise DomainError(code="role_not_found", message="Роль не найдена", status_code=404)

    db.query(UserRole).filter(UserRole.user_id == user.id).delete()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    refreshed = db.scalar(
        select(User)
        .options(joinedload(User.roles).joinedload(UserRole.role))
        .where(User.id == user_id)
    )
    assert refreshed is not None
    return AdminUserResponse(
        id=refreshed.id,
        email=refreshed.email,
        fullName=refreshed.full_name,
        isActive=refreshed.is_active,
        roles=[assignment.role.code for assignment in refreshed.roles],
        capabilities=resolve_user_capabilities(db, refreshed),
        createdAt=refreshed.created_at.isoformat(),
    )


def _can_retry(job: JobRun) -> bool:
    return job.job_name in {
        "validate_upload",
        "apply_upload",
        "refresh_analytics",
        "generate_export",
    } and job.status in {
        "failed",
        "completed",
    }


def serialize_admin_job(job: JobRun) -> AdminJobResponse:
    return AdminJobResponse(
        id=job.id,
        jobName=job.job_name,
        queueName=job.queue_name,
        status=job.status,
        payload=dict(job.payload or {}),
        startedAt=job.started_at.isoformat() if job.started_at else None,
        finishedAt=job.finished_at.isoformat() if job.finished_at else None,
        errorMessage=job.error_message,
        createdAt=job.created_at.isoformat(),
        canRetry=_can_retry(job),
    )


def list_admin_jobs(
    db: Session,
    *,
    status: str | None = None,
    queue_name: str | None = None,
    job_name: str | None = None,
) -> list[AdminJobResponse]:
    rows = db.scalars(select(JobRun).order_by(JobRun.created_at.desc())).all()
    if status:
        rows = [row for row in rows if row.status == status]
    if queue_name:
        rows = [row for row in rows if row.queue_name == queue_name]
    if job_name:
        rows = [row for row in rows if row.job_name == job_name]
    return [serialize_admin_job(row) for row in rows]


def list_admin_jobs_page(
    db: Session,
    *,
    status: str | None = None,
    queue_name: str | None = None,
    job_name: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[AdminJobResponse], int]:
    stmt = select(JobRun)
    if status:
        stmt = stmt.where(JobRun.status == status)
    if queue_name:
        stmt = stmt.where(JobRun.queue_name == queue_name)
    if job_name:
        stmt = stmt.where(JobRun.job_name == job_name)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(JobRun.created_at.desc())
        .offset(max(page - 1, 0) * page_size)
        .limit(page_size)
    ).all()
    return ([serialize_admin_job(row) for row in rows], int(total))


def get_admin_job(db: Session, job_id: str) -> AdminJobResponse:
    job = db.get(JobRun, job_id)
    if job is None:
        raise DomainError(code="job_not_found", message="Задача не найдена", status_code=404)
    return serialize_admin_job(job)


def retry_admin_job(db: Session, settings: Settings, *, job_id: str) -> AdminJobResponse:
    job = db.get(JobRun, job_id)
    if job is None:
        raise DomainError(code="job_not_found", message="Задача не найдена", status_code=404)
    if not _can_retry(job):
        raise DomainError(
            code="job_retry_not_supported", message="Безопасный retry для этой задачи не поддержан"
        )

    file_id = str(job.payload.get("file_id", "")) if job.payload else ""
    refreshed_job: JobRun | None = None
    if job.job_name == "validate_upload":
        validate_upload_file(db, settings, file_id)
    elif job.job_name == "apply_upload":
        apply_upload_file(db, settings, file_id)
    elif job.job_name == "refresh_analytics":
        materialize_analytics(db, settings)
    elif job.job_name == "generate_export":
        export_job_id = str(job.payload.get("export_job_id", "")) if job.payload else ""
        refreshed_job = retry_export_job(db, settings, export_job_id=export_job_id)
    if refreshed_job is not None:
        return serialize_admin_job(refreshed_job)
    latest = db.scalars(select(JobRun).order_by(JobRun.created_at.desc())).first()
    return serialize_admin_job(latest or job)


def list_admin_audit_events(
    db: Session,
    *,
    action: str | None = None,
    target_type: str | None = None,
) -> list[AuditEventResponse]:
    return list_audit_events(db, action=action, target_type=target_type)


def list_admin_audit_events_page(
    db: Session,
    *,
    action: str | None = None,
    target_type: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[AuditEventResponse], int]:
    return list_audit_events_page(
        db,
        action=action,
        target_type=target_type,
        page=page,
        page_size=page_size,
    )


def get_admin_system_freshness(db: Session) -> AdminSystemFreshnessResponse:
    freshness = get_freshness(db)
    last_batch_by_type: dict[str, str | None] = {}
    for source_type in ("sales", "stock", "inbound"):
        batch = db.scalars(
            select(UploadBatch)
            .where(UploadBatch.source_type == source_type)
            .order_by(desc(UploadBatch.created_at))
        ).first()
        last_batch_by_type[source_type] = batch.created_at.isoformat() if batch else None
    last_quality = db.scalars(select(QualityIssue).order_by(desc(QualityIssue.detected_at))).first()
    failed_jobs = db.query(JobRun).filter(JobRun.status == "failed").count()
    pending_jobs = db.query(JobRun).filter(JobRun.status.in_(["queued", "running"])).count()
    export_backlog = db.query(ExportJob).filter(ExportJob.status.in_(["queued", "running"])).count()
    failed_exports = db.query(ExportJob).filter(ExportJob.status == "failed").count()
    running_exports = db.query(ExportJob).filter(ExportJob.status == "running").count()
    return AdminSystemFreshnessResponse(
        lastSalesIngestAt=last_batch_by_type["sales"],
        lastStockSnapshotAt=last_batch_by_type["stock"],
        lastInboundUpdateAt=last_batch_by_type["inbound"],
        lastQualityRunAt=last_quality.detected_at.isoformat() if last_quality else None,
        lastReserveRefreshAt=freshness.last_reserve_run_at,
        failedJobsCount=failed_jobs,
        pendingJobsCount=pending_jobs,
        exportBacklogCount=export_backlog,
        failedExportsCount=failed_exports,
        runningExportsCount=running_exports,
    )


def get_admin_health_details(db: Session, settings: Settings) -> AdminHealthDetailsResponse:
    readiness = collect_readiness(db, settings)
    database_ok = bool(readiness["database_ok"])
    environment_warnings: list[str] = list(readiness.get("configuration_errors", []))
    if settings.app_env == "production" and settings.app_debug:
        environment_warnings.append("В боевом окружении включён debug-режим")
    if settings.app_env != "development" and settings.jwt_secret == "change-me-for-production":
        environment_warnings.append("Используется дефолтный JWT secret")
    if settings.app_env != "development" and not settings.app_release:
        environment_warnings.append("APP_RELEASE не задан")
    if settings.app_env == "production" and settings.export_async_enabled is False:
        environment_warnings.append("Крупные экспорты не переведены в асинхронный режим")
    if settings.app_env != "development" and not settings.sentry_dsn:
        environment_warnings.append("Sentry не настроен")
    if settings.app_env != "development" and not settings.otel_enabled:
        environment_warnings.append("OpenTelemetry выключен")
    if settings.app_env == "production" and settings.startup_schema_mode != "migrations_only":
        environment_warnings.append("Режим схемы должен быть migrations_only")
    return AdminHealthDetailsResponse(
        appEnv=settings.app_env,
        appDebug=settings.app_debug,
        appRelease=settings.app_release,
        databaseOk=database_ok,
        redisConfigured=bool(settings.redis_url),
        redisOk=bool(readiness["redis_ok"]),
        objectStorageMode=settings.object_storage_mode,
        objectStorageOk=bool(readiness["object_storage_ok"]),
        analyticsOk=bool(readiness["analytics_ok"]),
        exportRoot=settings.export_root,
        exportAsyncEnabled=settings.export_async_enabled,
        exportAsyncRowThreshold=settings.export_async_row_threshold,
        assistantProvider=(
            settings.assistant_provider if settings.assistant_llm_enabled else "deterministic"
        ),
        sentryEnabled=bool(settings.sentry_dsn),
        otelEnabled=settings.otel_enabled,
        startupSchemaMode=settings.startup_schema_mode,
        startupSeedSampleData=settings.startup_seed_sample_data,
        startupMaterializeAnalytics=settings.startup_materialize_analytics,
        workerQueues=["ingestion", "analytics", "exports"],
        environmentWarnings=environment_warnings,
        requestIdHeader="X-Request-Id",
        corsOrigins=settings.cors_origin_list,
    )
