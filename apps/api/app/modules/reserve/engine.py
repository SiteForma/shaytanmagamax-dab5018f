from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from datetime import date
from statistics import pstdev

from sqlalchemy.orm import Session

from apps.api.app.db.models import Client, DiyPolicy, SalesFact, Sku
from apps.api.app.modules.reserve.domain import (
    DemandMetrics,
    EffectivePolicy,
    ReserveCalculationInput,
    ReserveComputationRow,
    ReserveEngineConfig,
    ReserveStatus,
    SupplyPool,
)
from apps.api.app.modules.reserve.repository import ReserveDataset, load_reserve_dataset
from apps.api.app.modules.reserve.strategies import get_demand_strategy


def _round(value: float, precision: int = 1) -> float:
    return round(value, precision)


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _month_sequence(as_of_date: date, count: int = 6) -> list[date]:
    current = _month_start(as_of_date)
    months = [current]
    for _ in range(count - 1):
        previous = months[-1].replace(day=1)
        if previous.month == 1:
            previous = previous.replace(year=previous.year - 1, month=12)
        else:
            previous = previous.replace(month=previous.month - 1)
        months.append(previous)
    return months


def _build_monthly_sales_index(
    sales_facts: list[SalesFact],
) -> tuple[
    dict[tuple[str, str], dict[date, float]],
    dict[tuple[str, str], dict[date, float]],
    dict[str, dict[date, float]],
    dict[str, dict[date, float]],
    dict[tuple[str, str], date],
]:
    client_sku: dict[tuple[str, str], dict[date, float]] = defaultdict(lambda: defaultdict(float))
    client_category: dict[tuple[str, str], dict[date, float]] = defaultdict(lambda: defaultdict(float))
    global_sku: dict[str, dict[date, float]] = defaultdict(lambda: defaultdict(float))
    category_baseline: dict[str, dict[date, float]] = defaultdict(lambda: defaultdict(float))
    last_sale_dates: dict[tuple[str, str], date] = {}
    for fact in sales_facts:
        month = _month_start(fact.period_month)
        client_sku[(fact.client_id, fact.sku_id)][month] += fact.quantity
        global_sku[fact.sku_id][month] += fact.quantity
        if fact.category_id:
            client_category[(fact.client_id, fact.category_id)][month] += fact.quantity
            category_baseline[fact.category_id][month] += fact.quantity
        current_last = last_sale_dates.get((fact.client_id, fact.sku_id))
        if current_last is None or fact.period_month > current_last:
            last_sale_dates[(fact.client_id, fact.sku_id)] = fact.period_month
    return client_sku, client_category, global_sku, category_baseline, last_sale_dates


def _metrics_from_months(
    monthly_values: dict[date, float],
    *,
    as_of_date: date,
    last_sale_date: date | None,
) -> DemandMetrics:
    months = _month_sequence(as_of_date, count=6)
    values = [_round(monthly_values.get(month, 0.0)) for month in months]
    non_zero_values = [value for value in values if value > 0]
    recent_three = values[:3]
    older_three = values[3:6]
    sales_qty_1m = _round(recent_three[0] if recent_three else 0.0)
    sales_qty_3m = _round(sum(recent_three))
    sales_qty_6m = _round(sum(values))
    months_available_6m = len(non_zero_values)
    avg_3m = _round(sales_qty_3m / 3, 1)
    avg_6m = _round(sales_qty_6m / 6, 1)
    if len(non_zero_values) >= 2 and sum(non_zero_values) > 0:
        coefficient = pstdev(non_zero_values) / (sum(non_zero_values) / len(non_zero_values))
        demand_stability = _round(max(0.0, 1 - coefficient), 2)
    elif len(non_zero_values) == 1:
        demand_stability = 0.4
    else:
        demand_stability = 0.0
    avg_old = sum(older_three) / 3 if older_three else 0
    if avg_old and avg_3m >= avg_old * 1.1:
        trend_direction = "up"
    elif avg_old and avg_3m <= avg_old * 0.9:
        trend_direction = "down"
    else:
        trend_direction = "flat"
    return DemandMetrics(
        sales_qty_1m=sales_qty_1m,
        sales_qty_3m=sales_qty_3m,
        sales_qty_6m=sales_qty_6m,
        avg_monthly_sales_3m=avg_3m,
        avg_monthly_sales_6m=avg_6m,
        history_months_available=months_available_6m,
        last_sale_date=last_sale_date,
        demand_stability=demand_stability,
        trend_direction=trend_direction,
    )


