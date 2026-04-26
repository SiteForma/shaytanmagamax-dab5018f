from __future__ import annotations

from pydantic import Field

from apps.api.app.common.schemas import ORMModel, PaginatedResponse
from apps.api.app.modules.audit.schemas import AuditEventResponse


class AdminUserResponse(ORMModel):
    id: str
    email: str
    full_name: str = Field(alias="fullName")
    is_active: bool = Field(alias="isActive")
    roles: list[str]
    capabilities: list[str]
    created_at: str = Field(alias="createdAt")


class AdminUserRoleUpdateRequest(ORMModel):
    role: str


class AdminJobResponse(ORMModel):
    id: str
    job_name: str = Field(alias="jobName")
    queue_name: str = Field(alias="queueName")
    status: str
    payload: dict[str, object]
    started_at: str | None = Field(default=None, alias="startedAt")
    finished_at: str | None = Field(default=None, alias="finishedAt")
    error_message: str | None = Field(default=None, alias="errorMessage")
    created_at: str = Field(alias="createdAt")
    can_retry: bool = Field(alias="canRetry")


class AdminJobListResponse(PaginatedResponse[AdminJobResponse]):
    pass


class AdminAuditEventListResponse(PaginatedResponse[AuditEventResponse]):
    pass


class AdminSystemFreshnessResponse(ORMModel):
    last_sales_ingest_at: str | None = Field(default=None, alias="lastSalesIngestAt")
    last_stock_snapshot_at: str | None = Field(default=None, alias="lastStockSnapshotAt")
    last_inbound_update_at: str | None = Field(default=None, alias="lastInboundUpdateAt")
    last_quality_run_at: str | None = Field(default=None, alias="lastQualityRunAt")
    last_reserve_refresh_at: str | None = Field(default=None, alias="lastReserveRefreshAt")
    failed_jobs_count: int = Field(alias="failedJobsCount")
    pending_jobs_count: int = Field(alias="pendingJobsCount")
    export_backlog_count: int = Field(alias="exportBacklogCount")
    failed_exports_count: int = Field(alias="failedExportsCount")
    running_exports_count: int = Field(alias="runningExportsCount")


class AdminHealthDetailsResponse(ORMModel):
    app_env: str = Field(alias="appEnv")
    app_debug: bool = Field(alias="appDebug")
    app_release: str | None = Field(default=None, alias="appRelease")
    database_ok: bool = Field(alias="databaseOk")
    redis_configured: bool = Field(alias="redisConfigured")
    redis_ok: bool = Field(alias="redisOk")
    object_storage_mode: str = Field(alias="objectStorageMode")
    object_storage_ok: bool = Field(alias="objectStorageOk")
    analytics_ok: bool = Field(alias="analyticsOk")
    export_root: str = Field(alias="exportRoot")
    export_async_enabled: bool = Field(alias="exportAsyncEnabled")
    export_async_row_threshold: int = Field(alias="exportAsyncRowThreshold")
    assistant_provider: str = Field(alias="assistantProvider")
    sentry_enabled: bool = Field(alias="sentryEnabled")
    otel_enabled: bool = Field(alias="otelEnabled")
    startup_schema_mode: str = Field(alias="startupSchemaMode")
    startup_seed_sample_data: bool = Field(alias="startupSeedSampleData")
    startup_materialize_analytics: bool = Field(alias="startupMaterializeAnalytics")
    worker_queues: list[str] = Field(alias="workerQueues")
    environment_warnings: list[str] = Field(alias="environmentWarnings")
    request_id_header: str = Field(alias="requestIdHeader")
    cors_origins: list[str] = Field(alias="corsOrigins")
