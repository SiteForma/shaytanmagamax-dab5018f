from __future__ import annotations

from collections import defaultdict

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from apps.api.app.db.models import Client, InboundDelivery, SalesFact, Sku, StockSnapshot
from apps.api.app.modules.catalog.schemas import (
    InboundDeliveryView,
    MonthlySalesPoint,
    SkuClientSplitView,
    SkuDetailResponse,
    SkuListItem,
    SkuReserveSummaryResponse,
    StockSnapshotView,
)
from apps.api.app.modules.reserve.read_models import aggregate_sku_reserve_summary
from apps.api.app.modules.reserve.service import get_portfolio_rows


def _serialize_sku(sku: Sku) -> SkuListItem:
    return SkuListItem(
        id=sku.id,
        article=sku.article,
        name=sku.name,
        category=sku.category.name if sku.category else None,
        brand=sku.brand,
        unit=sku.unit,
        active=sku.active,
    )


def list_skus(db: Session, query: str | None = None) -> list[SkuListItem]:
    stmt = select(Sku).options(selectinload(Sku.category)).order_by(Sku.article)
    if query:
        pattern = f"%{query.lower()}%"
        stmt = stmt.where((Sku.article.ilike(pattern)) | (Sku.name.ilike(pattern)))
    return [_serialize_sku(sku) for sku in db.scalars(stmt).all()]


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
    stock = db.scalars(
        select(StockSnapshot)
        .where(StockSnapshot.sku_id == sku_id)
        .order_by(desc(StockSnapshot.snapshot_at))
    ).first()
    if stock is None:
        return None
    return StockSnapshotView(
        sku_id=stock.sku_id,
        free_stock=stock.free_stock_qty,
        reserved_like=stock.reserved_like_qty,
        warehouse=stock.warehouse_code,
        updated_at=stock.snapshot_at.isoformat(),
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

    return SkuDetailResponse(
        sku=_serialize_sku(sku),
        sales=get_sku_sales_history(db, sku_id),
        stock=_latest_stock_view(db, sku_id),
        inbound=get_sku_inbound_timeline(db, sku_id),
        client_split=get_sku_client_split(db, sku_id),
        reserve_summary=get_sku_reserve_summary(db, sku_id),
    )
