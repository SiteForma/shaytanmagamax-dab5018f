from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.app.db.session import get_db
from apps.api.app.modules.inbound.schemas import InboundTimelineResponse
from apps.api.app.modules.inbound.service import get_inbound_timeline

router = APIRouter(prefix="/inbound", tags=["inbound"])


@router.get("/timeline", response_model=list[InboundTimelineResponse])
def get_inbound_timeline_route(db: Session = Depends(get_db)) -> list[InboundTimelineResponse]:
    return get_inbound_timeline(db)
