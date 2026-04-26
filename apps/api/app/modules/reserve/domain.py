from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

DemandStrategyName = Literal[
    "weighted_recent_average",
    "strict_recent_average",
    "conservative_fallback",
]
ReserveStatus = Literal[
    "healthy",
    "warning",
    "critical",
    "no_history",
    "inactive",
    "overstocked",
]
FallbackLevel = Literal[
    "client_sku",
    "client_category",
    "global_sku",
    "category_baseline",
    "insufficient_history",
]


@dataclass(slots=True)
class ReserveCalculationInput:
    client_ids: list[str] | None = None
    sku_ids: list[str] | None = None
    sku_codes: list[str] | None = None
    category_ids: list[str] | None = None
    reserve_months_override: int | None = None
    safety_factor_override: float | None = None
    demand_strategy: DemandStrategyName = "weighted_recent_average"
    include_inbound: bool = True
    inbound_statuses_to_count: list[str] = field(default_factory=lambda: ["confirmed"])
    as_of_date: date | None = None
    grouping_mode: str = "client_sku"
    persist_run: bool = True
    horizon_days: int = 60

    # Compatibility fields for the existing shell.
    demand_basis: str | None = "weighted_recent_average"
    reserve_months: int | None = None
    safety_factor: float | None = None
    categories: list[str] | None = None

    def normalized_as_of_date(self) -> date:
        return self.as_of_date or date.today()

    def effective_reserve_months_override(self) -> int | None:
        return self.reserve_months_override or self.reserve_months

    def effective_safety_factor_override(self) -> float | None:
        return self.safety_factor_override or self.safety_factor

    def effective_category_ids(self) -> list[str]:
        return list(self.category_ids or self.categories or [])

    def effective_demand_strategy(self) -> DemandStrategyName:
        if self.demand_basis in {
            "weighted_recent_average",
            "strict_recent_average",
            "conservative_fallback",
        }:
            return self.demand_basis  # type: ignore[return-value]
        if self.demand_basis == "sales_3m":
            return "strict_recent_average"
        if self.demand_basis == "sales_6m":
            return "conservative_fallback"
        return self.demand_strategy

    def scope_type(self) -> str:
        client_count = len(self.client_ids or [])
        sku_count = len(self.sku_ids or self.sku_codes or [])
        category_count = len(self.effective_category_ids())
        if client_count == 1 and sku_count:
            return "client_sku_list"
        if client_count == 1 and category_count:
            return "client_category"
        if client_count == 1:
            return "client_full_assortment"
        if category_count:
            return "portfolio_category"
        return "portfolio_full_assortment"


@dataclass(slots=True)
class ReserveEngineConfig:
    direct_history_min_months: int = 2
    fallback_history_min_months: int = 1
    weighted_recent_weight_3m: float = 0.65
    weighted_recent_weight_6m: float = 0.35
    critical_shortage_ratio: float = 0.5
    critical_coverage_ratio: float = 0.4
    overstock_ratio: float = 2.0
    quantity_precision: int = 1


@dataclass(slots=True)
class EffectivePolicy:
    policy_id: str | None
    client_id: str
    active: bool
    reserve_months: int
    safety_factor: float
    priority_level: int
    fallback_chain: list[str]
    allowed_fallback_depth: int
    notes: str | None = None
    override_source: str | None = None


@dataclass(slots=True)
class DemandMetrics:
    sales_qty_1m: float
    sales_qty_3m: float
    sales_qty_6m: float
    avg_monthly_sales_3m: float
    avg_monthly_sales_6m: float
    history_months_available: int
    last_sale_date: date | None
    demand_stability: float
    trend_direction: str


@dataclass(slots=True)
class DemandDecision:
    demand_per_month: float
    demand_basis_type: str
    fallback_level: FallbackLevel
    basis_window_used: str
    fallback_reason: str
    history_sufficient: bool
    metrics: DemandMetrics
    warnings: list[str]


@dataclass(slots=True)
class SupplyPool:
    sku_id: str
    free_stock_qty: float
    inbound_in_horizon_qty: float
    total_considered_available_qty: float
    inbound_statuses_counted: list[str]


@dataclass(slots=True)
class ReserveComputationRow:
    client_id: str
    client_name: str
    sku_id: str
    article: str
    product_name: str
    category_id: str | None
    category_name: str | None
    policy: EffectivePolicy
    decision: DemandDecision
    supply_pool: SupplyPool
    allocated_free_stock_qty: float
    allocated_inbound_qty: float
    available_qty: float
    target_reserve_qty: float
    shortage_qty: float
    coverage_months: float | None
    status: ReserveStatus
    status_reason: str
    explanation_payload: dict[str, object]
