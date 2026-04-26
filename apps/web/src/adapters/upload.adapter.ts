import type {
  AliasEntry,
  IssueCounts,
  MappingField,
  MappingTemplate,
  PaginatedResult,
  UploadFileDetail,
  UploadIssue,
  UploadJob,
  UploadMappingState,
  UploadPreview,
  UploadValidationSummary,
} from "@/types";
import { mapPaginatedResult, type ApiPaginationEnvelope } from "@/adapters/common";

export function issueCountsApiToViewModel(payload: any): IssueCounts {
  return {
    info: payload?.info ?? 0,
    warning: payload?.warning ?? 0,
    error: payload?.error ?? 0,
    critical: payload?.critical ?? 0,
    total: payload?.total ?? 0,
  };
}

export function mappingFieldApiToViewModel(item: any): MappingField {
  return {
    source: item.source,
    canonical: item.canonical,
    confidence: item.confidence,
    status: item.status,
    sample: item.sample ?? undefined,
    candidates: item.candidates ?? [],
    required: item.required ?? false,
  };
}

export function uploadJobApiToViewModel(item: any): UploadJob {
  const sourceDetection = item.source_detection
    ? {
        requiresConfirmation: item.source_detection.requires_confirmation ?? false,
        confirmed: item.source_detection.confirmed ?? false,
        detectedSourceType: item.source_detection.detected_source_type,
        selectedSourceType: item.source_detection.selected_source_type,
        candidates: (item.source_detection.candidates ?? []).map((candidate: any) => ({
          sourceType: candidate.source_type,
          confidence: candidate.confidence ?? 0,
          matchedFields: candidate.matched_fields ?? [],
        })),
        customEntityName: item.source_detection.custom_entity_name ?? null,
      }
    : null;
  return {
    id: item.id,
    batchId: item.batch_id,
    fileName: item.file_name,
    sourceType: item.source_type,
    detectedSourceType: item.detected_source_type ?? item.source_type,
    sizeBytes: item.size_bytes,
    uploadedAt: item.uploaded_at,
    state: item.status ?? item.state,
    rows: item.total_rows ?? item.rows ?? 0,
    issues: item.issue_counts?.total ?? item.issues ?? 0,
    appliedRows: item.applied_rows ?? 0,
    failedRows: item.failed_rows ?? 0,
    warningsCount: item.warnings_count ?? 0,
    canApply: item.readiness?.can_apply ?? false,
    canValidate: item.readiness?.can_validate ?? false,
    canEditMapping: item.readiness?.can_edit_mapping ?? true,
    duplicateOfBatchId: item.duplicate_of_batch_id ?? null,
    sourceDetection,
  };
}

export function uploadPreviewApiToViewModel(item: any): UploadPreview {
  return {
    fileId: item.file_id,
    sourceType: item.source_type,
    detectedSourceType: item.detected_source_type,
    parser: item.parser,
    encoding: item.encoding ?? null,
    headers: item.headers ?? [],
    sampleRows: item.sample_rows ?? [],
    sampleRowCount: item.sample_row_count ?? 0,
    emptyRowCount: item.empty_row_count ?? 0,
  };
}

export function uploadValidationApiToViewModel(item: any): UploadValidationSummary {
  return {
    totalRows: item.total_rows,
    validRows: item.valid_rows,
    failedRows: item.failed_rows,
    warningsCount: item.warnings_count,
    issuesCount: item.issues_count,
    issueCounts: issueCountsApiToViewModel(item.issue_counts),
    hasBlockingIssues: item.has_blocking_issues,
  };
}

export function uploadIssueApiToViewModel(item: any): UploadIssue {
  return {
    id: item.id,
    rowNumber: item.row_number,
    fieldName: item.field_name ?? null,
    code: item.code,
    severity: item.severity,
    message: item.message,
    rawPayload: item.raw_payload ?? null,
  };
}

export function uploadMappingApiToViewModel(item: any): UploadMappingState {
  return {
    sourceType: item.source_type,
    canonicalFields: item.canonical_fields ?? [],
    requiredFields: item.required_fields ?? [],
    supportsApply: item.supports_apply ?? false,
    templateId: item.template_id ?? null,
    suggestions: (item.suggestions ?? []).map(mappingFieldApiToViewModel),
    activeMapping: item.active_mapping ?? {},
  };
}

export function uploadFileDetailApiToViewModel(item: any): UploadFileDetail {
  return {
    file: uploadJobApiToViewModel(item.file),
    preview: uploadPreviewApiToViewModel(item.preview),
    mapping: uploadMappingApiToViewModel(item.mapping),
    validation: uploadValidationApiToViewModel(item.validation),
    jobs: (item.jobs ?? []).map((job: any) => ({
      id: job.id,
      jobName: job.job_name,
      queueName: job.queue_name,
      status: job.status,
      startedAt: job.started_at ?? null,
      finishedAt: job.finished_at ?? null,
      errorMessage: job.error_message ?? null,
    })),
    issuesPreview: (item.issues_preview ?? []).map(uploadIssueApiToViewModel),
  };
}

export function paginatedUploadJobsApiToViewModel(
  payload: ApiPaginationEnvelope<any>,
): PaginatedResult<UploadJob> {
  return mapPaginatedResult(payload, uploadJobApiToViewModel);
}

export function paginatedUploadIssuesApiToViewModel(
  payload: ApiPaginationEnvelope<any>,
): PaginatedResult<UploadIssue> {
  return mapPaginatedResult(payload, uploadIssueApiToViewModel);
}

export function mappingTemplateApiToViewModel(item: any): MappingTemplate {
  return {
    id: item.id,
    name: item.name,
    sourceType: item.source_type,
    version: item.version,
    isDefault: item.is_default,
    isActive: item.is_active,
    requiredFields: item.required_fields ?? [],
    transformationHints: item.transformation_hints ?? {},
    mappings: item.mappings ?? {},
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}

export function aliasEntryApiToViewModel(item: any): AliasEntry {
  return {
    id: item.id,
    alias: item.alias,
    entityId: item.entity_id,
    entityCode: item.entity_code,
    entityName: item.entity_name,
    createdAt: item.created_at,
  };
}
