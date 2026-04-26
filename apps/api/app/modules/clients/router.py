from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.app.db.session import get_db
from apps.api.app.modules.clients.schemas import (
    CategoryExposureResponse,
    ClientDetailResponse,
    ClientSummaryResponse,
    ClientTopSkuResponse,
)
from apps.api.app.modules.clients.service import (
    get_client,
    get_client_category_exposure,
    get_client_reserve_rows,
    get_client_top_skus,
    list_clients,
)
from apps.api.app.modules.reserve.schemas import ReserveRowResponse

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=list[ClientSummaryResponse])
@router.get("/diy", response_model=list[ClientSummaryResponse])
def list_clients_route(db: Session = Depends(get_db)) -> list[ClientSummaryResponse]:
    return list_clients(db)


@router.get("/diy/{client_id}", response_model=ClientDetailResponse)
@router.get("/{client_id}", response_model=ClientDetailResponse)
def get_client_route(client_id: str, db: Session = Depends(get_db)) -> ClientDetailResponse:
    client = get_client(db, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.get("/diy/{client_id}/reserve-summary", response_model=ClientDetailResponse)
def get_client_reserve_summary_route(
    client_id: str,
    db: Session = Depends(get_db),
) -> ClientDetailResponse:
    client = get_client(db, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.get("/diy/{client_id}/reserve-rows", response_model=list[ReserveRowResponse])
@router.get("/{client_id}/reserve", response_model=list[ReserveRowResponse])
def get_client_reserve_rows_route(
    client_id: str,
    db: Session = Depends(get_db),
) -> list[ReserveRowResponse]:
    return get_client_reserve_rows(db, client_id)


@router.get("/diy/{client_id}/top-skus", response_model=list[ClientTopSkuResponse])
def get_client_top_skus_route(
    client_id: str,
    db: Session = Depends(get_db),
) -> list[ClientTopSkuResponse]:
    return get_client_top_skus(db, client_id)


@router.get("/diy/{client_id}/category-exposure", response_model=list[CategoryExposureResponse])
def get_client_category_exposure_route(
    client_id: str,
    db: Session = Depends(get_db),
) -> list[CategoryExposureResponse]:
    return get_client_category_exposure(db, client_id)
