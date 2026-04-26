from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.app.db.session import get_db
from apps.api.app.modules.sales.schemas import MonthlySalesResponse
from apps.api.app.modules.sales.service import get_monthly_sales

router = APIRouter(prefix="/sales", tags=["sales"])


@router.get("/monthly", response_model=list[MonthlySalesResponse])
def get_monthly_sales_route(
    sku_id: str | None = Query(default=None),
    client_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[MonthlySalesResponse]:
    return get_monthly_sales(db, sku_id=sku_id, client_id=client_id)