def _policy_override(source: dict[str, object], key_candidates: list[str]) -> dict[str, object] | None:
    for key in key_candidates:
        value = source.get(key)
        if isinstance(value, dict):
            return value
    return None


def _resolve_policy(
    client: Client,
    sku: Sku,
    policy: DiyPolicy | None,
    request: ReserveCalculationInput,
) -> EffectivePolicy:
    if policy is None:
        return EffectivePolicy(
            policy_id=None,
            client_id=client.id,
            active=True,
            reserve_months=request.effective_reserve_months_override() or 3,
            safety_factor=request.effective_safety_factor_override() or 1.1,
            priority_level=999,
            fallback_chain=[
                "client_sku",
                "client_category",
                "global_sku",
                "category_baseline",
                "insufficient_history",
            ],
            allowed_fallback_depth=4,
            notes="Базовая политика по умолчанию",
        )

    reserve_months = policy.reserve_months
    safety_factor = policy.safety_factor
    priority_level = policy.priority_level
    override_source = None
    if sku.category is not None:
        category_override = _policy_override(
            policy.category_overrides,
            [sku.category_id or "", sku.category.code, sku.category.name],
        )
        if category_override:
            reserve_months = int(category_override.get("reserve_months", reserve_months))
            safety_factor = float(category_override.get("safety_factor", safety_factor))
            priority_level = int(category_override.get("priority_level", priority_level))
            override_source = "category_override"
    sku_override = _policy_override(policy.sku_overrides, [sku.id, sku.article])
    if sku_override:
        reserve_months = int(sku_override.get("reserve_months", reserve_months))
        safety_factor = float(sku_override.get("safety_factor", safety_factor))
        priority_level = int(sku_override.get("priority_level", priority_level))
        override_source = "sku_override"
    if request.effective_reserve_months_override() is not None:
        reserve_months = request.effective_reserve_months_override() or reserve_months
        override_source = "run_override"
    if request.effective_safety_factor_override() is not None:
        safety_factor = request.effective_safety_factor_override() or safety_factor
        override_source = "run_override"
    return EffectivePolicy(
        policy_id=policy.id,
        client_id=client.id,
        active=policy.active,
        reserve_months=reserve_months,
        safety_factor=safety_factor,
        priority_level=priority_level,
        fallback_chain=list(policy.fallback_chain or []),
        allowed_fallback_depth=policy.allowed_fallback_depth or len(policy.fallback_chain or []),
        notes=policy.notes,
        override_source=override_source,
    )


def _fallback_candidates(
    *,
    client: Client,
    sku: Sku,
    as_of_date: date,
    client_sku_index: dict[tuple[str, str], dict[date, float]],
    client_category_index: dict[tuple[str, str], dict[date, float]],
    global_sku_index: dict[str, dict[date, float]],
    category_baseline_index: dict[str, dict[date, float]],
    last_sale_dates: dict[tuple[str, str], date],
) -> list[tuple[str, DemandMetrics, int, str]]:
    category_id = sku.category_id or ""
    return [
        (
            "client_sku",
            _metrics_from_months(
                client_sku_index.get((client.id, sku.id), {}),
                as_of_date=as_of_date,
                last_sale_date=last_sale_dates.get((client.id, sku.id)),
            ),
            2,
            "Использована прямая история клиент + SKU",
        ),
        (
            "client_category",
            _metrics_from_months(
                client_category_index.get((client.id, category_id), {}),
                as_of_date=as_of_date,
                last_sale_date=last_sale_dates.get((client.id, sku.id)),
            ),
            1,
            "Использована история клиент + категория, потому что прямой истории по SKU недостаточно",
        ),
        (
            "global_sku",
            _metrics_from_months(
                global_sku_index.get(sku.id, {}),
                as_of_date=as_of_date,
                last_sale_date=last_sale_dates.get((client.id, sku.id)),
            ),
            1,
            "Использована глобальная история по SKU, потому что клиентской истории недостаточно",
        ),
        (
            "category_baseline",
            _metrics_from_months(
                category_baseline_index.get(category_id, {}),
                as_of_date=as_of_date,
                last_sale_date=last_sale_dates.get((client.id, sku.id)),
            ),
            1,
            "Использован базовый спрос по категории, потому что истории по SKU недостаточно",
        ),
    ]


