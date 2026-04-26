from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from apps.api.app.api.dependencies import get_settings_dependency
from apps.api.app.core.config import Settings
from apps.api.app.db.session import get_db
from apps.api.app.modules.health.service import collect_readiness

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
) -> dict[str, object]:
    payload = collect_readiness(db, settings)
    status_code = 200 if payload["status"] == "ready" else 503
    return JSONResponse(status_code=status_code, content=payload)
