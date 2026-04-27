from __future__ import annotations

from datetime import date

from apps.api.app.modules.assistant.forecasting import forecast_stockout, recommend_order_qty


def test_forecast_stockout_is_transparent_and_weightless() -> None:
    forecast = forecast_stockout(
        avg_daily_sales=10,
        current_stock=40,
        inbound_qty=20,
        as_of=date(2025, 3, 1),
    )

    assert forecast.coverage_days == 6
    assert forecast.stockout_date == "2025-03-07"


def test_forecast_stockout_handles_zero_demand() -> None:
    forecast = forecast_stockout(avg_daily_sales=0, current_stock=40)

    assert forecast.coverage_days is None
    assert forecast.stockout_date is None


def test_recommend_order_qty_uses_target_coverage() -> None:
    recommendation = recommend_order_qty(
        target_coverage_months=3,
        avg_monthly_sales=100,
        current_stock=80,
        inbound_qty=20,
    )

    assert recommendation.recommended_qty == 200
