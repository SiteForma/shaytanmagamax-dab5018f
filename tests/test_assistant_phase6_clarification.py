from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.app.db.models import ReserveRun
from apps.api.app.modules.assistant.providers import plan_route_with_provider


def test_show_reserve_without_client_reads_latest_reserve_without_mutation(
    client: TestClient,
    db_session: Session,
) -> None:
    before = db_session.scalar(select(func.count()).select_from(ReserveRun))
    response = client.post("/api/assistant/query", json={"text": "Покажи резерв"})
    after = db_session.scalar(select(func.count()).select_from(ReserveRun))

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "answer"
    assert payload["status"] in {"completed", "partial"}
    assert payload["traceMetadata"]["resolved_tool"] == "get_reserve"
    assert before == after


def test_show_reserve_for_obi_uses_client_context(client: TestClient) -> None:
    response = client.post("/api/assistant/query", json={"text": "Покажи резерв по OBI"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "reserve_calculation"
    assert payload["type"] == "answer"
    assert payload["toolCalls"][0]["arguments"]["client_id"] == "client_3"
    assert payload["traceMetadata"]["resolved_intent"] == "reserve_calculation"
    assert payload["traceMetadata"]["resolved_tool"] == "get_reserve"
    assert payload["traceMetadata"]["missing_fields"] == []


def test_reserve_explanation_followup_uses_previous_state(client: TestClient) -> None:
    session = client.post("/api/assistant/sessions", json={"title": "Reserve followup"}).json()
    first = client.post(
        f"/api/assistant/sessions/{session['id']}/messages",
        json={"text": "Покажи резерв по OBI"},
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/assistant/sessions/{session['id']}/messages",
        json={"text": "Почему такой резерв?"},
    )

    assert second.status_code == 200
    payload = second.json()["response"]
    assert payload["intent"] == "reserve_explanation"
    assert any(tool["toolName"] == "get_reserve_explanation" for tool in payload["toolCalls"])
    assert payload["sourceRefs"]


def test_short_why_followup_uses_previous_reserve_state(client: TestClient) -> None:
    session = client.post("/api/assistant/sessions", json={"title": "Short why"}).json()
    first = client.post(
        f"/api/assistant/sessions/{session['id']}/messages",
        json={"text": "Покажи резерв по OBI"},
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/assistant/sessions/{session['id']}/messages",
        json={"text": "а почему?"},
    )

    assert second.status_code == 200
    payload = second.json()["response"]
    assert payload["intent"] == "reserve_explanation"
    assert payload["traceMetadata"]["resolved_tool"] == "get_reserve_explanation"


def test_sales_summary_without_period_returns_clarification(client: TestClient) -> None:
    response = client.post("/api/assistant/query", json={"text": "Что с продажами?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "analytics_slice"
    assert payload["type"] == "clarification"
    assert "period" in {field["name"] for field in payload["missingFields"]}


def test_short_answer_after_clarification_continues_pending_intent(client: TestClient) -> None:
    session = client.post("/api/assistant/sessions", json={"title": "Clarification"}).json()
    first = client.post(
        f"/api/assistant/sessions/{session['id']}/messages",
        json={"text": "Пересчитай резерв"},
    )
    assert first.status_code == 200
    assert first.json()["response"]["pendingIntent"] == "reserve_calculation"

    second = client.post(
        f"/api/assistant/sessions/{session['id']}/messages",
        json={"text": "OBI Россия"},
    )

    assert second.status_code == 200
    payload = second.json()["response"]
    assert payload["intent"] == "reserve_calculation"
    assert payload["type"] == "answer"
    assert payload["toolCalls"][0]["arguments"]["client_id"] == "client_3"


def test_followup_client_change_preserves_previous_intent(client: TestClient) -> None:
    session = client.post("/api/assistant/sessions", json={"title": "Client followup"}).json()
    client.post(
        f"/api/assistant/sessions/{session['id']}/messages",
        json={"text": "Покажи резерв по OBI"},
    )

    response = client.post(
        f"/api/assistant/sessions/{session['id']}/messages",
        json={"text": "А по Леруа?"},
    )

    assert response.status_code == 200
    payload = response.json()["response"]
    assert payload["intent"] == "reserve_calculation"
    assert payload["toolCalls"][0]["arguments"]["client_id"] == "client_1"


def test_period_comparison_without_metric_returns_clarification(client: TestClient) -> None:
    response = client.post("/api/assistant/query", json={"text": "Сравни с прошлым месяцем"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "period_comparison"
    assert payload["type"] == "clarification"
    assert "metric" in {field["name"] for field in payload["missingFields"]}


def test_period_comparison_followup_after_sales_keeps_domain_state(client: TestClient) -> None:
    session = client.post("/api/assistant/sessions", json={"title": "Sales comparison"}).json()
    first = client.post(
        f"/api/assistant/sessions/{session['id']}/messages",
        json={"text": "Что с продажами за март 2025?"},
    )
    assert first.status_code == 200
    assert first.json()["response"]["intent"] == "analytics_slice"

    second = client.post(
        f"/api/assistant/sessions/{session['id']}/messages",
        json={"text": "сравни с прошлым месяцем"},
    )

    assert second.status_code == 200
    payload = second.json()["response"]
    assert payload["intent"] == "period_comparison"
    assert payload["type"] == "answer"
    tool = next(tool for tool in payload["toolCalls"] if tool["toolName"] == "get_period_comparison")
    assert tool["arguments"]["current_period"] == "2025-03"
    assert tool["arguments"]["previous_period"] == "2025-02"


def test_stock_risk_question_uses_stock_tool(client: TestClient) -> None:
    response = client.post("/api/assistant/query", json={"text": "Какие SKU в зоне риска?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "stock_risk_summary"
    assert any(tool["toolName"] == "get_stock_coverage" for tool in payload["toolCalls"])


def test_planner_unknown_tool_is_rejected_safely(
    db_session: Session,
    test_settings,
    monkeypatch,
) -> None:
    class FakeHttpResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "intent": "sales_summary",
                                    "toolName": "run_sql",
                                    "params": {"sql": "select * from sales_facts"},
                                    "missingFields": [],
                                    "followupQuestion": None,
                                    "confidence": 0.9,
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }

    class FakeHttpClient:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            pass

        def __enter__(self) -> "FakeHttpClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001, ANN002, ANN003
            return None

        def post(self, *args, **kwargs) -> FakeHttpResponse:  # noqa: ANN002, ANN003
            return FakeHttpResponse()

    monkeypatch.setattr("apps.api.app.modules.assistant.providers.httpx.Client", FakeHttpClient)
    test_settings.assistant_llm_enabled = True
    test_settings.assistant_provider = "openai_compatible"
    test_settings.assistant_openai_base_url = "https://api.openai.com/v1"
    test_settings.assistant_openai_api_key = "test-key"

    plan = plan_route_with_provider(
        test_settings,
        question="Что с продажами?",
        deterministic_intent="sales_summary",
        history=[],
    )

    assert plan.intent == "sales_summary"
    assert plan.planner == "deterministic"
    assert plan.tool_names == []
