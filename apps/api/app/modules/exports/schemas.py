from __future__ import annotations

from typing import Literal

from pydantic import Field

from apps.api.app.common.schemas import ORMModel, PaginatedResponse

ExportFormat = Literal["csv", "xlsx"]


class ExportJobResponse(ORMModel):
    id: str
    export_type: str = Field(alias="exportType")
    status: str
    format: ExportFormat
    file_name: str | None = Field(default=None, alias="fileName")
    row_count: int = Field(alias="rowCount")
    requested_by_id: str | None = Field(default=None, alias="requestedById")
    requested_at: str = Field(alias="requestedAt")
    completed_at: str | None = Field(default=None, alias="completedAt")
    error_message: str | None = Field(default=None, alias="errorMessage")
    filters_payload: dict[str, object] = Field(alias="filtersPayload")
    summary_payload: dict[str, object] = Field(alias="summaryPayload")
    download_url: str | None = Field(default=None, alias="downloadUrl")
    can_download: bool = Field(alias="canDownload")


class ExportJobListResponse(PaginatedResponse[ExportJobResponse]):
    pass


class StockCoverageExportRequest(ORMModel):
    format: ExportFormat = "xlsx"
    category: str | None = None
    risk: str = "all"
    search: str | None = None
    sort_by: str = Field(default="shortage_qty_total", alias="sortBy")
    sort_dir: str = Field(default="desc", alias="sortDir")


class QualityIssuesExportRequest(ORMModel):
    format: ExportFormat = "xlsx"
    severity: str | None = None
    type: str | None = None
    search: str | None = None
    sort_by: str = Field(default="detected_at", alias="sortBy")
    sort_dir: str = Field(default="desc", alias="sortDir")


class DashboardTopRiskExportRequest(ORMModel):
    format: ExportFormat = "xlsx"


class ClientExposureExportRequest(ORMModel):
    format: ExportFormat = "xlsx"


class DiyExposureReportPackExportRequest(ORMModel):
    format: Literal["xlsx"] = "xlsx"
