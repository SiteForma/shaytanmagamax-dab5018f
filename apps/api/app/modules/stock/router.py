from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.app.common.pagination import paginated_response
from apps.api.app.common.schemas import PaginatedResponse
from apps.api.app.db.session import get_db
from apps.api.app.modules.stock.schemas import (
    PotentialStockoutRowResponse,
    StockCoverageListResponse,
    StockCoverageRowResponse,
)
from apps.api.app.modules.stock.service import (
    get_potential_stockout,
    get_stock_coverage_page,
)

router = APIRouter(prefix="/stock", tags=["stock"])


@router.get("/coverage", response_model=PaginatedResponse[StockCoverageRowResponse])
def get_stock_coverage_route(
    category: str | None = Query(default=None),
    risk: str = Query(default="all"),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    sort_by: str = Query(default="shortage_qty_total"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
) -> StockCoverageListResponse:
    items, total = get_stock_coverage_page(
        db,
        category=category,
        risk=risk,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )
    return StockCoverageListResponse.model_validate(
        paginated_response(items, total=total, page=page, page_size=page_size)
    )


@router.get("/potential-stockout", response_model=list[PotentialStockoutRowResponse])
def get_potential_stockout_route(
    db: Session = Depends(get_db),
) -> list[PotentialStockoutRowResponse]:
    return get_potential_stockout(db)
