from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from apps.api.app.modules.reserve.domain import DemandDecision, DemandMetrics, ReserveEngineConfig


class DemandStrategy(Protocol):
    name: str

    def compute(
        self,
        *,
        demand_basis_type: str,
        fallback_level: str,
        fallback_reason: str,
        metrics: DemandMetrics,
        history_sufficient: bool,
        config: ReserveEngineConfig,
    ) -> DemandDecision: ...


def _round(value: float, precision: int) -> float:
    return round(value, precision)


def _metrics_warning(metrics: DemandMetrics, history_sufficient: bool) -> list[str]:
    warnings: list[str] = []
    if not history_sufficient:
        warnings.append("weak_history")
    if metrics.history_months_available == 0:
        warnings.append("no_recent_sales")
    if metrics.trend_direction == "up":
        warnings.append("rising_demand")
    if metrics.trend_direction == "down":
        warnings.append("falling_demand")
    if metrics.demand_stability < 0.45 and metrics.history_months_available >= 2:
        warnings.append("volatile_history")
    return warnings


@dataclass(slots=True)
class WeightedRecentAverageStrategy:
    name: str = "weighted_recent_average"

    def compute(
        self,
        *,
        demand_basis_type: str,
        fallback_level: str,
        fallback_reason: str,
        metrics: DemandMetrics,
        history_sufficient: bool,
        config: ReserveEngineConfig,
    ) -> DemandDecision:
        if metrics.avg_monthly_sales_3m > 0 and metrics.avg_monthly_sales_6m > 0:
            demand_per_month = _round(
                metrics.avg_monthly_sales_3m * config.weighted_recent_weight_3m
                + metrics.avg_monthly_sales_6m * config.weighted_recent_weight_6m,
                config.quantity_precision,
            )
            basis_window_used = "weighted_3m_6m"
        elif metrics.avg_monthly_sales_3m > 0:
            demand_per_month = _round(metrics.avg_monthly_sales_3m, config.quantity_precision)
            basis_window_used = "3m"
        else:
            demand_per_month = _round(metrics.avg_monthly_sales_6m, config.quantity_precision)
            basis_window_used = "6m"
        return DemandDecision(
            demand_per_month=demand_per_month,
            demand_basis_type=demand_basis_type,
            fallback_level=fallback_level,  # type: ignore[arg-type]
            basis_window_used=basis_window_used,
            fallback_reason=fallback_reason,
            history_sufficient=history_sufficient,
            metrics=metrics,
            warnings=_metrics_warning(metrics, history_sufficient),
        )


@dataclass(slots=True)
class StrictRecentAverageStrategy:
    name: str = "strict_recent_average"

    def compute(
        self,
        *,
        demand_basis_type: str,
        fallback_level: str,
        fallback_reason: str,
        metrics: DemandMetrics,
        history_sufficient: bool,
        config: ReserveEngineConfig,
    ) -> DemandDecision:
        if metrics.avg_monthly_sales_3m > 0 and metrics.history_months_available >= 2:
            demand_per_month = _round(metrics.avg_monthly_sales_3m, config.quantity_precision)
            basis_window_used = "3m"
        elif metrics.avg_monthly_sales_6m > 0:
            demand_per_month = _round(metrics.avg_monthly_sales_6m, config.quantity_precision)
            basis_window_used = "6m_fallback"
        else:
            demand_per_month = 0.0
            basis_window_used = "none"
        warnings = _metrics_warning(metrics, history_sufficient)
        if basis_window_used == "6m_fallback":
            warnings.append("strict_recent_fell_back_to_6m")
        return DemandDecision(
            demand_per_month=demand_per_month,
            demand_basis_type=demand_basis_type,
            fallback_level=fallback_level,  # type: ignore[arg-type]
            basis_window_used=basis_window_used,
            fallback_reason=fallback_reason,
            history_sufficient=history_sufficient,
            metrics=metrics,
            warnings=warnings,
        )


@dataclass(slots=True)
class ConservativeFallbackStrategy:
    name: str = "conservative_fallback"

    def compute(
        self,
        *,
        demand_basis_type: str,
        fallback_level: str,
        fallback_reason: str,
        metrics: DemandMetrics,
        history_sufficient: bool,
        config: ReserveEngineConfig,
    ) -> DemandDecision:
        demand_per_month = _round(
            max(metrics.avg_monthly_sales_3m, metrics.avg_monthly_sales_6m),
            config.quantity_precision,
        )
        warnings = _metrics_warning(metrics, history_sufficient)
        if fallback_level != "client_sku":
            warnings.append("proxy_history_used")
        return DemandDecision(
            demand_per_month=demand_per_month,
            demand_basis_type=demand_basis_type,
            fallback_level=fallback_level,  # type: ignore[arg-type]
            basis_window_used="max_3m_6m",
            fallback_reason=fallback_reason,
            history_sufficient=history_sufficient,
            metrics=metrics,
            warnings=warnings,
        )


STRATEGIES: dict[str, DemandStrategy] = {
    "weighted_recent_average": WeightedRecentAverageStrategy(),
    "strict_recent_average": StrictRecentAverageStrategy(),
    "conservative_fallback": ConservativeFallbackStrategy(),
}


def get_demand_strategy(name: str) -> DemandStrategy:
    return STRATEGIES.get(name, STRATEGIES["weighted_recent_average"])
