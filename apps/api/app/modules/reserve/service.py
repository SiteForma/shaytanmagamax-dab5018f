from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from apps.api.app.core.config import get_settings
from apps.api.app.db.models import ReserveRow, ReserveRun
from apps.api.app.modules.analytics.service import materialize_analytics
from apps.api.app.modules.reserve.domain import ReserveCalculationInput, ReserveComputationRow
from apps.api.app.modules.reserve.engine import calculate_reserve_preview
from apps.api.app.modules.reserve.read_models import summarize_reserve_rows
from apps.api.app.modules.reserve.schemas import (
    ReserveCalculationResponse,
    ReserveRowResponse,
    ReserveRunSummary,
    ReserveRunSummaryResponse,
)


def build_portfolio_request() -> ReserveCalculationInput:
    return ReserveCalculationInput(
        client_ids=None,
        include_inbound=True,
        inbound_statuses_to_count=["confirmed"],
        horizon_days=60,
        demand_strategy="weighted_recent_average",
        persist_run=True,
    )


def _request_payload(request: ReserveCalculationInput) -> dict[str, object]:
    return {
        "client_ids": list(request.client_ids or []),
        "sku_ids": list(request.sku_ids or []),
        "sku_codes": list(request.sku_codes or []),
        "category_ids": list(request.effective_category_ids()),
        "include_inbound": request.include_inbound,
        "inbound_statuses_to_count": list(request.inbound_statuses_to_count),
        "as_of_date": request.normalized_as_of_date().isoformat(),
        "horizon_days": request.horizon_days,
    }


def _run_matches_request(run: ReserveRun, request: ReserveCalculationInput) -> bool:
    expected = _request_payload(request)
    return (
        run.scope_type == request.scope_type()
        and run.grouping_mode == request.grouping_mode
        and run.demand_strategy == request.effective_demand_strategy()
        and run.reserve_months
        == (request.effective_reserve_months_override() or run.reserve_months)
        and abs(
            run.safety_factor - (request.effective_safety_factor_override() or run.safety_factor)
        )
        < 0.0001
        and run.include_inbound == request.include_inbound
        and run.horizon_days == request.horizon_days
        and run.filters_payload == expected
        and run.status == "completed"
    )


def _serialize_run(run: ReserveRun) -> ReserveRunSummary:
    return ReserveRunSummary(
        id=run.id,
        scope_type=run.scope_type,
        grouping_mode=run.grouping_mode,
        reserve_months=run.reserve_months,
        safety_factor=run.safety_factor,
        demand_strategy=run.demand_strategy,
        include_inbound=run.include_inbound,
        inbound_statuses=list(run.inbound_statuses),
        horizon_days=run.horizon_days,
        row_count=run.row_count,
        status=run.status,
        created_at=run.created_at.isoformat(),
        summary_payload=dict(run.summary_payload),
    )


def _serialize_row(row: ReserveRow) -> ReserveRowResponse:
    payload = row.explanation_payload or {}
    return ReserveRowResponse(
        client_id=row.client_id,
        client_name=str(payload.get("client_name", "")),
        sku_id=row.sku_id,
        article=str(payload.get("sku_article", "")),
        product_name=str(payload.get("product_name", "")),
        category=payload.get("category_name"),  # type: ignore[arg-type]
        policy_id=row.policy_id,
        client_priority_level=row.client_priority_level,
        sales_qty_1m=row.sales_qty_1m,
        sales_qty_3m=row.sales_qty_3m,
        sales_qty_6m=row.sales_qty_6m,
        avg_monthly_3m=row.avg_sales_3m,
        avg_monthly_6m=row.avg_sales_6m,
        history_months_available=row.history_months_available,
        last_sale_date=row.last_sale_date.isoformat() if row.last_sale_date else None,
        demand_stability=row.demand_stability,
        trend_signal=row.trend_signal,
        demand_per_month=row.demand_per_month,
        reserve_months=row.reserve_months,
        safety_factor=float(payload.get("safety_factor", 0.0)),
        target_reserve_qty=row.target_reserve_qty,
        free_stock=float(payload.get("allocated_free_stock_qty", row.free_stock_qty)),
        inbound_within_horizon=float(
            payload.get("allocated_inbound_qty", row.inbound_in_horizon_qty)
        ),
        total_free_stock_qty=row.free_stock_qty,
        total_inbound_in_horizon_qty=row.inbound_in_horizon_qty,
        allocated_free_stock_qty=float(payload.get("allocated_free_stock_qty", row.free_stock_qty)),
        allocated_inbound_qty=float(
            payload.get("allocated_inbound_qty", row.inbound_in_horizon_qty)
        ),
        available_qty=row.available_qty,
        shortage_qty=row.shortage_qty,
        coverage_months=(
            row.coverage_months if row.coverage_months > 0 else payload.get("coverage_months")
        ),
        status=row.status,
        status_reason=row.status_reason or str(payload.get("status_reason", "")),
        demand_basis=row.demand_basis,
        demand_basis_type=row.demand_basis_type,
        fallback_level=row.fallback_level,
        basis_window_used=row.basis_window_used,
        explanation_payload=dict(payload),
    )


