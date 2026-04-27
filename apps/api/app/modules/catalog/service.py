from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from apps.api.app.db.models import (
    Client,
    InboundDelivery,
    SalesFact,
    Sku,
    SkuCost,
    StockSnapshot,
)
from apps.api.app.modules.catalog.schemas import (
    InboundDeliveryView,
    MonthlySalesPoint,
    SkuClientSplitView,
    SkuCostResponse,
    SkuDetailResponse,
    SkuListItem,
    SkuReserveSummaryResponse,
    StockSnapshotView,
)
from apps.api.app.modules.reserve.read_models import aggregate_sku_reserve_summary
from apps.api.app.modules.reserve.service import get_portfolio_rows


def _cost_view(cost: SkuCost | None) -> SkuCostResponse | None:
    if cost is None:
        return None
    return SkuCostResponse(
        article=cost.article,
        product_name=cost.product_name,
        cost_rub=float(cost.cost_rub),
        upload_file_id=cost.upload_file_id,
        source_row_number=cost.source_row_number,
        updated_at=cost.updated_at.isoformat(),
    )


def _serialize_sku(sku: Sku, cost: SkuCost | None = None) -> SkuListItem:
    return SkuListItem(
        id=sku.id,
        article=sku.article,
        name=cost.product_name if cost else sku.name,
        category=sku.category.name if sku.category else None,
        category_path=sku.category.path if sku.category else None,
        brand=sku.brand,
        unit=sku.unit,
        active=sku.active,
        cost_rub=float(cost.cost_rub) if cost else None,
        cost_product_name=cost.product_name if cost else None,
    )


def list_skus(db: Session, query: str | None = None) -> list[SkuListItem]:
    stmt = (
        select(Sku, SkuCost)
        .join(SkuCost, SkuCost.article == Sku.article)
        .options(selectinload(Sku.category))
        .order_by(SkuCost.article)
    )
    if query:
        pattern = f"%{query.lower()}%"
        stmt = stmt.where(
            (Sku.article.ilike(pattern))
            | (Sku.name.ilike(pattern))
            | (SkuCost.product_name.ilike(pattern))
        )
    return [_serialize_sku(sku, cost) for sku, cost in db.execute(stmt).all()]


def list_sku_costs(
    db: Session, query: str | None = None, limit: int = 5000
) -> list[SkuCostResponse]:
    stmt = select(SkuCost).order_by(SkuCost.article).limit(limit)
    if query:
        pattern = f"%{query.lower()}%"
        stmt = stmt.where((SkuCost.article.ilike(pattern)) | (SkuCost.product_name.ilike(pattern)))
    items: list[SkuCostResponse] = []
    for cost in db.scalars(stmt).all():
        view = _cost_view(cost)
        if view is not None:
            items.append(view)
    return items


def get_sku_sales_history(db: Session, sku_id: str) -> list[MonthlySalesPoint]:
    monthly_totals: dict[str, float] = defaultdict(float)
    sales_facts = db.scalars(
        select(SalesFact).where(SalesFact.sku_id == sku_id).order_by(SalesFact.period_month)
    ).all()
    for fact in sales_facts:
        monthly_totals[fact.period_month.strftime("%Y-%m")] += fact.quantity
    return [
        MonthlySalesPoint(month=month, qty=round(qty, 1))
        for month, qty in sorted(monthly_totals.items())
    ]


def get_sku_inbound_timeline(db: Session, sku_id: str) -> list[InboundDeliveryView]:
    inbound_rows = db.scalars(
        select(InboundDelivery)
        .where(InboundDelivery.sku_id == sku_id)
        .order_by(InboundDelivery.eta_date)
    ).all()
    return [
        InboundDeliveryView(
            id=row.id,
            sku_id=row.sku_id,
            qty=row.quantity,
            eta=row.eta_date.isoformat(),
            status=row.status,
            affected_clients=row.affected_client_ids,
            reserve_impact=row.reserve_impact_qty,
        )
        for row in inbound_rows
    ]


def _latest_stock_view(db: Session, sku_id: str) -> StockSnapshotView | None:
    latest_at = db.scalar(
        select(func.max(StockSnapshot.snapshot_at)).where(StockSnapshot.sku_id == sku_id)
    )
    if latest_at is None:
        return None
    stock = db.execute(
        select(
            func.sum(StockSnapshot.free_stock_qty).label("free_stock_qty"),
            func.sum(StockSnapshot.reserved_like_qty).label("reserved_like_qty"),
        ).where(
            StockSnapshot.sku_id == sku_id,
            StockSnapshot.snapshot_at == latest_at,
        )
    ).first()
    if stock is None:
        return None
    return StockSnapshotView(
        sku_id=sku_id,
        free_stock=float(stock.free_stock_qty or 0.0),
        reserved_like=float(stock.reserved_like_qty or 0.0),
        warehouse="Сводный",
        updated_at=latest_at.isoformat(),
    )


def get_sku_client_split(db: Session, sku_id: str) -> list[SkuClientSplitView]:
    _, reserve_rows = get_portfolio_rows(db)
    selected_rows = [row for row in reserve_rows if row.sku_id == sku_id]
    if not selected_rows:
        return []

    sales_totals = {row.client_id: row.sales_qty_6m for row in selected_rows}
    total_sales = sum(sales_totals.values()) or 1.0
    clients = {
        client.id: client
        for client in db.scalars(select(Client).where(Client.id.in_(sales_totals))).all()
    }
    ordered = sorted(
        selected_rows,
        key=lambda row: (row.shortage_qty, row.target_reserve_qty),
        reverse=True,
    )
    return [
        SkuClientSplitView(
            client_id=row.client_id,
            client_name=(
                clients.get(row.client_id).name if clients.get(row.client_id) else row.client_name
            ),
            share=round((sales_totals.get(row.client_id, 0.0) / total_sales) * 100, 1),
            reserve_position=row.target_reserve_qty,
            shortage_qty=row.shortage_qty,
            coverage_months=row.coverage_months,
            status=row.status,
        )
        for row in ordered
    ]


def get_sku_reserve_summary(db: Session, sku_id: str) -> SkuReserveSummaryResponse | None:
    run, rows = get_portfolio_rows(db)
    payload = aggregate_sku_reserve_summary(rows, sku_id)
    if payload is None:
        return None
    return SkuReserveSummaryResponse(
        sku_id=str(payload["sku_id"]),
        sku_code=str(payload["sku_code"]),
        product_name=str(payload["product_name"]),
        category_name=payload["category_name"],  # type: ignore[arg-type]
        affected_clients_count=int(payload["affected_clients_count"]),
        shortage_qty_total=float(payload["shortage_qty_total"]),
        avg_coverage_months=payload["avg_coverage_months"],  # type: ignore[arg-type]
        worst_status=str(payload["worst_status"]),
        latest_run_id=run.id if run else None,
    )


def get_sku_detail(db: Session, sku_id: str) -> SkuDetailResponse | None:
    sku = db.scalar(select(Sku).options(selectinload(Sku.category)).where(Sku.id == sku_id))
    if sku is None:
        return None
    cost = db.scalar(select(SkuCost).where(SkuCost.article == sku.article))

    return SkuDetailResponse(
        sku=_serialize_sku(sku, cost),
        sales=get_sku_sales_history(db, sku_id),
        stock=_latest_stock_view(db, sku_id),
        inbound=get_sku_inbound_timeline(db, sku_id),
        client_split=get_sku_client_split(db, sku_id),
        reserve_summary=get_sku_reserve_summary(db, sku_id),
        cost=_cost_view(cost),
    )
