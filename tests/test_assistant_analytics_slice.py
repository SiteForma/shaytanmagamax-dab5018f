from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.app.db.models import ReserveRun, SalesFact, Sku, SkuCost
from apps.api.app.modules.assistant.context import build_context_bundle
from apps.api.app.modules.assistant.domain import AssistantContextBundle
from apps.api.app.modules.assistant.routing import route_question
from apps.api.app.modules.assistant.schemas import AssistantPinnedContext
from apps.api.app.modules.assistant.tools import tool_get_analytics_slice


def _bundle(db: Session, question: str) -> AssistantContextBundle:
    return build_context_bundle(
        db,
        route=route_question(db, question),
        pinned_context=AssistantPinnedContext(),
    )


def test_sales_revenue_by_client_month_matches_db(db_session: Session) -> None:
    execution = tool_get_analytics_slice(
        db_session,
        _bundle(db_session, "Покажи продажи по OBI за март 2025"),
        {
            "metrics": ["revenue", "sales_qty"],
            "dimensions": [],
            "client_id": "client_3",
            "date_from": "2025-03-01",
            "date_to": "2025-03-31",
        },
    )

    expected_qty, expected_revenue = db_session.execute(
        select(
            func.coalesce(func.sum(SalesFact.quantity), 0),
            func.coalesce(func.sum(SalesFact.revenue_amount), 0),
        ).where(
            SalesFact.client_id == "client_3",
            SalesFact.period_month >= "2025-03-01",
            SalesFact.period_month <= "2025-03-31",
        )
    ).one()
    assert execution.payload["status"] == "completed"
    assert execution.payload["rows"][0]["sales_qty"] == float(expected_qty)
    assert execution.payload["rows"][0]["revenue"] == float(expected_revenue)
    assert execution.payload["source"] == "sales"
    assert execution.source_refs[0]["sourceType"] == "sales"


def test_sales_breakdown_by_category(db_session: Session) -> None:
    execution = tool_get_analytics_slice(
        db_session,
        _bundle(db_session, "Покажи продажи по категориям за март 2025"),
        {
            "metrics": ["revenue", "sales_qty"],
            "dimensions": ["category"],
            "date_from": "2025-03-01",
            "date_to": "2025-03-31",
        },
    )

    assert execution.payload["status"] == "completed"
    assert execution.payload["rows"]
    assert "category" in execution.payload["rows"][0]


def test_top_sku_by_revenue_is_sorted(db_session: Session) -> None:
    execution = tool_get_analytics_slice(
        db_session,
        _bundle(db_session, "Покажи топ SKU по выручке за 2025"),
        {
            "metrics": ["revenue"],
            "dimensions": ["sku", "article"],
            "date_from": "2025-01-01",
            "date_to": "2025-12-31",
            "sort_by": "revenue",
            "sort_direction": "desc",
            "limit": 20,
        },
    )

    revenues = [row["revenue"] for row in execution.payload["rows"]]
    assert revenues == sorted(revenues, reverse=True)
    assert len(revenues) <= 20


def test_sales_profit_metrics_use_sku_cost_reference(db_session: Session) -> None:
    sku = db_session.get(Sku, "sku_2")
    assert sku is not None
    db_session.add(
        SkuCost(
            article=sku.article,
            product_name=sku.name,
            cost_rub=300,
            sku_id=sku.id,
        )
    )
    db_session.commit()

    execution = tool_get_analytics_slice(
        db_session,
        _bundle(db_session, "Покажи прибыль по артикулам за март 2025"),
        {
            "metrics": ["cost_amount", "gross_profit", "gross_margin_pct"],
            "dimensions": ["article"],
            "sku_id": sku.id,
            "date_from": "2025-03-01",
            "date_to": "2025-03-31",
        },
    )

    qty, revenue = db_session.execute(
        select(
            func.coalesce(func.sum(SalesFact.quantity), 0),
            func.coalesce(func.sum(SalesFact.revenue_amount), 0),
        ).where(
            SalesFact.sku_id == sku.id,
            SalesFact.period_month >= "2025-03-01",
            SalesFact.period_month <= "2025-03-31",
        )
    ).one()
    expected_cost = float(qty) * 300
    expected_profit = float(revenue) - expected_cost
    row = execution.payload["rows"][0]

    assert execution.payload["status"] == "completed"
    assert row["article"] == sku.article
    assert row["cost_amount"] == expected_cost
    assert row["gross_profit"] == expected_profit
    assert row["gross_margin_pct"] == round((expected_profit / float(revenue)) * 100, 4)
    assert any(ref["sourceType"] == "sku_costs" for ref in execution.source_refs)


