from __future__ import annotations

from pydantic import Field

from apps.api.app.common.schemas import ORMModel
from apps.api.app.modules.mapping.schemas import MappingFieldResponse, MappingStateResponse


class IssueCountsResponse(ORMModel):
    info: int = 0
    warning: int = 0
    error: int = 0
    critical: int = 0
    total: int = 0


class UploadReadinessResponse(ORMModel):
    can_apply: bool
    can_validate: bool
    can_edit_mapping: bool


class UploadSourceTypeCandidateResponse(ORMModel):
    source_type: str
    confidence: float
    matched_fields: list[str] = Field(default_factory=list)


class UploadSourceDetectionResponse(ORMModel):
    requires_confirmation: bool
    confirmed: bool
    detected_source_type: str
    selected_source_type: str
    candidates: list[UploadSourceTypeCandidateResponse] = Field(default_factory=list)
    custom_entity_name: str | None = None


class UploadSourceTypeUpdateRequest(ORMModel):
    source_type: str
    new_entity_name: str | None = None


class UploadJobRunResponse(ORMModel):
    id: str
    job_name: str
    queue_name: str
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    error_message: str | None = None


class UploadIssueResponse(ORMModel):
    id: str
    row_number: int
    field_name: str | None = None
    code: str
    severity: str
    message: str
    raw_payload: dict[str, object] | None = None


class UploadPreviewResponse(ORMModel):
    file_id: str
    source_type: str
    detected_source_type: str
    parser: str
    encoding: str | None = None
    headers: list[str]
    sample_rows: list[dict[str, object | None]]
    sample_row_count: int
    empty_row_count: int


class UploadValidationSummaryResponse(ORMModel):
    total_rows: int
    valid_rows: int
    failed_rows: int
    warnings_count: int
    issues_count: int
    issue_counts: IssueCountsResponse
    has_blocking_issues: bool


class UploadFileSummaryResponse(ORMModel):
    id: str
    batch_id: str
    file_name: str
    source_type: str
    detected_source_type: str
    uploaded_at: str
    status: str
    size_bytes: int
    mime_type: str
    checksum: str
    storage_key: str
    parsing_version: str
    normalization_version: str
    mapping_template_id: str | None = None
    uploaded_by_id: str | None = None
    total_rows: int
    applied_rows: int
    failed_rows: int
    warnings_count: int
    issue_counts: IssueCountsResponse
    duplicate_of_batch_id: str | None = None
    is_duplicate: bool = False
    readiness: UploadReadinessResponse
    source_detection: UploadSourceDetectionResponse | None = None


class UploadFileDetailResponse(ORMModel):
    file: UploadFileSummaryResponse
    preview: UploadPreviewResponse
    mapping: MappingStateResponse
    validation: UploadValidationSummaryResponse
    jobs: list[UploadJobRunResponse]
    issues_preview: list[UploadIssueResponse] = Field(default_factory=list)


class UploadBatchSummaryResponse(ORMModel):
    id: str
    source_type: str
    status: str
    uploaded_at: str
    file_count: int
    total_rows: int
    issue_counts: IssueCountsResponse


class UploadBatchDetailResponse(ORMModel):
    batch: UploadBatchSummaryResponse
    files: list[UploadFileSummaryResponse]
    jobs: list[UploadJobRunResponse]


class ApplyUploadResponse(ORMModel):
    file_id: str
    batch_id: str
    status: str
    applied_rows: int
    failed_rows: int
    warnings_count: int
    issue_counts: IssueCountsResponse


class UploadJobResponse(ORMModel):
    id: str
    file_name: str
    source_type: str
    size_bytes: int
    uploaded_at: str
    state: str
    rows: int
    issues: int


class UploadDetailResponse(ORMModel):
    job: UploadJobResponse
    mapping_fields: list[MappingFieldResponse]
    issues: list[UploadIssueResponse]
