from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from apps.api.app.db.models import AssistantMessage, AssistantSession
from apps.api.app.modules.assistant.orchestration import execute_assistant_query
from apps.api.app.modules.assistant.providers import plan_route_with_provider
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


def test_assistant_routing_uses_free_chat_for_domain_usage_messages(db_session: Session) -> None:
    route = route_question(
        db_session,
        "Привет, объясни коротко как с тобой лучше работать",
    )

    assert route.intent == "free_chat"
    assert not route.warnings


def test_assistant_query_returns_domain_chat_response_without_tool_calls(client: TestClient) -> None:
    response = client.post(
        "/api/assistant/query",
        json={"text": "Привет, как лучше задавать тебе вопросы?"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "free_chat"
    assert payload["status"] == "completed"
    assert payload["toolCalls"] == []
    assert payload["sections"]
    assert not any(warning["code"] == "unsupported_intent" for warning in payload["warnings"])


def test_assistant_rejects_out_of_scope_questions(client: TestClient) -> None:
    response = client.post(
        "/api/assistant/query",
        json={"text": "Кто написал Евгения Онегина?"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "unsupported_or_ambiguous"
    assert payload["status"] == "unsupported"
    assert payload["provider"] == "deterministic"
    assert payload["toolCalls"] == []
    assert "Я могу помочь только с работой MAGAMAX" in payload["summary"]
    assert any(warning["code"] == "out_of_scope_or_ambiguous" for warning in payload["warnings"])


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


def test_assistant_session_can_be_deleted(client: TestClient, db_session: Session) -> None:
    session_response = client.post(
        "/api/assistant/sessions",
        json={"title": "Удаляемая сессия"},
    )
    assert session_response.status_code == 200
    session = session_response.json()

    message_response = client.post(
        f"/api/assistant/sessions/{session['id']}/messages",
        json={"text": "Привет, как работать с MAGAMAX?"},
    )
    assert message_response.status_code == 200

    delete_response = client.delete(f"/api/assistant/sessions/{session['id']}")
    assert delete_response.status_code == 204

    assert db_session.get(AssistantSession, session["id"]) is None
    assert (
        db_session.query(AssistantMessage)
        .filter(AssistantMessage.session_id == session["id"])
        .count()
        == 0
    )


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
    test_settings.assistant_openai_api_key = None
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
                "usage": {
                    "prompt_tokens": 1000,
                    "completion_tokens": 500,
                    "total_tokens": 1500,
                },
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
    assert response.token_usage.input_tokens == 1000
    assert response.token_usage.output_tokens == 500
    assert response.token_usage.total_tokens == 1500
    assert response.token_usage.estimated_cost_rub > 0


def test_assistant_llm_planner_can_override_followup_intent(
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
                                    "intent": "management_report_summary",
                                    "confidence": 0.93,
                                    "toolQuestion": "какая ТГ самая выгодная в 2025. Follow-up: дай развернутые данные",
                                    "toolNames": ["get_management_report"],
                                    "rationale": "Follow-up inherits previous management report answer.",
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

    plan = plan_route_with_provider(
        test_settings,
        question="дай развернутые данные",
        deterministic_intent="free_chat",
        history=[
            {"role": "user", "text": "какая ТГ самая выгодная в 2025"},
            {
                "role": "assistant",
                "intent": "management_report_summary",
                "summary": "По рентабельности самая выгодная ТГ — 14. Толкатели и амортизаторы.",
                "toolCalls": [{"toolName": "get_management_report"}],
            },
        ],
    )

    assert plan.intent == "management_report_summary"
    assert plan.planner == "openai_compatible"
    assert plan.tool_names == ["get_management_report"]
    assert "какая ТГ" in (plan.tool_question or "")


def test_assistant_llm_planner_can_reject_out_of_scope_questions(
    db_session: Session,
    test_settings,
    monkeypatch,
) -> None:
    calls: list[str] = []

    class FakeHttpResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "usage": {
                    "prompt_tokens": 80,
                    "completion_tokens": 20,
                    "total_tokens": 100,
                },
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "intent": "unsupported_or_ambiguous",
                                    "confidence": 0.98,
                                    "toolQuestion": "Расскажи анекдот про программиста",
                                    "toolNames": [],
                                    "rationale": "Вопрос не связан с рабочими данными MAGAMAX.",
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ],
            }

    class FakeHttpClient:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            pass

        def __enter__(self) -> "FakeHttpClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001, ANN002, ANN003
            return None

        def post(self, *args, **kwargs) -> FakeHttpResponse:  # noqa: ANN002, ANN003
            calls.append("planner")
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
        payload=AssistantQueryRequest(text="Расскажи анекдот про программиста"),
        created_by_id="user_admin",
    )

    assert response.intent == "unsupported_or_ambiguous"
    assert response.status == "unsupported"
    assert response.provider == "deterministic"
    assert calls == ["planner"]
    assert response.token_usage.total_tokens == 100


def test_assistant_llm_planner_can_rescue_domain_question_from_deterministic_unsupported(
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
                                    "intent": "management_report_summary",
                                    "confidence": 0.91,
                                    "toolQuestion": "какая группа принесла максимум маржи в отчете 2025",
                                    "toolNames": ["get_management_report"],
                                    "rationale": "Запрос про управленческий отчёт MAGAMAX и расчёт заработка.",
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ],
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

    plan = plan_route_with_provider(
        test_settings,
        question="какая группа дала максимум денег",
        deterministic_intent="unsupported_or_ambiguous",
        history=[],
    )

    assert plan.intent == "management_report_summary"
    assert plan.tool_names == ["get_management_report"]
    assert "2025" in (plan.tool_question or "")