def _serialize_computation_row(
    row: ReserveComputationRow, request: ReserveCalculationInput
) -> ReserveRowResponse:
    return ReserveRowResponse(
        client_id=row.client_id,
        client_name=row.client_name,
        sku_id=row.sku_id,
        article=row.article,
        product_name=row.product_name,
        category=row.category_name,
        policy_id=row.policy.policy_id,
        client_priority_level=row.policy.priority_level,
        sales_qty_1m=row.decision.metrics.sales_qty_1m,
        sales_qty_3m=row.decision.metrics.sales_qty_3m,
        sales_qty_6m=row.decision.metrics.sales_qty_6m,
        avg_monthly_3m=row.decision.metrics.avg_monthly_sales_3m,
        avg_monthly_6m=row.decision.metrics.avg_monthly_sales_6m,
        history_months_available=row.decision.metrics.history_months_available,
        last_sale_date=(
            row.decision.metrics.last_sale_date.isoformat()
            if row.decision.metrics.last_sale_date
            else None
        ),
        demand_stability=row.decision.metrics.demand_stability,
        trend_signal=row.decision.metrics.trend_direction,
        demand_per_month=row.decision.demand_per_month,
        reserve_months=row.policy.reserve_months,
        safety_factor=row.policy.safety_factor,
        target_reserve_qty=row.target_reserve_qty,
        free_stock=row.allocated_free_stock_qty,
        inbound_within_horizon=row.allocated_inbound_qty,
        total_free_stock_qty=row.supply_pool.free_stock_qty,
        total_inbound_in_horizon_qty=row.supply_pool.inbound_in_horizon_qty,
        allocated_free_stock_qty=row.allocated_free_stock_qty,
        allocated_inbound_qty=row.allocated_inbound_qty,
        available_qty=row.available_qty,
        shortage_qty=row.shortage_qty,
        coverage_months=row.coverage_months,
        status=row.status,
        status_reason=row.status_reason,
        demand_basis=request.effective_demand_strategy(),
        demand_basis_type=row.decision.demand_basis_type,
        fallback_level=row.decision.fallback_level,
        basis_window_used=row.decision.basis_window_used,
        explanation_payload=row.explanation_payload,
    )


def _persist_rows(
    db: Session,
    *,
    run: ReserveRun,
    rows: list[ReserveComputationRow],
    request: ReserveCalculationInput,
) -> None:
    db.execute(delete(ReserveRow).where(ReserveRow.run_id == run.id))
    for row in rows:
        db.add(
            ReserveRow(
                run_id=run.id,
                client_id=row.client_id,
                sku_id=row.sku_id,
                category_id=row.category_id,
                policy_id=row.policy.policy_id,
                client_priority_level=row.policy.priority_level,
                sales_qty_1m=row.decision.metrics.sales_qty_1m,
                sales_qty_3m=row.decision.metrics.sales_qty_3m,
                sales_qty_6m=row.decision.metrics.sales_qty_6m,
                history_months_available=row.decision.metrics.history_months_available,
                demand_basis=request.effective_demand_strategy(),
                demand_basis_type=row.decision.demand_basis_type,
                fallback_level=row.decision.fallback_level,
                basis_window_used=row.decision.basis_window_used,
                last_sale_date=row.decision.metrics.last_sale_date,
                trend_signal=row.decision.metrics.trend_direction,
                demand_stability=row.decision.metrics.demand_stability,
                avg_sales_3m=row.decision.metrics.avg_monthly_sales_3m,
                avg_sales_6m=row.decision.metrics.avg_monthly_sales_6m,
                demand_per_month=row.decision.demand_per_month,
                reserve_months=row.policy.reserve_months,
                target_reserve_qty=row.target_reserve_qty,
                free_stock_qty=row.supply_pool.free_stock_qty,
                inbound_in_horizon_qty=row.supply_pool.inbound_in_horizon_qty,
                available_qty=row.available_qty,
                shortage_qty=row.shortage_qty,
                coverage_months=row.coverage_months or 0.0,
                status=row.status,
                status_reason=row.status_reason,
                explanation_payload={
                    **row.explanation_payload,
                    "client_name": row.client_name,
                    "sku_article": row.article,
                    "product_name": row.product_name,
                    "category_name": row.category_name,
                    "safety_factor": row.policy.safety_factor,
                },
            )
        )