def _choose_demand_decision(
    *,
    client: Client,
    sku: Sku,
    policy: EffectivePolicy,
    request: ReserveCalculationInput,
    config: ReserveEngineConfig,
    client_sku_index: dict[tuple[str, str], dict[date, float]],
    client_category_index: dict[tuple[str, str], dict[date, float]],
    global_sku_index: dict[str, dict[date, float]],
    category_baseline_index: dict[str, dict[date, float]],
    last_sale_dates: dict[tuple[str, str], date],
    as_of_date: date,
):
    strategy = get_demand_strategy(request.effective_demand_strategy())
    fallback_chain = policy.fallback_chain or [
        "client_sku",
        "client_category",
        "global_sku",
        "category_baseline",
        "insufficient_history",
    ]
    allowed_chain = fallback_chain[: max(policy.allowed_fallback_depth, 1)]
    candidates = {
        level: (metrics, min_history, reason)
        for level, metrics, min_history, reason in _fallback_candidates(
            client=client,
            sku=sku,
            as_of_date=as_of_date,
            client_sku_index=client_sku_index,
            client_category_index=client_category_index,
            global_sku_index=global_sku_index,
            category_baseline_index=category_baseline_index,
            last_sale_dates=last_sale_dates,
        )
    }
    last_reason = "Недостаточно истории на всех разрешённых уровнях fallback"
    for level in allowed_chain:
        if level == "insufficient_history":
            break
        candidate = candidates.get(level)
        if candidate is None:
            continue
        metrics, min_history, reason = candidate
        history_sufficient = (
            metrics.history_months_available >= min_history and metrics.sales_qty_6m > 0
        )
        if history_sufficient:
            return strategy.compute(
                demand_basis_type=level,
                fallback_level=level,
                fallback_reason=reason,
                metrics=metrics,
                history_sufficient=True,
                config=config,
            )
        last_reason = reason
    zero_metrics = DemandMetrics(
        sales_qty_1m=0.0,
        sales_qty_3m=0.0,
        sales_qty_6m=0.0,
        avg_monthly_sales_3m=0.0,
        avg_monthly_sales_6m=0.0,
        history_months_available=0,
        last_sale_date=None,
        demand_stability=0.0,
        trend_direction="flat",
    )
    decision = strategy.compute(
        demand_basis_type="insufficient_history",
        fallback_level="insufficient_history",
        fallback_reason=last_reason,
        metrics=zero_metrics,
        history_sufficient=False,
        config=config,
    )
    decision.warnings.append("insufficient_history")
    return decision


