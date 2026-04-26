from __future__ import annotations

from apps.api.app.common.schemas import ORMModel


class ClientSummaryResponse(ORMModel):
    id: str
    name: str
    region: str
    reserve_months: int
    positions_tracked: int
    shortage_qty: float
    critical_positions: int
    warning_positions: int
    coverage_months: float | None = None
    expected_inbound_relief: float
    latest_run_id: str | None = None


class ClientDetailResponse(ClientSummaryResponse):
    code: str
    network_type: str
    policy_active: bool
    safety_factor: float
    priority_level: int
    allowed_fallback_depth: int
    notes: str | None = None


class ClientTopSkuResponse(ORMModel):
    sku_id: str
    sku_code: str
    product_name: str
    category_name: str | None = None
    status: str
    shortage_qty: float
    coverage_months: float | None = None
    target_reserve_qty: float
    available_qty: float


class CategoryExposureResponse(ORMModel):
    category_name: str
    positions: int
    shortage_qty_total: float
