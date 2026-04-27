from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.api.app.api.dependencies import get_settings_dependency, require_capability
from apps.api.app.core.config import Settings
from apps.api.app.db.models import User
from apps.api.app.db.session import get_db
from apps.api.app.modules.catalog.cost_import import import_sku_costs_from_upload
from apps.api.app.modules.catalog.cost_schemas import SkuCostImportResponse
from apps.api.app.modules.catalog.schemas import (
    InboundDeliveryView,
    MonthlySalesPoint,
    SkuClientSplitView,
    SkuCostResponse,
    SkuDetailResponse,
    SkuListItem,
    SkuReserveSummaryResponse,
)
from apps.api.app.modules.catalog.service import (
    get_sku_client_split,
    get_sku_detail,
    get_sku_inbound_timeline,
    get_sku_reserve_summary,
    get_sku_sales_history,
    list_sku_costs,
    list_skus,
)
from apps.api.app.modules.uploads.storage import get_object_storage

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/skus", response_model=list[SkuListItem])
def list_skus_route(
    query: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[SkuListItem]:
    return list_skus(db, query)


@router.get("/sku-costs", response_model=list[SkuCostResponse])
def list_sku_costs_route(
    query: str | None = Query(default=None),
    limit: int = Query(default=5000, ge=1, le=10000),
    db: Session = Depends(get_db),
) -> list[SkuCostResponse]:
    return list_sku_costs(db, query=query, limit=limit)


@router.get("/skus/{sku_id}", response_model=SkuDetailResponse)
def get_sku_detail_route(sku_id: str, db: Session = Depends(get_db)) -> SkuDetailResponse:
    detail = get_sku_detail(db, sku_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="SKU not found")
    return detail


@router.get("/skus/{sku_id}/reserve-summary", response_model=SkuReserveSummaryResponse)
def get_sku_reserve_summary_route(
    sku_id: str,
    db: Session = Depends(get_db),
) -> SkuReserveSummaryResponse:
    summary = get_sku_reserve_summary(db, sku_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="SKU reserve summary not found")
    return summary


@router.get("/skus/{sku_id}/sales-history", response_model=list[MonthlySalesPoint])
def get_sku_sales_history_route(
    sku_id: str,
    db: Session = Depends(get_db),
) -> list[MonthlySalesPoint]:
    return get_sku_sales_history(db, sku_id)


@router.get("/skus/{sku_id}/inbound-timeline", response_model=list[InboundDeliveryView])
def get_sku_inbound_timeline_route(
    sku_id: str,
    db: Session = Depends(get_db),
) -> list[InboundDeliveryView]:
    return get_sku_inbound_timeline(db, sku_id)


@router.get("/skus/{sku_id}/client-split", response_model=list[SkuClientSplitView])
def get_sku_client_split_route(
    sku_id: str,
    db: Session = Depends(get_db),
) -> list[SkuClientSplitView]:
    return get_sku_client_split(db, sku_id)


@router.post("/sku-costs/import-upload/{file_id}", response_model=SkuCostImportResponse)
def import_sku_costs_from_upload_route(
    file_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    _current_user: User = Depends(require_capability("catalog", "write")),
) -> SkuCostImportResponse:
    storage = get_object_storage(settings)
    summary = import_sku_costs_from_upload(db, storage, file_id)
    return SkuCostImportResponse(
        upload_file_id=summary.upload_file_id,
        file_name=summary.file_name,
        total_rows=summary.total_rows,
        imported_rows=summary.imported_rows,
        skipped_rows=summary.skipped_rows,
        linked_sku_rows=summary.linked_sku_rows,
        history_rows=summary.history_rows,
    )
