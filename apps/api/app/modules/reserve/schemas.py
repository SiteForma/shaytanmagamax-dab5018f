from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field

from apps.api.app.common.schemas import ORMModel, PaginatedResponse


class ReserveCalculationRequest(ORMModel):
    client_ids: list[str] | None = Field(default=None, alias="clientIds")
    sku_ids: list[str] | None = Field(default=None, alias="skuIds")
    sku_codes: list[str] | None = Field(default=None, alias="skuCodes")
    category_ids: list[str] | None = Field(default=None, alias="categoryIds")
    reserve_months_override: int | None = Field(default=None, alias="reserveMonths")
    safety_factor_override: float | None = Field(default=None, alias="safetyFactor")
    demand_strategy: str = Field(default="weighted_recent_average", alias="demandStrategy")
    include_inbound: bool = Field(default=True, alias="includeInbound")
    inbound_statuses_to_count: list[str] = Field(
        default_factory=lambda: ["confirmed"], alias="inboundStatusesToCount"
    )
    as_of_date: date | None = Field(default=None, alias="asOfDate")
    grouping_mode: str = Field(default="client_sku", alias="groupingMode")
    persist_run: bool = Field(default=True, alias="persistRun")
    horizon_days: int = Field(default=60, alias="horizonDays")

    # Compatibility aliases for the existing UI.
    demand_basis: str | None = Field(default="weighted_recent_average", alias="demandBasis")
    categories: list[str] | None = None


class ReserveRowResponse(ORMModel):
    client_id: str
    client_name: str
    sku_id: str
    article: str
    product_name: str
    category: str | None = None
    policy_id: str | None = None
    client_priority_level: int
    sales_qty_1m: float
    sales_qty_3m: float
    sales_qty_6m: float
    avg_monthly_3m: float
    avg_monthly_6m: float
    history_months_available: int
    last_sale_date: str | None = None
    demand_stability: float
    trend_signal: str
    demand_per_month: float
    reserve_months: int
    safety_factor: float
    target_reserve_qty: float
    free_stock: float
    inbound_within_horizon: float
    total_free_stock_qty: float
    total_inbound_in_horizon_qty: float
    allocated_free_stock_qty: float
    allocated_inbound_qty: float
    available_qty: float
    shortage_qty: float
    coverage_months: float | None = None
    status: str
    status_reason: str
    demand_basis: str
    demand_basis_type: str
    fallback_level: str
    basis_window_used: str
    explanation_payload: dict[str, object]


class ReserveRunSummary(ORMModel):
    id: str
    scope_type: str
    grouping_mode: str
    reserve_months: int
    safety_factor: float
    demand_strategy: str
    include_inbound: bool
    inbound_statuses: list[str]
    horizon_days: int
    row_count: int
    status: str
    created_at: str
    summary_payload: dict[str, object]


class ReserveRunListResponse(PaginatedResponse[ReserveRunSummary]):
    pass


class ReserveRunSummaryResponse(ORMModel):
    run: ReserveRunSummary
    totals: dict[str, float | int | None]
    status_counts: dict[str, int]


class ReserveCalculationResponse(ORMModel):
    run: ReserveRunSummary
    rows: list[ReserveRowResponse]


class CoverageBucketResponse(ORMModel):
    bucket: Literal["no_history", "under_1m", "between_1m_and_target", "healthy", "overstocked"]
    count: int


class FreshnessPanelResponse(ORMModel):
    last_upload_at: str | None = None
    last_reserve_run_at: str | None = None
    freshness_hours: int
    open_quality_issues: int
    latest_run_id: str | None = None
