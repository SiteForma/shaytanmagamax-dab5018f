from __future__ import annotations

from sqlalchemy import and_, asc, case, desc, func, select
from sqlalchemy.orm import Session

from apps.api.app.common.pagination import page_offset
from apps.api.app.db.models import Category, ReserveRow, Sku, StockSnapshot
from apps.api.app.modules.reserve.read_models import aggregate_potential_stockout
from apps.api.app.modules.reserve.service import get_portfolio_rows, get_portfolio_run
from apps.api.app.modules.stock.schemas import (
    PotentialStockoutRowResponse,
    StockCoverageRowResponse,
)

STATUS_RANK = {
    "critical": 5,
    "warning": 4,
    "no_history": 3,
    "inactive": 2,
    "healthy": 1,
    "overstocked": 0,
}
RANK_TO_STATUS = {rank: status for status, rank in STATUS_RANK.items()}


def _latest_stock_subquery():
    latest_snapshot = (
        select(
            StockSnapshot.sku_id.label("sku_id"),
            func.max(StockSnapshot.snapshot_at).label("snapshot_at"),
        )
        .group_by(StockSnapshot.sku_id)
        .subquery()
    )
    return (
        select(
            StockSnapshot.sku_id.label("sku_id"),
            StockSnapshot.warehouse_code.label("warehouse"),
            StockSnapshot.free_stock_qty.label("free_stock_qty"),
            StockSnapshot.reserved_like_qty.label("reserved_like_qty"),
        )
        .join(
            latest_snapshot,
            and_(
                StockSnapshot.sku_id == latest_snapshot.c.sku_id,
                StockSnapshot.snapshot_at == latest_snapshot.c.snapshot_at,
            ),
        )
        .subquery()
    )


def _stock_coverage_stmt(
    db: Session,
    *,
    category: str | None = None,
    risk: str = "all",
    search: str | None = None,
    sort_by: str = "shortage_qty_total",
    sort_dir: str = "desc",
):
    run = get_portfolio_run(db)
    if run is None:
        return None

    status_rank_case = case(
        *[(ReserveRow.status == name, rank) for name, rank in STATUS_RANK.items()],
        else_=0,
    )
    reserve_rollup = (
        select(
            ReserveRow.sku_id.label("sku_id"),
            func.sum(ReserveRow.demand_per_month).label("demand_per_month"),
            func.sum(ReserveRow.shortage_qty).label("shortage_qty_total"),
            func.count(ReserveRow.id).label("affected_clients_count"),
            func.max(ReserveRow.inbound_in_horizon_qty).label("inbound_qty_within_horizon"),
            func.max(status_rank_case).label("worst_status_rank"),
        )
        .where(ReserveRow.run_id == run.id)
        .group_by(ReserveRow.sku_id)
        .subquery()
    )
    latest_stock = _latest_stock_subquery()
    free_qty = func.coalesce(latest_stock.c.free_stock_qty, 0.0)
    reserved_like = func.coalesce(latest_stock.c.reserved_like_qty, 0.0)
    coverage_months = case(
        (reserve_rollup.c.demand_per_month > 0, free_qty / reserve_rollup.c.demand_per_month),
        else_=None,
    )

    stmt = (
        select(
            reserve_rollup.c.sku_id.label("sku_id"),
            Sku.article.label("article"),
            Sku.name.label("product_name"),
            Category.name.label("category_name"),
            latest_stock.c.warehouse.label("warehouse"),
            free_qty.label("free"),
            reserved_like.label("reserved_like"),
            reserve_rollup.c.demand_per_month.label("demand_per_month"),
            coverage_months.label("coverage_months"),
            reserve_rollup.c.shortage_qty_total.label("shortage_qty_total"),
            reserve_rollup.c.affected_clients_count.label("affected_clients_count"),
            reserve_rollup.c.worst_status_rank.label("worst_status_rank"),
            reserve_rollup.c.inbound_qty_within_horizon.label("inbound_qty_within_horizon"),
        )
        .join(Sku, Sku.id == reserve_rollup.c.sku_id)
        .outerjoin(Category, Category.id == Sku.category_id)
        .outerjoin(latest_stock, latest_stock.c.sku_id == reserve_rollup.c.sku_id)
    )
    if category:
        stmt = stmt.where(Category.name == category)
    if search:
        pattern = f"%{search.lower()}%"
        stmt = stmt.where(
            func.lower(Sku.article).like(pattern) | func.lower(Sku.name).like(pattern)
        )
    if risk == "low_stock":
        stmt = stmt.where(reserve_rollup.c.worst_status_rank >= STATUS_RANK["warning"])
    elif risk == "overstock":
        stmt = stmt.where(coverage_months > 6)

    sorters = {
        "article": Sku.article,
        "product_name": Sku.name,
        "category_name": Category.name,
        "free": free_qty,
        "demand_per_month": reserve_rollup.c.demand_per_month,
        "coverage_months": coverage_months,
        "shortage_qty_total": reserve_rollup.c.shortage_qty_total,
        "affected_clients_count": reserve_rollup.c.affected_clients_count,
        "worst_status": reserve_rollup.c.worst_status_rank,
    }
    column = sorters.get(sort_by, reserve_rollup.c.shortage_qty_total)
    order_fn = desc if sort_dir == "desc" else asc
    return stmt.order_by(order_fn(column), asc(Sku.article))


