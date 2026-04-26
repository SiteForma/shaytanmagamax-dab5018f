from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from apps.api.app.db.models import Category, Client, DiyPolicy, Product, ReserveRow, ReserveRun, SalesFact, Sku
from apps.api.app.modules.reserve.domain import (
    DemandMetrics,
    EffectivePolicy,
    ReserveCalculationInput,
    ReserveEngineConfig,
)
from apps.api.app.modules.reserve.engine import _classify_status, _metrics_from_months, calculate_reserve_preview
from apps.api.app.modules.reserve.repository import _month_window_start
from apps.api.app.modules.reserve.service import calculate_and_persist, get_run_rows
from apps.api.app.modules.reserve.strategies import WeightedRecentAverageStrategy


def test_weighted_recent_average_strategy_blends_3m_and_6m() -> None:
    strategy = WeightedRecentAverageStrategy()
    decision = strategy.compute(
        demand_basis_type="client_sku",
        fallback_level="client_sku",
        fallback_reason="Прямая история клиент + SKU",
        metrics=DemandMetrics(
            sales_qty_1m=12,
            sales_qty_3m=30,
            sales_qty_6m=36,
            avg_monthly_sales_3m=10,
            avg_monthly_sales_6m=6,
            history_months_available=6,
            last_sale_date=None,
            demand_stability=0.82,
            trend_direction="flat",
        ),
        history_sufficient=True,
        config=ReserveEngineConfig(),
    )

    assert decision.demand_per_month == 8.6
    assert decision.basis_window_used == "weighted_3m_6m"


def test_metrics_average_sparse_history_over_full_windows() -> None:
    metrics = _metrics_from_months(
        {date(2026, 4, 1): 120},
        as_of_date=date(2026, 4, 20),
        last_sale_date=date(2026, 4, 1),
    )

    assert metrics.sales_qty_3m == 120
    assert metrics.sales_qty_6m == 120
    assert metrics.avg_monthly_sales_3m == 40.0
    assert metrics.avg_monthly_sales_6m == 20.0
    assert metrics.history_months_available == 1


def test_month_window_start_uses_calendar_month_arithmetic() -> None:
    assert _month_window_start(date(2026, 4, 20), months=6) == date(2025, 11, 1)
    assert _month_window_start(date(2026, 1, 5), months=6) == date(2025, 8, 1)


def test_status_classification_marks_no_history_for_zero_demand() -> None:
    status, reason = _classify_status(
        policy=EffectivePolicy(
            policy_id="policy_demo",
            client_id="client_demo",
            active=True,
            reserve_months=3,
            safety_factor=1.1,
            priority_level=1,
            fallback_chain=["client_sku", "global_sku", "insufficient_history"],
            allowed_fallback_depth=3,
        ),
        decision_demand_per_month=0,
        shortage_qty=0,
        coverage_months=None,
        target_reserve_qty=0,
        config=ReserveEngineConfig(),
        warnings=["insufficient_history"],
    )

    assert status == "no_history"
    assert "Недостаточно истории" in reason


def test_status_classification_marks_critical_when_shortage_ratio_is_high() -> None:
    status, reason = _classify_status(
        policy=EffectivePolicy(
            policy_id="policy_demo",
            client_id="client_demo",
            active=True,
            reserve_months=3,
            safety_factor=1.1,
            priority_level=1,
            fallback_chain=["client_sku"],
            allowed_fallback_depth=1,
        ),
        decision_demand_per_month=10,
        shortage_qty=18,
        coverage_months=0.5,
        target_reserve_qty=30,
        config=ReserveEngineConfig(),
        warnings=[],
    )

    assert status == "critical"
    assert "значительно ниже" in reason


def test_reserve_engine_uses_global_sku_fallback(db_session: Session) -> None:
    rows = calculate_reserve_preview(
        db_session,
        ReserveCalculationInput(
            client_ids=["client_1"],
            sku_ids=["sku_5"],
            reserve_months=3,
            safety_factor=1.1,
            demand_basis="blended",
            horizon_days=60,
        ),
    )

    assert len(rows) == 1
    assert rows[0].decision.fallback_level == "global_sku"
    assert rows[0].decision.demand_per_month > 0


