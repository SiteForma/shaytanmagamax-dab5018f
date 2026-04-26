from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from apps.api.app.modules.assistant.orchestration import execute_assistant_query
from apps.api.app.modules.assistant.routing import route_question
from apps.api.app.modules.assistant.schemas import AssistantQueryRequest


def test_assistant_routing_extracts_client_sku_and_months(db_session: Session) -> None:
    route = route_question(
        db_session,
        "Рассчитай резерв для Leman Pro на 3 месяца по SKU K-2650-CR",
    )

    assert route.intent == "reserve_calculation"
    assert route.extracted_client_id == "client_2"
    assert route.extracted_sku_ids == ["sku_1"]
    assert route.reserve_months == 3


def test_assistant_query_returns_structured_reserve_response(client: TestClient) -> None:
    response = client.post(
        "/api/assistant/query",
        json={
            "text": "Рассчитай резерв на 3 месяца по этому SKU",
            "context": {
                "selectedClientId": "client_2",
                "selectedSkuId": "sku_1",
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "reserve_calculation"
    assert payload["status"] in {"completed", "partial"}
    assert payload["sections"]
    assert any(item["sourceType"] == "reserve_engine" for item in payload["sourceRefs"])
    assert any(tool["toolName"] == "calculate_reserve" for tool in payload["toolCalls"])


def test_assistant_reserve_explanation_uses_pinned_context(client: TestClient) -> None:
    response = client.post(
        "/api/assistant/query",
        json={
            "text": "Почему эта позиция критична?",
            "context": {
                "selectedClientId": "client_2",
                "selectedSkuId": "sku_1",
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "reserve_explanation"
    assert any(item["sourceType"] == "diy_policy" for item in payload["sourceRefs"])
    assert payload["summary"]


def test_assistant_session_lifecycle(client: TestClient) -> None:
    session_response = client.post(
        "/api/assistant/sessions",
        json={"title": "Тестовая AI-сессия", "pinnedContext": {"selectedClientId": "client_1"}},
    )
    assert session_response.status_code == 200
    session = session_response.json()

    list_response = client.get("/api/assistant/sessions")
    assert list_response.status_code == 200
    assert any(item["id"] == session["id"] for item in list_response.json())

    post_message_response = client.post(
        f"/api/assistant/sessions/{session['id']}/messages",
        json={"text": "Покажи позиции ниже резерва по этому клиенту"},
    )
    assert post_message_response.status_code == 200
    result = post_message_response.json()
    assert result["response"]["intent"] == "diy_coverage_check"
    assert result["assistantMessage"]["role"] == "assistant"

    messages_response = client.get(f"/api/assistant/sessions/{session['id']}/messages")
    assert messages_response.status_code == 200
    messages = messages_response.json()
    assert len(messages) == 2
    assert {message["role"] for message in messages} == {"user", "assistant"}


def test_assistant_session_can_be_renamed_and_archived(client: TestClient) -> None:
    session_response = client.post(
        "/api/assistant/sessions",
        json={"title": "Черновик сессии", "pinnedContext": {"selectedClientId": "client_1"}},
    )
    assert session_response.status_code == 200
    session = session_response.json()

    patch_response = client.patch(
        f"/api/assistant/sessions/{session['id']}",
        json={
            "title": "Сессия по Леман Про",
            "status": "archived",
            "pinnedContext": {"selectedClientId": "client_2", "selectedSkuId": "sku_1"},
        },
    )
    assert patch_response.status_code == 200
    payload = patch_response.json()
    assert payload["title"] == "Сессия по Леман Про"
    assert payload["status"] == "archived"
    assert payload["pinnedContext"]["selectedClientId"] == "client_2"
    assert payload["pinnedContext"]["selectedSkuId"] == "sku_1"


def test_assistant_query_handles_upload_and_quality_awareness(client: TestClient) -> None:
    response = client.post(
        "/api/assistant/query",
        json={"text": "Когда обновлялись данные и есть ли quality issues?"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] in {"upload_status_summary", "quality_issue_summary"}
    assert any(
        item["sourceType"] in {"upload_batch", "quality"}
        for item in payload["sourceRefs"]
    )


def test_assistant_provider_disabled_falls_back_to_deterministic(
    db_session: Session,
    test_settings,
) -> None:
    test_settings.assistant_provider = "openai_compatible"
    response = execute_assistant_query(
        db_session,
        test_settings,
        payload=AssistantQueryRequest(
            text="Суммируй ситуацию по SKU K-2650-CR",
            context={"selectedSkuId": "sku_1"},
        ),
        created_by_id="user_admin",
    )

    assert response.provider == "deterministic"
    assert any(warning.code == "provider_unavailable" for warning in response.warnings)


def test_assistant_provider_can_polish_response_when_enabled(
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
                                    "title": "LLM-уточнённая сводка по SKU",
                                    "summary": "Провайдер аккуратно уточнил формулировку без изменения фактов.",
                                    "sections": [],
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

    monkeypatch.setattr(
        "apps.api.app.modules.assistant.providers.httpx.Client",
        FakeHttpClient,
    )
    test_settings.assistant_llm_enabled = True
    test_settings.assistant_provider = "openai_compatible"
    test_settings.assistant_openai_base_url = "https://api.openai.com/v1"
    test_settings.assistant_openai_api_key = "test-key"

    response = execute_assistant_query(
        db_session,
        test_settings,
        payload=AssistantQueryRequest(
            text="Суммируй ситуацию по SKU K-2650-CR",
            context={"selectedSkuId": "sku_1"},
        ),
        created_by_id="user_admin",
    )

    assert response.provider == "openai_compatible"
    assert response.title == "LLM-уточнённая сводка по SKU"
    assert response.summary == "Провайдер аккуратно уточнил формулировку без изменения фактов."
