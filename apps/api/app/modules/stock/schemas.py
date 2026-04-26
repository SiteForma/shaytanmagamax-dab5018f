from __future__ import annotations

from apps.api.app.common.schemas import ORMModel, PaginatedResponse


class StockCoverageRowResponse(ORMModel):
    sku_id: str
    article: str
    product_name: str
    category_name: str | None = None
    warehouse: str | None = None
    free: float
    reserved_like: float
    demand_per_month: float
    coverage_months: float | None = None
    shortage_qty_total: float
    affected_clients_count: int
    worst_status: str
    inbound_qty_within_horizon: float


class PotentialStockoutRowResponse(ORMModel):
    client_id: str
    client_name: str
    sku_id: str
    article: str
    product_name: str
    category_name: str | None = None
    shortage_qty: float
    coverage_months: float | None = None
    status: str
    target_reserve_qty: float
    available_qty: float


class StockCoverageListResponse(PaginatedResponse[StockCoverageRowResponse]):
    pass
