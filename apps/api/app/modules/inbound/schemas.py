from __future__ import annotations

from pydantic import Field

from apps.api.app.common.schemas import ORMModel


class InboundTimelineResponse(ORMModel):
    id: str
    sku_id: str
    article: str
    sku_name: str
    container_ref: str | None = None
    qty: float
    free_stock_after_allocation: float = 0
    client_order_qty: float = 0
    eta: str
    status: str
    sheet_status: str | None = None
    affected_clients: list[str]
    client_allocations: dict[str, float] = Field(default_factory=dict)
    reserve_impact: float
    source_synced_at: str | None = None


class InboundSyncResponse(ORMModel):
    status: str
    source_url: str
    synced_at: str
    rows_seen: int
    rows_imported: int
    rows_skipped: int
    deliveries_replaced: int
    sku_created: int
    clients_created: int
    total_in_transit_qty: float
    total_free_stock_after_allocation_qty: float
    total_client_order_qty: float
    warnings: list[str] = Field(default_factory=list)
