from __future__ import annotations

from apps.api.app.common.schemas import ORMModel
from apps.api.app.modules.reserve.schemas import CoverageBucketResponse, FreshnessPanelResponse


class DashboardSummaryResponse(ORMModel):
    total_skus_tracked: int
    active_diy_clients: int
    positions_at_risk: int
    total_shortage_qty: float
    inbound_qty_within_horizon: float
    avg_coverage_months: float | None = None
    open_quality_issues: int
    last_update: str
    freshness_hours: int
    latest_run_id: str | None = None


class TopRiskSkuResponse(ORMModel):
    sku_id: str
    sku_code: str
    product_name: str
    affected_clients_count: int
    shortage_qty_total: float
    min_coverage_months: float | None = None
    worst_status: str
    category_name: str | None = None


class ExposedClientResponse(ORMModel):
    client_id: str
    client_name: str
    positions_tracked: int
    critical_positions: int
    warning_positions: int
    shortage_qty_total: float
    avg_coverage_months: float | None = None
    inbound_relief_qty: float


class InboundShortagePoint(ORMModel):
    month: str
    inbound_qty: float
    shortage_qty: float


class DashboardOverviewResponse(ORMModel):
    summary: DashboardSummaryResponse
    top_risk_skus: list[TopRiskSkuResponse]
    exposed_clients: list[ExposedClientResponse]
    coverage_distribution: list[CoverageBucketResponse]
    inbound_vs_shortage: list[InboundShortagePoint]
    freshness: FreshnessPanelResponse
