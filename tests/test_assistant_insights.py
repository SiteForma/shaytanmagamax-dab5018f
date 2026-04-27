from __future__ import annotations

from apps.api.app.modules.assistant.insights import (
    build_comparison_insights,
    build_ranking_insights,
)


def test_build_comparison_insights_detects_growth_and_decline() -> None:
    insights = build_comparison_insights(
        [
            {"client": "OBI", "current_value": 120, "previous_value": 100},
            {"client": "Леруа", "current_value": 80, "previous_value": 160},
        ],
        dimension_key="client",
    )

    assert [item.type for item in insights] == ["growth", "decline"]
    assert insights[0].severity == "positive"
    assert insights[1].severity == "warning"


def test_build_ranking_insights_detects_concentration() -> None:
    insights = build_ranking_insights(
        [
            {"category": "Вазы", "revenue": 80},
            {"category": "Корзины", "revenue": 20},
        ],
        metric="revenue",
        dimension_key="category",
    )

    assert insights[0].type == "opportunity"
    assert any(item.type == "risk" for item in insights)
