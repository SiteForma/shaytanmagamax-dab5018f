from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.app.api.dependencies import require_capability
from apps.api.app.db.models import User
from apps.api.app.db.session import get_db
from apps.api.app.modules.audit.service import record_audit_event
from apps.api.app.modules.reserve.domain import ReserveCalculationInput
from apps.api.app.modules.reserve.schemas import (
    ReserveCalculationRequest,
    ReserveCalculationResponse,
    ReserveRowResponse,
    ReserveRunSummary,
    ReserveRunSummaryResponse,
)
from apps.api.app.modules.reserve.service import (
    calculate_and_persist,
    get_run,
    get_run_detail,
    get_run_rows,
    list_runs,
)

router = APIRouter(prefix="/reserve", tags=["reserve"])


def _to_input(payload: ReserveCalculationRequest) -> ReserveCalculationInput:
    return ReserveCalculationInput(**payload.model_dump())


@router.post("/calculate", response_model=ReserveCalculationResponse)
def calculate_reserve_route(
    payload: ReserveCalculationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_capability("reserve", "run")),
) -> ReserveCalculationResponse:
    response = calculate_and_persist(
        db,
        _to_input(payload),
        created_by_id=current_user.id,
        reuse_existing=False,
    )
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="reserve.run_created",
        target_type="reserve_run",
        target_id=response.run.id,
        context={
            "client_ids": payload.client_ids,
            "sku_codes": payload.sku_codes,
            "category_ids": payload.category_ids,
            "strategy": payload.demand_strategy,
        },
    )
    db.commit()
    return response


@router.get("/runs", response_model=list[ReserveRunSummary])
def list_reserve_runs_route(db: Session = Depends(get_db)) -> list[ReserveRunSummary]:
    return list_runs(db)


@router.get("/runs/{run_id}", response_model=ReserveRunSummary)
def get_reserve_run_route(run_id: str, db: Session = Depends(get_db)) -> ReserveRunSummary:
    run = get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Расчёт резерва не найден")
    return run


@router.get("/runs/{run_id}/rows", response_model=list[ReserveRowResponse])
def get_reserve_run_rows_route(
    run_id: str, db: Session = Depends(get_db)
) -> list[ReserveRowResponse]:
    if get_run(db, run_id) is None:
        raise HTTPException(status_code=404, detail="Расчёт резерва не найден")
    return get_run_rows(db, run_id)


@router.get("/runs/{run_id}/summary", response_model=ReserveRunSummaryResponse)
def get_reserve_run_summary_route(
    run_id: str, db: Session = Depends(get_db)
) -> ReserveRunSummaryResponse:
    summary = get_run_detail(db, run_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Расчёт резерва не найден")
    return summary
