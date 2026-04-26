from __future__ import annotations

from apps.api.app.common.schemas import ORMModel


class SkuListItem(ORMModel):
    id: str
    article: str
    name: str
    category: str | None = None
    brand: str
    unit: str
    active: bool


class MonthlySalesPoint(ORMModel):
    month: str
    qty: float


class StockSnapshotView(ORMModel):
    sku_id: str
    free_stock: float
    reserved_like: float
    warehouse: str
    updated_at: str


class InboundDeliveryView(ORMModel):
    id: str
    sku_id: str
    qty: float
    eta: str
    status: str
    affected_clients: list[str]
    reserve_impact: float


class SkuClientSplitView(ORMModel):
    client_id: str
    client_name: str
    share: float
    reserve_position: float
    shortage_qty: float
    coverage_months: float | None = None
    status: str


class SkuReserveSummaryResponse(ORMModel):
    sku_id: str
    sku_code: str
    product_name: str
    category_name: str | None = None
    affected_clients_count: int
    shortage_qty_total: float
    avg_coverage_months: float | None = None
    worst_status: str
    latest_run_id: str | None = None


class SkuDetailResponse(ORMModel):
    sku: SkuListItem
    sales: list[MonthlySalesPoint]
    stock: StockSnapshotView | None
    inbound: list[InboundDeliveryView]
    client_split: list[SkuClientSplitView]
    reserve_summary: SkuReserveSummaryResponse | None = None