def find_recent_matching_run(
    db: Session,
    request: ReserveCalculationInput,
) -> ReserveRun | None:
    runs = db.scalars(select(ReserveRun).order_by(ReserveRun.created_at.desc())).all()
    for run in runs[:25]:
        if _run_matches_request(run, request):
            return run
    return None


def calculate_and_persist(
    db: Session,
    payload: ReserveCalculationInput,
    created_by_id: str | None = None,
    *,
    reuse_existing: bool = True,
) -> ReserveCalculationResponse:
    if payload.persist_run and reuse_existing:
        existing = find_recent_matching_run(db, payload)
        if existing is not None:
            return ReserveCalculationResponse(
                run=_serialize_run(existing),
                rows=get_run_rows(db, existing.id),
            )

    computed_rows = calculate_reserve_preview(db, payload)
    serialized_rows = [_serialize_computation_row(row, payload) for row in computed_rows]
    totals, status_counts = summarize_reserve_rows(serialized_rows)
    run = ReserveRun(
        created_by_id=created_by_id,
        status="completed",
        scope_type=payload.scope_type(),
        grouping_mode=payload.grouping_mode,
        reserve_months=payload.effective_reserve_months_override() or 3,
        safety_factor=payload.effective_safety_factor_override() or 1.1,
        demand_basis=payload.effective_demand_strategy(),
        demand_strategy=payload.effective_demand_strategy(),
        include_inbound=payload.include_inbound,
        inbound_statuses=list(payload.inbound_statuses_to_count),
        as_of_date=payload.normalized_as_of_date(),
        horizon_days=payload.horizon_days,
        filters_payload=_request_payload(payload),
        summary_payload={
            **totals,
            "status_counts": status_counts,
        },
        row_count=len(serialized_rows),
    )
    db.add(run)
    db.flush()
    _persist_rows(db, run=run, rows=computed_rows, request=payload)
    db.commit()
    materialize_analytics(db, get_settings())
    db.refresh(run)
    return ReserveCalculationResponse(
        run=_serialize_run(run),
        rows=get_run_rows(db, run.id),
    )


def ensure_reserve_run(
    db: Session,
    payload: ReserveCalculationInput,
    *,
    created_by_id: str | None = None,
) -> ReserveRun:
    existing = find_recent_matching_run(db, payload)
    if existing is not None:
        return existing
    result = calculate_and_persist(db, payload, created_by_id=created_by_id, reuse_existing=False)
    run = db.get(ReserveRun, result.run.id)
    assert run is not None
    return run


def get_portfolio_run(db: Session) -> ReserveRun | None:
    return find_recent_matching_run(db, build_portfolio_request())


def get_portfolio_rows(db: Session) -> tuple[ReserveRun | None, list[ReserveRowResponse]]:
    run = get_portfolio_run(db)
    if run is None:
        return None, []
    return run, get_run_rows(db, run.id)


def list_runs(db: Session) -> list[ReserveRunSummary]:
    runs = db.scalars(select(ReserveRun).order_by(ReserveRun.created_at.desc())).all()
    return [_serialize_run(run) for run in runs]


def get_run(db: Session, run_id: str) -> ReserveRunSummary | None:
    run = db.get(ReserveRun, run_id)
    if run is None:
        return None
    return _serialize_run(run)


def get_run_detail(db: Session, run_id: str) -> ReserveRunSummaryResponse | None:
    run = db.get(ReserveRun, run_id)
    if run is None:
        return None
    rows = get_run_rows(db, run_id)
    totals, status_counts = summarize_reserve_rows(rows)
    return ReserveRunSummaryResponse(
        run=_serialize_run(run), totals=totals, status_counts=status_counts
    )


def get_run_rows(db: Session, run_id: str) -> list[ReserveRowResponse]:
    rows = db.scalars(select(ReserveRow).where(ReserveRow.run_id == run_id)).all()
    return [_serialize_row(row) for row in rows]
