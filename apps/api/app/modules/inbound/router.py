from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.app.api.dependencies import (
    get_current_user,
    get_settings_dependency,
    require_capability,
)
from apps.api.app.core.config import Settings
from apps.api.app.db.models import User
from apps.api.app.db.session import get_db
from apps.api.app.modules.inbound.schemas import InboundSyncResponse, InboundTimelineResponse
from apps.api.app.modules.inbound.service import get_inbound_timeline, sync_inbound_google_sheet

router = APIRouter(prefix="/inbound", tags=["inbound"])


@router.get("/timeline", response_model=list[InboundTimelineResponse])
def get_inbound_timeline_route(db: Session = Depends(get_db)) -> list[InboundTimelineResponse]:
    return get_inbound_timeline(db)


@router.post(
    "/sync",
    response_model=InboundSyncResponse,
    dependencies=[Depends(require_capability("inbound", "sync"))],
)
def sync_inbound_google_sheet_route(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    current_user: User | None = Depends(get_current_user),
) -> InboundSyncResponse:
    return sync_inbound_google_sheet(
        db,
        settings,
        actor_user_id=current_user.id if current_user else None,
    )
