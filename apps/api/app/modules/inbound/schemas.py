from __future__ import annotations

from apps.api.app.common.schemas import ORMModel


class InboundTimelineResponse(ORMModel):
    id: str
    sku_id: str
    article: str
    sku_name: str
    qty: float
    eta: str
    status: str
    affected_clients: list[str]
    reserve_impact: float
