from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from apps.api.app.db.models import Client, DiyPolicy
from apps.api.app.modules.clients.schemas import (
    CategoryExposureResponse,
    ClientDetailResponse,
    ClientSummaryResponse,
    ClientTopSkuResponse,
)
from apps.api.app.modules.reserve.read_models import (
    aggregate_client_category_exposure,
    aggregate_client_top_skus,
    summarize_reserve_rows,
)
from apps.api.app.modules.reserve.schemas import ReserveRowResponse
from apps.api.app.modules.reserve.service import get_portfolio_rows


def _diy_clients(db: Session) -> list[Client]:
    return db.scalars(
        select(Client)
        .where(
            Client.is_active.is_(True),
            (Client.network_type == "DIY") | (Client.client_group == "DIY"),
        )
        .options(selectinload(Client.policies))
        .order_by(Client.name)
    ).unique().all()


def _active_policy(client: Client) -> DiyPolicy | None:
    return next((policy for policy in client.policies if policy.active), None)


def _build_summary(
    client: Client,
    rows: list[ReserveRowResponse],
    *,
    latest_run_id: str | None,
) -> ClientSummaryResponse:
    policy = _active_policy(client)
    totals, status_counts = summarize_reserve_rows(rows)
    return ClientSummaryResponse(
        id=client.id,
        name=client.name,
        region=client.region,
        reserve_months=policy.reserve_months if policy else 3,
        positions_tracked=len(rows),
        shortage_qty=float(totals["total_shortage_qty"]),
        critical_positions=status_counts.get("critical", 0),
        warning_positions=status_counts.get("warning", 0),
        coverage_months=totals["avg_coverage_months"],  # type: ignore[arg-type]
        expected_inbound_relief=round(sum(row.inbound_within_horizon for row in rows), 1),
        latest_run_id=latest_run_id,
    )


def list_clients(db: Session) -> list[ClientSummaryResponse]:
    clients = _diy_clients(db)
    run, rows = get_portfolio_rows(db)
    rows_by_client: dict[str, list[ReserveRowResponse]] = defaultdict(list)
    for row in rows:
        rows_by_client[row.client_id].append(row)
    return [
        _build_summary(client, rows_by_client.get(client.id, []), latest_run_id=run.id if run else None)
        for client in clients
    ]


def get_client(db: Session, client_id: str) -> ClientDetailResponse | None:
    client = db.scalar(
        select(Client)
        .where(Client.id == client_id, Client.is_active.is_(True))
        .options(selectinload(Client.policies))
    )
    if client is None:
        return None
    run, rows = get_portfolio_rows(db)
    selected_rows = [row for row in rows if row.client_id == client_id]
    summary = _build_summary(client, selected_rows, latest_run_id=run.id if run else None)
    policy = _active_policy(client)
    return ClientDetailResponse(
        **summary.model_dump(),
        code=client.code,
        network_type=client.network_type,
        policy_active=policy.active if policy else False,
        safety_factor=policy.safety_factor if policy else 1.1,
        priority_level=policy.priority_level if policy else 999,
        allowed_fallback_depth=policy.allowed_fallback_depth if policy else 4,
        notes=policy.notes if policy else None,
    )


def get_client_reserve_rows(db: Session, client_id: str) -> list[ReserveRowResponse]:
    _, rows = get_portfolio_rows(db)
    return [row for row in rows if row.client_id == client_id]


def get_client_top_skus(db: Session, client_id: str) -> list[ClientTopSkuResponse]:
    _, rows = get_portfolio_rows(db)
    return [
        ClientTopSkuResponse(
            sku_id=str(item["sku_id"]),
            sku_code=str(item["sku_code"]),
            product_name=str(item["product_name"]),
            category_name=item["category_name"],  # type: ignore[arg-type]
            status=str(item["status"]),
            shortage_qty=float(item["shortage_qty"]),
            coverage_months=item["coverage_months"],  # type: ignore[arg-type]
            target_reserve_qty=float(item["target_reserve_qty"]),
            available_qty=float(item["available_qty"]),
        )
        for item in aggregate_client_top_skus(rows, client_id)
    ]


def get_client_category_exposure(db: Session, client_id: str) -> list[CategoryExposureResponse]:
    _, rows = get_portfolio_rows(db)
    return [
        CategoryExposureResponse(
            category_name=str(item["category_name"]),
            positions=int(item["positions"]),
            shortage_qty_total=float(item["shortage_qty_total"]),
        )
        for item in aggregate_client_category_exposure(rows, client_id)
    ]
