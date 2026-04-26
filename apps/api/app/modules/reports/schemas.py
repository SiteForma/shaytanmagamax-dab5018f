from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import Field

from apps.api.app.common.schemas import ORMModel


class ManagementReportImportResponse(ORMModel):
    id: str
    file_name: str = Field(alias="fileName")
    checksum: str
    report_year: int | None = Field(default=None, alias="reportYear")
    sheet_count: int = Field(alias="sheetCount")
    raw_row_count: int = Field(alias="rawRowCount")
    metric_count: int = Field(alias="metricCount")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    metadata_payload: dict[str, Any] = Field(default_factory=dict, alias="metadataPayload")


class ManagementReportMetricResponse(ORMModel):
    id: str
    import_id: str = Field(alias="importId")
    sheet_name: str = Field(alias="sheetName")
    row_index: int = Field(alias="rowIndex")
    dimension_type: str = Field(alias="dimensionType")
    dimension_code: str | None = Field(default=None, alias="dimensionCode")
    dimension_name: str = Field(alias="dimensionName")
    metric_name: str = Field(alias="metricName")
    metric_year: int | None = Field(default=None, alias="metricYear")
    metric_value: Decimal = Field(alias="metricValue")
    metric_unit: str = Field(alias="metricUnit")


class ManagementReportRowResponse(ORMModel):
    id: str
    import_id: str = Field(alias="importId")
    sheet_name: str = Field(alias="sheetName")
    row_index: int = Field(alias="rowIndex")
    is_header: bool = Field(alias="isHeader")
    parsed_metric_count: int = Field(alias="parsedMetricCount")
    raw_values: list[Any] = Field(alias="rawValues")
    notes: str | None = None


class OrganizationUnitResponse(ORMModel):
    id: str
    unit_type: str = Field(alias="unitType")
    code: str
    name: str
    display_name: str = Field(alias="displayName")
    source_import_id: str | None = Field(default=None, alias="sourceImportId")


class ManagementReportKeyMetric(ORMModel):
    label: str
    value: Decimal
    unit: str
    year: int | None = None
    dimension: str | None = None
    sheet_name: str = Field(alias="sheetName")


class ManagementReportSummaryResponse(ORMModel):
    latest_import: ManagementReportImportResponse | None = Field(alias="latestImport")
    organization_units: list[OrganizationUnitResponse] = Field(alias="organizationUnits")
    key_metrics: list[ManagementReportKeyMetric] = Field(alias="keyMetrics")
    metric_counts_by_sheet: dict[str, int] = Field(alias="metricCountsBySheet")
