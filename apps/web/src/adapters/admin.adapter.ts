import type {
  AdminHealthDetails,
  AdminJob,
  AdminSystemFreshness,
  AdminUser,
  AuditEvent,
  PaginatedResult,
} from "@/types";
import { mapPaginatedResult, type ApiPaginationEnvelope } from "@/adapters/common";

export function adminUserApiToViewModel(item: any): AdminUser {
  return {
    id: item.id,
    email: item.email,
    fullName: item.full_name ?? item.fullName,
    isActive: item.is_active ?? item.isActive,
    roles: item.roles ?? [],
    capabilities: item.capabilities ?? [],
    createdAt: item.created_at ?? item.createdAt,
  };
}

export function adminJobApiToViewModel(item: any): AdminJob {
  return {
    id: item.id,
    jobName: item.job_name ?? item.jobName,
    queueName: item.queue_name ?? item.queueName,
    status: item.status,
    payload: item.payload ?? {},
    startedAt: item.started_at ?? item.startedAt ?? null,
    finishedAt: item.finished_at ?? item.finishedAt ?? null,
    errorMessage: item.error_message ?? item.errorMessage ?? null,
    createdAt: item.created_at ?? item.createdAt,
    canRetry: item.can_retry ?? item.canRetry ?? false,
  };
}

export function auditEventApiToViewModel(item: any): AuditEvent {
  return {
    id: item.id,
    actorUserId: item.actor_user_id ?? item.actorUserId ?? null,
    action: item.action,
    targetType: item.target_type ?? item.targetType,
    targetId: item.target_id ?? item.targetId ?? null,
    status: item.status,
    traceId: item.trace_id ?? item.traceId ?? null,
    requestId: item.request_id ?? item.requestId ?? null,
    createdAt: item.created_at ?? item.createdAt,
    context: item.context ?? {},
  };
}

export function paginatedAdminJobsApiToViewModel(
  payload: ApiPaginationEnvelope<any>,
): PaginatedResult<AdminJob> {
  return mapPaginatedResult(payload, adminJobApiToViewModel);
}

export function paginatedAuditEventsApiToViewModel(
  payload: ApiPaginationEnvelope<any>,
): PaginatedResult<AuditEvent> {
  return mapPaginatedResult(payload, auditEventApiToViewModel);
}

export function adminSystemFreshnessApiToViewModel(payload: any): AdminSystemFreshness {
  return {
    lastSalesIngestAt: payload.last_sales_ingest_at ?? payload.lastSalesIngestAt ?? null,
    lastStockSnapshotAt: payload.last_stock_snapshot_at ?? payload.lastStockSnapshotAt ?? null,
    lastInboundUpdateAt: payload.last_inbound_update_at ?? payload.lastInboundUpdateAt ?? null,
    lastQualityRunAt: payload.last_quality_run_at ?? payload.lastQualityRunAt ?? null,
    lastReserveRefreshAt: payload.last_reserve_refresh_at ?? payload.lastReserveRefreshAt ?? null,
    failedJobsCount: payload.failed_jobs_count ?? payload.failedJobsCount ?? 0,
    pendingJobsCount: payload.pending_jobs_count ?? payload.pendingJobsCount ?? 0,
    exportBacklogCount: payload.export_backlog_count ?? payload.exportBacklogCount ?? 0,
    failedExportsCount: payload.failed_exports_count ?? payload.failedExportsCount ?? 0,
    runningExportsCount: payload.running_exports_count ?? payload.runningExportsCount ?? 0,
  };
}

export function adminHealthDetailsApiToViewModel(payload: any): AdminHealthDetails {
  return {
    appEnv: payload.app_env ?? payload.appEnv,
    appDebug: payload.app_debug ?? payload.appDebug ?? false,
    appRelease: payload.app_release ?? payload.appRelease ?? null,
    databaseOk: payload.database_ok ?? payload.databaseOk,
    redisConfigured: payload.redis_configured ?? payload.redisConfigured ?? false,
    objectStorageMode: payload.object_storage_mode ?? payload.objectStorageMode,
    exportRoot: payload.export_root ?? payload.exportRoot,
    exportAsyncEnabled: payload.export_async_enabled ?? payload.exportAsyncEnabled ?? false,
    exportAsyncRowThreshold: payload.export_async_row_threshold ?? payload.exportAsyncRowThreshold ?? 0,
    assistantProvider: payload.assistant_provider ?? payload.assistantProvider,
    sentryEnabled: payload.sentry_enabled ?? payload.sentryEnabled ?? false,
    otelEnabled: payload.otel_enabled ?? payload.otelEnabled ?? false,
    startupSchemaMode: payload.startup_schema_mode ?? payload.startupSchemaMode,
    startupSeedSampleData: payload.startup_seed_sample_data ?? payload.startupSeedSampleData ?? false,
    startupMaterializeAnalytics:
      payload.startup_materialize_analytics ?? payload.startupMaterializeAnalytics ?? false,
    workerQueues: payload.worker_queues ?? payload.workerQueues ?? [],
    environmentWarnings: payload.environment_warnings ?? payload.environmentWarnings ?? [],
    requestIdHeader: payload.request_id_header ?? payload.requestIdHeader,
    corsOrigins: payload.cors_origins ?? payload.corsOrigins ?? [],
  };
}
