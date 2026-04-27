from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True, slots=True)
class StockoutForecast:
    avg_daily_sales: float
    current_stock: float
    inbound_qty: float
    coverage_days: float | None
    stockout_date: str | None

    def to_payload(self) -> dict[str, float | str | None]:
        return {
            "avgDailySales": self.avg_daily_sales,
            "currentStock": self.current_stock,
            "inboundQty": self.inbound_qty,
            "coverageDays": self.coverage_days,
            "stockoutDate": self.stockout_date,
        }


@dataclass(frozen=True, slots=True)
class OrderRecommendation:
    target_coverage_months: float
    avg_monthly_sales: float
    current_stock: float
    inbound_qty: float
    recommended_qty: float

    def to_payload(self) -> dict[str, float]:
        return {
            "targetCoverageMonths": self.target_coverage_months,
            "avgMonthlySales": self.avg_monthly_sales,
            "currentStock": self.current_stock,
            "inboundQty": self.inbound_qty,
            "recommendedQty": self.recommended_qty,
        }


def forecast_stockout(
    *,
    avg_daily_sales: float,
    current_stock: float,
    inbound_qty: float = 0,
    as_of: date | None = None,
) -> StockoutForecast:
    available_qty = max(float(current_stock), 0) + max(float(inbound_qty), 0)
    if avg_daily_sales <= 0:
        return StockoutForecast(
            avg_daily_sales=float(avg_daily_sales),
            current_stock=float(current_stock),
            inbound_qty=float(inbound_qty),
            coverage_days=None,
            stockout_date=None,
        )
    coverage_days = available_qty / float(avg_daily_sales)
    base_date = as_of or date.today()
    return StockoutForecast(
        avg_daily_sales=float(avg_daily_sales),
        current_stock=float(current_stock),
        inbound_qty=float(inbound_qty),
        coverage_days=round(coverage_days, 2),
        stockout_date=(base_date + timedelta(days=int(coverage_days))).isoformat(),
    )


def recommend_order_qty(
    *,
    target_coverage_months: float,
    avg_monthly_sales: float,
    current_stock: float,
    inbound_qty: float = 0,
) -> OrderRecommendation:
    target_qty = max(float(target_coverage_months), 0) * max(float(avg_monthly_sales), 0)
    available_qty = max(float(current_stock), 0) + max(float(inbound_qty), 0)
    recommended_qty = max(target_qty - available_qty, 0)
    return OrderRecommendation(
        target_coverage_months=float(target_coverage_months),
        avg_monthly_sales=float(avg_monthly_sales),
        current_stock=float(current_stock),
        inbound_qty=float(inbound_qty),
        recommended_qty=round(recommended_qty, 2),
    )
