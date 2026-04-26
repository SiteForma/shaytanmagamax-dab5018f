from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.common.utils import utc_now
from apps.api.app.db.models import (
    AssistantMessage,
    Client,
    InboundDelivery,
    QualityIssue,
    UploadBatch,
)
from apps.api.app.modules.dashboard.schemas import (
    DashboardOverviewResponse,
    DashboardSummaryResponse,
    ExposedClientResponse,
    InboundShortagePoint,
    TopRiskSkuResponse,
)
from apps.api.app.modules.reserve.read_models import (
    aggregate_coverage_distribution,
    aggregate_exposed_clients,
    aggregate_inbound_vs_shortage,
    aggregate_top_risk_skus,
    summarize_reserve_rows,
)
from apps.api.app.modules.reserve.schemas import FreshnessPanelResponse
from apps.api.app.modules.reserve.service import get_portfolio_rows


def _latest_upload(db: Session) -> UploadBatch | None:
    return db.scalars(select(UploadBatch).order_by(UploadBatch.created_at.desc())).first()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _assistant_api_cost_rub(db: Session) -> float:
    cost_rub = 0.0
    messages = db.scalars(
        select(AssistantMessage).where(AssistantMessage.role == "assistant")
    ).all()
    for message in messages:
        response = message.response_payload or {}
        usage = response.get("tokenUsage") if isinstance(response, dict) else None
        if not isinstance(usage, dict):
            continue
        cost_rub += float(usage.get("estimatedCostRub") or usage.get("estimated_cost_rub") or 0)
    return round(cost_rub, 4)


def get_dashboard_overview(db: Session) -> DashboardOverviewResponse:
    run, rows = get_portfolio_rows(db)
    totals, _ = summarize_reserve_rows(rows)
    top_risk = aggregate_top_risk_skus(rows)[:8]
    exposed_clients = aggregate_exposed_clients(rows)[:6]
    latest_upload = _latest_upload(db)
    open_quality_issues = len(
        db.scalars(select(QualityIssue).where(QualityIssue.status == "open")).all()
    )
    latest_timestamp = _as_utc(run.created_at if run is not None else utc_now())
    if latest_upload and _as_utc(latest_upload.created_at) > latest_timestamp:
        latest_timestamp = _as_utc(latest_upload.created_at)
    freshness_delta = utc_now() - latest_timestamp
    freshness_hours = max(int(freshness_delta.total_seconds() // 3600), 0)

    inbound_by_month: dict[str, float] = defaultdict(float)
    for inbound in db.scalars(select(InboundDelivery).order_by(InboundDelivery.eta_date)).all():
        inbound_by_month[inbound.eta_date.strftime("%Y-%m")] += inbound.quantity
    inbound_vs_shortage = aggregate_inbound_vs_shortage(
        rows,
        [{"month": month, "inbound_qty": qty} for month, qty in inbound_by_month.items()],
        as_of_date=run.as_of_date if run and run.as_of_date else latest_timestamp.date(),
    )

    summary = DashboardSummaryResponse(
        total_skus_tracked=len({row.sku_id for row in rows}),
        active_diy_clients=len({client.id for client in db.scalars(select(Client)).all()}),
        positions_at_risk=int(totals["positions_at_risk"]),
        total_shortage_qty=float(totals["total_shortage_qty"]),
        inbound_qty_within_horizon=round(
            sum(item["inbound_qty"] for item in inbound_vs_shortage), 1
        ),
        avg_coverage_months=totals["avg_coverage_months"],  # type: ignore[arg-type]
        assistant_api_cost_rub=_assistant_api_cost_rub(db),
        open_quality_issues=open_quality_issues,
        last_update=latest_timestamp.isoformat(),
        freshness_hours=freshness_hours,
        latest_run_id=run.id if run else None,
    )
    freshness = FreshnessPanelResponse(
        last_upload_at=latest_upload.created_at.isoformat() if latest_upload else None,
        last_reserve_run_at=run.created_at.isoformat() if run else None,
        freshness_hours=freshness_hours,
        open_quality_issues=open_quality_issues,
        latest_run_id=run.id if run else None,
    )
    return DashboardOverviewResponse(
        summary=summary,
        top_risk_skus=[
            TopRiskSkuResponse(
                sku_id=str(item["sku_id"]),
                sku_code=str(item["sku_code"]),
                product_name=str(item["product_name"]),
                affected_clients_count=int(item["affected_clients_count"]),
                shortage_qty_total=float(item["shortage_qty_total"]),
                min_coverage_months=item["min_coverage_months"],  # type: ignore[arg-type]
                worst_status=str(item["worst_status"]),
                category_name=item["category_name"],  # type: ignore[arg-type]
            )
            for item in top_risk
        ],
        exposed_clients=[
            ExposedClientResponse(
                client_id=str(item["client_id"]),
                client_name=str(item["client_name"]),
                positions_tracked=int(item["positions_tracked"]),
                critical_positions=int(item["critical_positions"]),
                warning_positions=int(item["warning_positions"]),
                shortage_qty_total=float(item["shortage_qty_total"]),
                avg_coverage_months=item["avg_coverage_months"],  # type: ignore[arg-type]
                inbound_relief_qty=float(item["inbound_relief_qty"]),
            )
            for item in exposed_clients
        ],
        coverage_distribution=aggregate_coverage_distribution(rows),
        inbound_vs_shortage=[
            InboundShortagePoint(
                month=str(item["month"]),
                inbound_qty=float(item["inbound_qty"]),
                shortage_qty=float(item["shortage_qty"]),
            )
            for item in inbound_vs_shortage
        ],
        freshness=freshness,
    )


def get_summary(db: Session) -> DashboardSummaryResponse:
    return get_dashboard_overview(db).summary


def get_top_risk_skus(db: Session) -> list[TopRiskSkuResponse]:
    return get_dashboard_overview(db).top_risk_skus


def get_exposed_clients(db: Session) -> list[ExposedClientResponse]:
    return get_dashboard_overview(db).exposed_clients


def get_coverage_distribution(db: Session):
    return get_dashboard_overview(db).coverage_distribution


def get_inbound_vs_shortage(db: Session):
    return get_dashboard_overview(db).inbound_vs_shortage


def get_freshness(db: Session):
    return get_dashboard_overview(db).freshness
