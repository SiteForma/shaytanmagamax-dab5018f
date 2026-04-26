from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from apps.api.app.modules.assistant.providers import plan_route_with_provider
from apps.api.app.modules.assistant.registry import get_default_tool_registry


class _FakeHttpResponse:
    def __init__(self, content: dict[str, Any]) -> None:
        self._content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {
            "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
            "choices": [{"message": {"content": json.dumps(self._content, ensure_ascii=False)}}],
        }


def _patch_llm_planner(monkeypatch, content: dict[str, Any]) -> None:
    class FakeHttpClient:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            pass

        def __enter__(self) -> "FakeHttpClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001, ANN002, ANN003
            return None

        def post(self, *args, **kwargs) -> _FakeHttpResponse:  # noqa: ANN002, ANN003
            return _FakeHttpResponse(content)

    monkeypatch.setattr("apps.api.app.modules.assistant.providers.httpx.Client", FakeHttpClient)


def _enable_llm(test_settings) -> None:
    test_settings.assistant_llm_enabled = True
    test_settings.assistant_provider = "openai_compatible"
    test_settings.assistant_openai_base_url = "https://api.openai.com/v1"
    test_settings.assistant_openai_api_key = "test-key"


def test_registry_specs_are_first_class_and_permissioned() -> None:
    registry = get_default_tool_registry()

    assert registry.default_plan_for_intent("reserve_calculation")[0] == "get_reserve"
    assert "get_reserve" in registry.tools_for_intent("reserve_calculation")
    assert "calculate_reserve" in registry.tools_for_intent("reserve_calculation")
    assert all(spec.handler is not None for spec in registry.specs)
    assert all(spec.required_capabilities for spec in registry.specs)


def test_planner_unknown_params_are_rejected_before_execution(test_settings, monkeypatch) -> None:
    _enable_llm(test_settings)
    _patch_llm_planner(
        monkeypatch,
        {
            "intent": "sales_summary",
            "toolName": "get_sales_summary",
            "params": {
                "date_from": "2025-01-01",
                "date_to": "2025-12-01",
                "arbitrary_filter": "anything",
            },
            "missingFields": [],
            "confidence": 0.9,
        },
    )

    plan = plan_route_with_provider(
        test_settings,
        question="Что с продажами в 2025?",
        deterministic_intent="sales_summary",
        history=[],
    )

    assert plan.planner == "deterministic"
    assert plan.params == {}
    assert plan.tool_names == []


def test_planner_sql_like_allowed_param_is_rejected(test_settings, monkeypatch) -> None:
    _enable_llm(test_settings)
    _patch_llm_planner(
        monkeypatch,
        {
            "intent": "management_report_summary",
            "toolName": "get_management_report",
            "params": {"question": "select * from management_report_metrics"},
            "missingFields": [],
            "confidence": 0.9,
        },
    )

    plan = plan_route_with_provider(
        test_settings,
        question="Покажи управленческий отчёт",
        deterministic_intent="management_report_summary",
        history=[],
    )

    assert plan.planner == "deterministic"
    assert plan.params == {}
    assert plan.tool_names == []


def test_planner_nonexistent_client_entity_is_rejected(client: TestClient, test_settings, monkeypatch) -> None:
    _enable_llm(test_settings)
    _patch_llm_planner(
        monkeypatch,
        {
            "intent": "sales_summary",
            "toolName": "get_sales_summary",
            "params": {
                "date_from": "2025-01-01",
                "date_to": "2025-12-01",
                "client_id": "client_private",
            },
            "missingFields": [],
            "confidence": 0.9,
        },
    )

    response = client.post("/api/assistant/query", json={"text": "Что с продажами в 2025?"})

    assert response.status_code == 403
    assert response.json()["code"] == "assistant_entity_not_available"
    assert response.json()["details"] == {"entity": "client", "param": "client_id"}


def test_completed_answer_trace_metadata_has_source_ref_count(client: TestClient) -> None:
    response = client.post("/api/assistant/query", json={"text": "Покажи резерв по OBI"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["traceMetadata"]["resolved_intent"] == "reserve_calculation"
    assert payload["traceMetadata"]["resolved_tool"] == "get_reserve"
    assert payload["traceMetadata"]["source_refs_count"] == len(payload["sourceRefs"])
    assert payload["traceMetadata"]["source_refs_count"] > 0


def test_new_topic_does_not_inherit_previous_reserve_filters(client: TestClient) -> None:
    session = client.post("/api/assistant/sessions", json={"title": "Topic reset"}).json()
    first = client.post(
        f"/api/assistant/sessions/{session['id']}/messages",
        json={"text": "Покажи резерв по OBI"},
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/assistant/sessions/{session['id']}/messages",
        json={"text": "Что с продажами в 2025?"},
    )

    assert second.status_code == 200
    payload = second.json()["response"]
    assert payload["intent"] == "analytics_slice"
    sales_tool = next(tool for tool in payload["toolCalls"] if tool["toolName"] == "get_analytics_slice")
    assert sales_tool["arguments"].get("client_id") is None


def test_problematic_followup_preserves_previous_intent_and_filters(client: TestClient) -> None:
    session = client.post("/api/assistant/sessions", json={"title": "Problematic followup"}).json()
    first = client.post(
        f"/api/assistant/sessions/{session['id']}/messages",
        json={"text": "Покажи резерв по OBI"},
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/assistant/sessions/{session['id']}/messages",
        json={"text": "Покажи только проблемные"},
    )

    assert second.status_code == 200
    payload = second.json()["response"]
    assert payload["intent"] == "reserve_calculation"
    assert payload["toolCalls"][0]["arguments"]["client_id"] == "client_3"