def _serialize_stock_coverage_row(row) -> StockCoverageRowResponse:  # type: ignore[no-untyped-def]
    coverage_months = float(row.coverage_months) if row.coverage_months is not None else None
    return StockCoverageRowResponse(
        sku_id=str(row.sku_id),
        article=str(row.article),
        product_name=str(row.product_name),
        category_name=row.category_name,
        warehouse=row.warehouse,
        free=round(float(row.free or 0.0), 1),
        reserved_like=round(float(row.reserved_like or 0.0), 1),
        demand_per_month=round(float(row.demand_per_month or 0.0), 1),
        coverage_months=round(coverage_months, 1) if coverage_months is not None else None,
        shortage_qty_total=round(float(row.shortage_qty_total or 0.0), 1),
        affected_clients_count=int(row.affected_clients_count or 0),
        worst_status=RANK_TO_STATUS.get(int(row.worst_status_rank or 0), "healthy"),
        inbound_qty_within_horizon=round(float(row.inbound_qty_within_horizon or 0.0), 1),
    )


def get_stock_coverage(
    db: Session,
    category: str | None = None,
    risk: str = "all",
    search: str | None = None,
    sort_by: str = "shortage_qty_total",
    sort_dir: str = "desc",
) -> list[StockCoverageRowResponse]:
    stmt = _stock_coverage_stmt(
        db,
        category=category,
        risk=risk,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    if stmt is None:
        return []
    rows = db.execute(stmt).all()
    return [_serialize_stock_coverage_row(row) for row in rows]


def get_stock_coverage_page(
    db: Session,
    *,
    category: str | None = None,
    risk: str = "all",
    search: str | None = None,
    sort_by: str = "shortage_qty_total",
    sort_dir: str = "desc",
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[StockCoverageRowResponse], int]:
    stmt = _stock_coverage_stmt(
        db,
        category=category,
        risk=risk,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    if stmt is None:
        return [], 0
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.execute(stmt.offset(page_offset(page, page_size)).limit(page_size)).all()
    return ([_serialize_stock_coverage_row(row) for row in rows], int(total))


def get_potential_stockout(db: Session) -> list[PotentialStockoutRowResponse]:
    _, rows = get_portfolio_rows(db)
    return [
        PotentialStockoutRowResponse(
            client_id=row.client_id,
            client_name=row.client_name,
            sku_id=row.sku_id,
            article=row.article,
            product_name=row.product_name,
            category_name=row.category,
            shortage_qty=row.shortage_qty,
            coverage_months=row.coverage_months,
            status=row.status,
            target_reserve_qty=row.target_reserve_qty,
            available_qty=row.available_qty,
        )
        for row in aggregate_potential_stockout(rows)[:25]
    ]
