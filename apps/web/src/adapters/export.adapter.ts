import type { ExportJob, PaginatedResult } from "@/types";
import { mapPaginatedResult, type ApiPaginationEnvelope } from "@/adapters/common";

export function exportJobApiToViewModel(item: any): ExportJob {
  return {
    id: item.id,
    exportType: item.export_type ?? item.exportType,
    status: item.status,
    format: item.format,
    fileName: item.file_name ?? item.fileName ?? null,
    rowCount: item.row_count ?? item.rowCount ?? 0,
    requestedById: item.requested_by_id ?? item.requestedById ?? null,
    requestedAt: item.requested_at ?? item.requestedAt,
    completedAt: item.completed_at ?? item.completedAt ?? null,
    errorMessage: item.error_message ?? item.errorMessage ?? null,
    filtersPayload: item.filters_payload ?? item.filtersPayload ?? {},
    summaryPayload: item.summary_payload ?? item.summaryPayload ?? {},
    downloadUrl: item.download_url ?? item.downloadUrl ?? null,
    canDownload: item.can_download ?? item.canDownload ?? false,
  };
}

export function paginatedExportJobsApiToViewModel(
  payload: ApiPaginationEnvelope<any>,
): PaginatedResult<ExportJob> {
  return mapPaginatedResult(payload, exportJobApiToViewModel);
}