def _classify_status(
    *,
    policy: EffectivePolicy,
    decision_demand_per_month: float,
    shortage_qty: float,
    coverage_months: float | None,
    target_reserve_qty: float,
    config: ReserveEngineConfig,
    warnings: list[str],
) -> tuple[ReserveStatus, str]:
    if not policy.active:
        return "inactive", "Политика DIY для этого клиента неактивна"
    if decision_demand_per_month <= 0:
        if "insufficient_history" in warnings:
            return "no_history", "Недостаточно истории, чтобы уверенно оценить спрос"
        return "healthy", "В выбранном горизонте нет активного спроса"
    target_coverage_months = policy.reserve_months * policy.safety_factor
    coverage = coverage_months or 0.0
    if shortage_qty <= 0:
        if coverage >= target_coverage_months * config.overstock_ratio:
            return "overstocked", "Покрытие существенно превышает целевой резерв"
        return "healthy", "Доступное количество закрывает целевой резерв"
    shortage_ratio = shortage_qty / target_reserve_qty if target_reserve_qty else 1.0
    if shortage_ratio >= config.critical_shortage_ratio or coverage < (
        target_coverage_months * config.critical_coverage_ratio
    ):
        return "critical", "Покрытие значительно ниже целевого резерва"
    return "warning", "Покрытие ниже целевого резерва"


def _build_supply_pool(dataset: ReserveDataset, sku: Sku, request: ReserveCalculationInput) -> SupplyPool:
    stock = dataset.stock_by_sku.get(sku.id)
    inbound_rows = dataset.inbound_by_sku.get(sku.id, []) if request.include_inbound else []
    inbound_qty = _round(sum(row.quantity for row in inbound_rows))
    free_stock_qty = _round(stock.free_stock_qty if stock else 0.0)
    return SupplyPool(
        sku_id=sku.id,
        free_stock_qty=free_stock_qty,
        inbound_in_horizon_qty=inbound_qty,
        total_considered_available_qty=_round(free_stock_qty + inbound_qty),
        inbound_statuses_counted=list(request.inbound_statuses_to_count if request.include_inbound else []),
    )


