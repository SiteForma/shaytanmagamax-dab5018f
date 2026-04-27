from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

InsightType = Literal[
    "growth",
    "decline",
    "anomaly",
    "risk",
    "opportunity",
    "data_quality",
    "recommendation",
]
InsightSeverity = Literal["info", "warning", "critical", "positive"]


@dataclass(frozen=True, slots=True)
class Insight:
    type: InsightType
    title: str
    explanation: str
    severity: InsightSeverity = "info"
    evidence: dict[str, Any] = field(default_factory=dict)
    suggested_followup: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "title": self.title,
            "explanation": self.explanation,
            "severity": self.severity,
            "evidence": self.evidence,
            "suggestedFollowup": self.suggested_followup,
        }


def build_comparison_insights(
    rows: list[dict[str, Any]],
    *,
    dimension_key: str,
    current_metric: str = "current_value",
    previous_metric: str = "previous_value",
) -> list[Insight]:
    if not rows:
        return []
    enriched: list[tuple[dict[str, Any], float, float]] = []
    for row in rows:
        current = float(row.get(current_metric) or 0)
        previous = float(row.get(previous_metric) or 0)
        enriched.append((row, current - previous, 0.0 if previous == 0 else (current - previous) / previous * 100))
    biggest_growth = max(enriched, key=lambda item: item[1], default=None)
    biggest_decline = min(enriched, key=lambda item: item[1], default=None)
    insights: list[Insight] = []
    if biggest_growth and biggest_growth[1] > 0:
        row, delta, delta_pct = biggest_growth
        insights.append(
            Insight(
                type="growth",
                title="Самый сильный рост",
                explanation=f"{row.get(dimension_key, 'Сегмент')} вырос на {delta:.1f} ({delta_pct:.1f}%).",
                severity="positive",
                evidence={"row": row, "delta": delta, "deltaPct": delta_pct},
            )
        )
    if biggest_decline and biggest_decline[1] < 0:
        row, delta, delta_pct = biggest_decline
        insights.append(
            Insight(
                type="decline",
                title="Самое сильное падение",
                explanation=f"{row.get(dimension_key, 'Сегмент')} просел на {abs(delta):.1f} ({abs(delta_pct):.1f}%).",
                severity="warning",
                evidence={"row": row, "delta": delta, "deltaPct": delta_pct},
                suggested_followup="Показать вклад в падение по SKU",
            )
        )
    return insights


def build_ranking_insights(
    rows: list[dict[str, Any]],
    *,
    metric: str,
    dimension_key: str,
) -> list[Insight]:
    if not rows:
        return []
    sorted_rows = sorted(rows, key=lambda row: float(row.get(metric) or 0), reverse=True)
    total = sum(float(row.get(metric) or 0) for row in sorted_rows)
    insights: list[Insight] = []
    top = sorted_rows[0]
    top_value = float(top.get(metric) or 0)
    insights.append(
        Insight(
            type="opportunity",
            title="Лидер среза",
            explanation=f"{top.get(dimension_key, 'Сегмент')} даёт максимум по метрике {metric}: {top_value:.1f}.",
            severity="positive",
            evidence={"row": top, "metric": metric},
        )
    )
    if total > 0 and top_value / total > 0.5:
        insights.append(
            Insight(
                type="risk",
                title="Концентрация результата",
                explanation="На один сегмент приходится больше 50% результата. Это риск концентрации.",
                severity="warning",
                evidence={"share": top_value / total, "row": top},
                suggested_followup="Разложить результат по клиентам и SKU",
            )
        )
    bottom_candidates = [row for row in sorted_rows if float(row.get(metric) or 0) > 0]
    if bottom_candidates:
        bottom = bottom_candidates[-1]
        insights.append(
            Insight(
                type="data_quality",
                title="Нижняя граница среза",
                explanation=f"Минимальный ненулевой результат: {bottom.get(dimension_key, 'Сегмент')}.",
                severity="info",
                evidence={"row": bottom, "metric": metric},
            )
        )
    return insights[:5]
