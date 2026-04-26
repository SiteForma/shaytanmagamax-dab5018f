from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.db.models import InboundDelivery, Sku
from apps.api.app.modules.inbound.schemas import InboundTimelineResponse


def get_inbound_timeline(db: Session) -> list[InboundTimelineResponse]:
    skus = {sku.id: sku for sku in db.scalars(select(Sku)).all()}
    inbound_rows = db.scalars(select(InboundDelivery).order_by(InboundDelivery.eta_date)).all()
    return [
        InboundTimelineResponse(
            id=row.id,
            sku_id=row.sku_id,
            article=skus[row.sku_id].article,
            sku_name=skus[row.sku_id].name,
            qty=row.quantity,
            eta=row.eta_date.isoformat(),
            status=row.status,
            affected_clients=row.affected_client_ids,
            reserve_impact=row.reserve_impact_qty,
        )
        for row in inbound_rows
    ]
