from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session, selectinload

from apps.api.app.db.models import Client, DiyPolicy, InboundDelivery, SalesFact, Sku, StockSnapshot
from apps.api.app.modules.reserve.domain import ReserveCalculationInput


@dataclass(slots=True)
class ReserveDataset:
    clients: list[Client]
    skus: list[Sku]
    policies_by_client: dict[str, DiyPolicy | None]
    sales_facts: list[SalesFact]
    stock_by_sku: dict[str, StockSnapshot]
    inbound_by_sku: dict[str, list[InboundDelivery]]
    as_of_date: date


def _month_window_start(as_of_date: date, months: int = 6) -> date:
    current_month_start = as_of_date.replace(day=1)
    month_index = current_month_start.year * 12 + current_month_start.month - 1 - (months - 1)
    year = month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _filtered_clients(db: Session, request: ReserveCalculationInput) -> list[Client]:
    stmt = (
        select(Client)
        .where(Client.is_active.is_(True))
        .options(selectinload(Client.policies))
        .order_by(Client.name)
    )
    clients = db.scalars(stmt).unique().all()
    diy_clients = [
        client for client in clients if client.network_type == "DIY" or client.client_group == "DIY"
    ]
    if request.client_ids:
        allowed_ids = set(request.client_ids)
        diy_clients = [client for client in diy_clients if client.id in allowed_ids]
    return diy_clients


def _candidate_sku_ids(
    db: Session, request: ReserveCalculationInput, client_ids: list[str], as_of_date: date
) -> set[str]:
    if request.sku_ids:
        return set(request.sku_ids)

    sku_codes = set(request.sku_codes or [])
    if sku_codes:
        skus = db.scalars(select(Sku).where(Sku.article.in_(sku_codes))).all()
        return {sku.id for sku in skus}

    category_filters = set(request.effective_category_ids())
    if category_filters:
        skus = db.scalars(select(Sku).options(selectinload(Sku.category))).all()
        matched_ids: set[str] = set()
        for sku in skus:
            if sku.category is None:
                continue
            if sku.category.id in category_filters or sku.category.name in category_filters:
                matched_ids.add(sku.id)
        return matched_ids

    monitored_ids: set[str] = set()
    start = _month_window_start(as_of_date, months=6)
    sales_stmt = select(SalesFact).where(SalesFact.period_month >= start)
    if client_ids:
        sales_stmt = sales_stmt.where(SalesFact.client_id.in_(client_ids))
    for fact in db.scalars(sales_stmt).all():
        monitored_ids.add(fact.sku_id)
    for stock in db.scalars(select(StockSnapshot)).all():
        monitored_ids.add(stock.sku_id)
    for inbound in db.scalars(select(InboundDelivery)).all():
        monitored_ids.add(inbound.sku_id)
    return monitored_ids


def _filtered_skus(
    db: Session, request: ReserveCalculationInput, client_ids: list[str], as_of_date: date
) -> list[Sku]:
    allowed_ids = _candidate_sku_ids(db, request, client_ids, as_of_date)
    skus = db.scalars(
        select(Sku)
        .options(selectinload(Sku.category))
        .where(Sku.active.is_(True))
        .order_by(Sku.article)
    ).all()
    if allowed_ids:
        skus = [sku for sku in skus if sku.id in allowed_ids]
    return skus


def _latest_stock_by_sku(db: Session, sku_ids: list[str]) -> dict[str, StockSnapshot]:
    latest: dict[str, StockSnapshot] = {}
    rows = db.scalars(
        select(StockSnapshot)
        .where(StockSnapshot.sku_id.in_(sku_ids))
        .order_by(StockSnapshot.sku_id, desc(StockSnapshot.snapshot_at))
    ).all()
    for row in rows:
        latest.setdefault(row.sku_id, row)
    return latest


def _inbound_by_sku(
    db: Session,
    *,
    sku_ids: list[str],
    as_of_date: date,
    horizon_days: int,
    inbound_statuses_to_count: list[str],
) -> dict[str, list[InboundDelivery]]:
    if not sku_ids:
        return {}
    statuses = set(inbound_statuses_to_count)
    horizon_limit = as_of_date + timedelta(days=horizon_days)
    rows = db.scalars(
        select(InboundDelivery).where(
            InboundDelivery.sku_id.in_(sku_ids),
            InboundDelivery.eta_date <= horizon_limit,
        )
    ).all()
    grouped: dict[str, list[InboundDelivery]] = {sku_id: [] for sku_id in sku_ids}
    for row in rows:
        if row.status not in statuses:
            continue
        grouped.setdefault(row.sku_id, []).append(row)
    return grouped


def _sales_facts(
    db: Session,
    *,
    sku_ids: list[str],
    category_ids: list[str],
    as_of_date: date,
) -> list[SalesFact]:
    if not sku_ids and not category_ids:
        return []
    start = _month_window_start(as_of_date, months=6)
    filters = []
    if sku_ids:
        filters.append(SalesFact.sku_id.in_(sku_ids))
    if category_ids:
        filters.append(SalesFact.category_id.in_(category_ids))
    return db.scalars(
        select(SalesFact).where(
            or_(*filters),
            SalesFact.period_month >= start,
        )
    ).all()


def load_reserve_dataset(db: Session, request: ReserveCalculationInput) -> ReserveDataset:
    as_of_date = request.normalized_as_of_date()
    clients = _filtered_clients(db, request)
    client_ids = [client.id for client in clients]
    skus = _filtered_skus(db, request, client_ids, as_of_date)
    sku_ids = [sku.id for sku in skus]
    category_ids = [sku.category_id for sku in skus if sku.category_id]
    policies_by_client = {
        client.id: next((policy for policy in client.policies if policy.active), None)
        for client in clients
    }
    return ReserveDataset(
        clients=clients,
        skus=skus,
        policies_by_client=policies_by_client,
        sales_facts=_sales_facts(
            db,
            sku_ids=sku_ids,
            category_ids=category_ids,
            as_of_date=as_of_date,
        ),
        stock_by_sku=_latest_stock_by_sku(db, sku_ids),
        inbound_by_sku=_inbound_by_sku(
            db,
            sku_ids=sku_ids,
            as_of_date=as_of_date,
            horizon_days=request.horizon_days,
            inbound_statuses_to_count=request.inbound_statuses_to_count,
        ),
        as_of_date=as_of_date,
    )