def test_unit_cost_slice_reads_sku_cost_reference(db_session: Session) -> None:
    sku = db_session.get(Sku, "sku_1")
    assert sku is not None
    db_session.add(
        SkuCost(
            article=sku.article,
            product_name=sku.name,
            cost_rub=410.25,
            sku_id=sku.id,
        )
    )
    db_session.commit()

    execution = tool_get_analytics_slice(
        db_session,
        _bundle(db_session, "Покажи себестоимость по артикулам"),
        {
            "metrics": ["unit_cost"],
            "dimensions": ["article"],
            "sku_id": sku.id,
        },
    )

    assert execution.payload["status"] == "completed"
    assert execution.payload["source"] == "catalog"
    assert execution.payload["rows"][0]["article"] == sku.article
    assert execution.payload["rows"][0]["unit_cost"] == 410.25
    assert execution.source_refs[0]["sourceType"] == "sku_costs"


def test_analytics_slice_rejects_unknown_metric_dimension_and_sql(db_session: Session) -> None:
    unsupported = tool_get_analytics_slice(
        db_session,
        _bundle(db_session, "срез"),
        {
            "metrics": ["unknown_metric"],
            "dimensions": ["client"],
            "date_from": "2025-01-01",
            "date_to": "2025-12-31",
        },
    )

    assert unsupported.payload["status"] == "unsupported"
    assert "unknown_metric" in unsupported.payload["unsupported_metrics"]


def test_assistant_sales_followups_use_analytics_slice(client: TestClient) -> None:
    session = client.post("/api/assistant/sessions", json={"title": "Analytics followup"}).json()
    first = client.post(
        f"/api/assistant/sessions/{session['id']}/messages",
        json={"text": "Покажи продажи по OBI за март 2025"},
    ).json()["response"]
    assert first["intent"] == "analytics_slice"
    assert first["toolCalls"][0]["toolName"] == "get_analytics_slice"

    leroy = client.post(
        f"/api/assistant/sessions/{session['id']}/messages",
        json={"text": "А по Леруа?"},
    ).json()["response"]
    assert leroy["toolCalls"][0]["arguments"]["client_id"] == "client_1"
    assert leroy["toolCalls"][0]["arguments"]["date_from"] == "2025-03-01"

    qty = client.post(
        f"/api/assistant/sessions/{session['id']}/messages",
        json={"text": "А в штуках?"},
    ).json()["response"]
    assert qty["toolCalls"][0]["arguments"]["metrics"] == ["sales_qty"]

    categories = client.post(
        f"/api/assistant/sessions/{session['id']}/messages",
        json={"text": "А по категориям?"},
    ).json()["response"]
    assert categories["toolCalls"][0]["arguments"]["dimensions"] == ["category"]


def test_show_reserve_does_not_create_run_and_recalculate_requires_action(
    client: TestClient, db_session: Session
) -> None:
    before = db_session.scalar(select(func.count()).select_from(ReserveRun)) or 0

    show = client.post("/api/assistant/query", json={"text": "Покажи резерв по OBI"})
    after_show = db_session.scalar(select(func.count()).select_from(ReserveRun)) or 0
    recalc = client.post("/api/assistant/query", json={"text": "Пересчитай резерв по OBI"})
    after_recalc = db_session.scalar(select(func.count()).select_from(ReserveRun)) or 0

    assert show.status_code == 200
    assert show.json()["traceMetadata"]["resolved_tool"] == "get_reserve"
    assert before == after_show
    assert recalc.status_code == 200
    assert recalc.json()["traceMetadata"]["resolved_tool"] == "calculate_reserve"
    assert after_recalc == after_show + 1