def calculate_reserve_preview(
    db: Session,
    request: ReserveCalculationInput,
    config: ReserveEngineConfig | None = None,
) -> list[ReserveComputationRow]:
    config = config or ReserveEngineConfig()
    dataset = load_reserve_dataset(db, request)
    (
        client_sku_index,
        client_category_index,
        global_sku_index,
        category_baseline_index,
        last_sale_dates,
    ) = _build_monthly_sales_index(dataset.sales_facts)

    pre_allocation: dict[str, list[dict[str, object]]] = defaultdict(list)
    for client in dataset.clients:
        for sku in dataset.skus:
            effective_policy = _resolve_policy(
                client,
                sku,
                dataset.policies_by_client.get(client.id),
                request,
            )
            decision = _choose_demand_decision(
                client=client,
                sku=sku,
                policy=effective_policy,
                request=request,
                config=config,
                client_sku_index=client_sku_index,
                client_category_index=client_category_index,
                global_sku_index=global_sku_index,
                category_baseline_index=category_baseline_index,
                last_sale_dates=last_sale_dates,
                as_of_date=dataset.as_of_date,
            )
            target_reserve_qty = _round(
                decision.demand_per_month
                * effective_policy.reserve_months
                * effective_policy.safety_factor,
                config.quantity_precision,
            )
            supply_pool = _build_supply_pool(dataset, sku, request)
            pre_allocation[sku.id].append(
                {
                    "client": client,
                    "sku": sku,
                    "policy": effective_policy,
                    "decision": decision,
                    "target_reserve_qty": target_reserve_qty,
                    "supply_pool": supply_pool,
                }
            )

    computed_rows: list[ReserveComputationRow] = []
    for sku_id, scoped_rows in pre_allocation.items():
        if not scoped_rows:
            continue
        supply_pool = scoped_rows[0]["supply_pool"]  # type: ignore[assignment]
        remaining_free = supply_pool.free_stock_qty
        remaining_inbound = supply_pool.inbound_in_horizon_qty
        ordered_rows = sorted(
            scoped_rows,
            key=lambda item: (
                item["policy"].priority_level,  # type: ignore[index]
                -float(item["target_reserve_qty"]),  # type: ignore[arg-type]
                item["client"].name,  # type: ignore[index]
            ),
        )
        for item in ordered_rows:
            client = item["client"]  # type: ignore[assignment]
            sku = item["sku"]  # type: ignore[assignment]
            policy = item["policy"]  # type: ignore[assignment]
            decision = item["decision"]  # type: ignore[assignment]
            target_reserve_qty = float(item["target_reserve_qty"])  # type: ignore[arg-type]
            allocated_free = min(remaining_free, target_reserve_qty)
            remaining_need = max(target_reserve_qty - allocated_free, 0.0)
            allocated_inbound = min(remaining_inbound, remaining_need) if request.include_inbound else 0.0
            remaining_free = _round(remaining_free - allocated_free, config.quantity_precision)
            remaining_inbound = _round(
                remaining_inbound - allocated_inbound, config.quantity_precision
            )
            available_qty = _round(allocated_free + allocated_inbound, config.quantity_precision)
            shortage_qty = _round(
                max(target_reserve_qty - available_qty, 0.0), config.quantity_precision
            )
            coverage_months = (
                _round(available_qty / decision.demand_per_month, config.quantity_precision)
                if decision.demand_per_month > 0
                else None
            )
            status, status_reason = _classify_status(
                policy=policy,
                decision_demand_per_month=decision.demand_per_month,
                shortage_qty=shortage_qty,
                coverage_months=coverage_months,
                target_reserve_qty=target_reserve_qty,
                config=config,
                warnings=decision.warnings,
            )
            explanation_payload = {
                "policy_used": asdict(policy),
                "demand_strategy_used": request.effective_demand_strategy(),
                "fallback_path_used": decision.fallback_level,
                "basis_window_used": decision.basis_window_used,
                "fallback_reason": decision.fallback_reason,
                "history_sufficiency": {
                    "history_months_available": decision.metrics.history_months_available,
                    "sufficient": decision.history_sufficient,
                },
                "sales_qty_1m": decision.metrics.sales_qty_1m,
                "sales_qty_3m": decision.metrics.sales_qty_3m,
                "sales_qty_6m": decision.metrics.sales_qty_6m,
                "avg_sales_3m": decision.metrics.avg_monthly_sales_3m,
                "avg_sales_6m": decision.metrics.avg_monthly_sales_6m,
                "last_sale_date": (
                    decision.metrics.last_sale_date.isoformat()
                    if decision.metrics.last_sale_date
                    else None
                ),
                "trend_direction": decision.metrics.trend_direction,
                "demand_stability": decision.metrics.demand_stability,
                "demand_per_month": decision.demand_per_month,
                "reserve_months": policy.reserve_months,
                "safety_factor": policy.safety_factor,
                "target_reserve_qty": target_reserve_qty,
                "free_stock_qty": supply_pool.free_stock_qty,
                "inbound_in_horizon_qty": supply_pool.inbound_in_horizon_qty,
                "total_considered_available_qty": supply_pool.total_considered_available_qty,
                "allocated_free_stock_qty": _round(allocated_free),
                "allocated_inbound_qty": _round(allocated_inbound),
                "available_qty": available_qty,
                "shortage_qty": shortage_qty,
                "coverage_months": coverage_months,
                "status_reason": status_reason,
                "warnings": decision.warnings,
                "allocation": {
                    "priority_level": policy.priority_level,
                    "remaining_free_after_allocation": remaining_free,
                    "remaining_inbound_after_allocation": remaining_inbound,
                },
            }
            computed_rows.append(
                ReserveComputationRow(
                    client_id=client.id,
                    client_name=client.name,
                    sku_id=sku_id,
                    article=sku.article,
                    product_name=sku.name,
                    category_id=sku.category_id,
                    category_name=sku.category.name if sku.category else None,
                    policy=policy,
                    decision=decision,
                    supply_pool=supply_pool,
                    allocated_free_stock_qty=_round(allocated_free),
                    allocated_inbound_qty=_round(allocated_inbound),
                    available_qty=available_qty,
                    target_reserve_qty=target_reserve_qty,
                    shortage_qty=shortage_qty,
                    coverage_months=coverage_months,
                    status=status,
                    status_reason=status_reason,
                    explanation_payload=explanation_payload,
                )
            )
    return computed_rows