def test_reserve_engine_uses_category_baseline_when_sku_has_no_history(db_session: Session) -> None:
    category = db_session.get(Category, "cat_handles")
    db_session.add(Client(id="client_empty", code="empty", name="New DIY", region="Moscow"))
    db_session.add(
        DiyPolicy(
            client_id="client_empty",
            reserve_months=3,
            safety_factor=1.1,
            priority_level=1,
            fallback_chain=["client_sku", "client_category", "global_sku", "category_baseline"],
        )
    )
    sku = Sku(
        id="sku_no_history",
        article="K-0000-ZZ",
        name="Experimental Handle",
        category_id=category.id if category else None,
        product=Product(id="prd_no_history", name="Experimental Handle", brand="MAGAMAX"),
        brand="MAGAMAX",
        unit="pcs",
        active=True,
    )
    db_session.add(sku)
    db_session.commit()

    rows = calculate_reserve_preview(
        db_session,
        ReserveCalculationInput(
            client_ids=["client_empty"],
            sku_ids=[sku.id],
            reserve_months=3,
            safety_factor=1.1,
            demand_basis="blended",
            horizon_days=60,
        ),
    )

    assert len(rows) == 1
    assert rows[0].decision.fallback_level == "category_baseline"
    assert rows[0].target_reserve_qty >= rows[0].decision.demand_per_month


def test_reserve_engine_allocates_shared_supply_pool_without_double_counting(
    db_session: Session,
) -> None:
    rows = calculate_reserve_preview(
        db_session,
        ReserveCalculationInput(
            client_ids=["client_1", "client_2"],
            sku_ids=["sku_1"],
            reserve_months=3,
            safety_factor=1.1,
            demand_basis="blended",
            horizon_days=60,
        ),
    )

    assert len(rows) == 2
    total_available = sum(row.available_qty for row in rows)
    shared_pool = rows[0].supply_pool.total_considered_available_qty
    assert total_available <= shared_pool


def test_reserve_run_and_rows_are_persisted_for_client_sku_scope(db_session: Session) -> None:
    result = calculate_and_persist(
        db_session,
        ReserveCalculationInput(
            client_ids=["client_2"],
            sku_ids=["sku_1", "sku_3"],
            reserve_months=3,
            safety_factor=1.1,
            demand_strategy="weighted_recent_average",
            persist_run=True,
            horizon_days=60,
        ),
        created_by_id="user_admin",
        reuse_existing=False,
    )

    run = db_session.get(ReserveRun, result.run.id)
    assert run is not None
    assert run.scope_type == "client_sku_list"
    assert run.row_count == 2
    assert run.summary_payload["positions"] == 2

    persisted_rows = db_session.query(ReserveRow).filter(ReserveRow.run_id == run.id).all()
    assert len(persisted_rows) == 2
    assert {row.client_id for row in persisted_rows} == {"client_2"}
    assert {row.sku_id for row in persisted_rows} == {"sku_1", "sku_3"}

    api_rows = get_run_rows(db_session, run.id)
    assert len(api_rows) == 2
    assert {row.sku_id for row in api_rows} == {"sku_1", "sku_3"}


def test_reserve_engine_excludes_sales_outside_calendar_window(db_session: Session) -> None:
    client = Client(
        id="client_window",
        code="window",
        name="Window DIY",
        region="Moscow",
        client_group="DIY",
        network_type="DIY",
        is_active=True,
    )
    db_session.add(client)
    db_session.add(
        DiyPolicy(
            client_id=client.id,
            reserve_months=3,
            safety_factor=1.1,
            priority_level=1,
            fallback_chain=["client_sku", "global_sku", "insufficient_history"],
            allowed_fallback_depth=3,
        )
    )
    sku = Sku(
        id="sku_window",
        article="WIN-001",
        name="Window SKU",
        product=Product(id="prd_window", name="Window Product", brand="MAGAMAX"),
        brand="MAGAMAX",
        unit="pcs",
        active=True,
    )
    db_session.add(sku)
    db_session.add_all(
        [
            SalesFact(
                source_batch_id="batch_old",
                client_id=client.id,
                sku_id=sku.id,
                category_id=None,
                period_month=date(2025, 10, 31),
                quantity=600,
                revenue_amount=None,
            ),
            SalesFact(
                source_batch_id="batch_in",
                client_id=client.id,
                sku_id=sku.id,
                category_id=None,
                period_month=date(2025, 11, 1),
                quantity=60,
                revenue_amount=None,
            ),
        ]
    )
    db_session.commit()

    rows = calculate_reserve_preview(
        db_session,
        ReserveCalculationInput(
            client_ids=[client.id],
            sku_ids=[sku.id],
            reserve_months=3,
            safety_factor=1.1,
            demand_strategy="weighted_recent_average",
            as_of_date=date(2026, 4, 20),
            horizon_days=60,
        ),
    )

    assert len(rows) == 1
    assert rows[0].decision.metrics.sales_qty_6m == 60
    assert rows[0].decision.metrics.avg_monthly_sales_6m == 10.0
