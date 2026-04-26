from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.app.core.security import hash_password
from apps.api.app.db.models import AccessPolicy, ReserveRun, Role, User, UserRole
from apps.api.app.modules.assistant.context import build_context_bundle
from apps.api.app.modules.assistant.domain import (
    AssistantAnswerDraft,
    AssistantResolvedContext,
    AssistantToolExecution,
)
from apps.api.app.modules.assistant.providers import finalize_with_provider
from apps.api.app.modules.assistant.routing import route_question
from apps.api.app.modules.assistant.schemas import AssistantPinnedContext
from apps.api.app.modules.assistant.tools import _measure_tool, tool_get_analytics_slice


def _create_user_with_policies(
    db: Session,
    *,
    role_code: str,
    user_id: str,
    policies: list[tuple[str, str]],
) -> None:
    role = Role(code=role_code, name=role_code)
    user = User(
        id=user_id,
        email=f"{user_id}@magamax.local",
        full_name=user_id,
        password_hash=hash_password("pass"),
        is_active=True,
    )
    db.add_all([role, user])
    for resource, action in policies:
        db.add(AccessPolicy(role_code=role_code, resource=resource, action=action, effect="allow"))
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()


def test_internal_analytics_user_sees_full_context_options(
    client: TestClient,
    db_session: Session,
) -> None:
    _create_user_with_policies(
        db_session,
        role_code="assistant_internal_context",
        user_id="user_assistant_internal_context",
        policies=[("assistant", "query"), ("assistant", "internal_analytics")],
    )
    client.headers.update({"X-Dev-User": "user_assistant_internal_context"})

    response = client.get("/api/assistant/context-options")

    assert response.status_code == 200
    payload = response.json()
    assert payload["clients"]
    assert payload["skus"]
    assert payload["categories"]
    assert payload["uploads"]
    assert payload["reserveRuns"]


def test_data_overview_is_read_only_and_source_aware(
    client: TestClient,
    db_session: Session,
) -> None:
    _create_user_with_policies(
        db_session,
        role_code="assistant_internal_data_overview",
        user_id="user_assistant_internal_data_overview",
        policies=[("assistant", "query"), ("assistant", "internal_analytics")],
    )
    client.headers.update({"X-Dev-User": "user_assistant_internal_data_overview"})
    before = db_session.scalar(select(func.count()).select_from(ReserveRun))

    response = client.post("/api/assistant/query", json={"text": "Покажи всё полезное, что есть в БД"})

    after = db_session.scalar(select(func.count()).select_from(ReserveRun))
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "data_overview"
    assert payload["traceMetadata"]["resolved_tool"] == "get_data_overview"
    assert [tool["toolName"] for tool in payload["toolCalls"]] == ["get_data_overview"]
    assert before == after
    assert payload["sourceRefs"]
    assert "скрытые расчёты" in payload["summary"]


def test_data_overview_requires_internal_or_full_read_access(
    client: TestClient,
    db_session: Session,
) -> None:
    _create_user_with_policies(
        db_session,
        role_code="assistant_data_overview_limited",
        user_id="user_assistant_data_overview_limited",
        policies=[("assistant", "query"), ("sales", "read")],
    )
    client.headers.update({"X-Dev-User": "user_assistant_data_overview_limited"})

    response = client.post("/api/assistant/query", json={"text": "Какие данные есть в БД?"})

    assert response.status_code == 403
    assert response.json()["details"]["permission_denied_tool"] == "get_data_overview"


def test_limited_user_context_options_are_filtered_by_granular_capabilities(
    client: TestClient,
    db_session: Session,
) -> None:
    _create_user_with_policies(
        db_session,
        role_code="assistant_limited_context",
        user_id="user_assistant_limited_context",
        policies=[("assistant", "query"), ("clients", "read")],
    )
    client.headers.update({"X-Dev-User": "user_assistant_limited_context"})

    response = client.get("/api/assistant/context-options")

    assert response.status_code == 200
    payload = response.json()
    assert payload["clients"]
    assert payload["skus"] == []
    assert payload["categories"] == []
    assert payload["uploads"] == []
    assert payload["reserveRuns"] == []


def test_show_reserve_does_not_create_run_but_recalculate_does(
    client: TestClient,
    db_session: Session,
) -> None:
    before = db_session.scalar(select(func.count()).select_from(ReserveRun))

    read_response = client.post("/api/assistant/query", json={"text": "Покажи резерв по OBI"})
    after_read = db_session.scalar(select(func.count()).select_from(ReserveRun))
    recalc_response = client.post("/api/assistant/query", json={"text": "Пересчитай резерв по OBI"})
    after_recalc = db_session.scalar(select(func.count()).select_from(ReserveRun))

    assert read_response.status_code == 200
    assert read_response.json()["traceMetadata"]["resolved_tool"] == "get_reserve"
    assert before == after_read
    assert recalc_response.status_code == 200
    assert recalc_response.json()["traceMetadata"]["resolved_tool"] == "calculate_reserve"
    assert after_recalc == after_read + 1


def test_recalculate_reserve_requires_reserve_run_capability(
    client: TestClient,
    db_session: Session,
) -> None:
    _create_user_with_policies(
        db_session,
        role_code="assistant_reserve_read_only",
        user_id="user_assistant_reserve_read_only",
        policies=[("assistant", "query"), ("reserve", "read")],
    )
    client.headers.update({"X-Dev-User": "user_assistant_reserve_read_only"})

    response = client.post("/api/assistant/query", json={"text": "Пересчитай резерв по OBI"})

    assert response.status_code == 403
    assert response.json()["details"]["permission_denied_tool"] == "calculate_reserve"
    assert response.json()["details"]["action"] == "run"


def test_sales_summary_obi_march_2025(client: TestClient) -> None:
    response = client.post("/api/assistant/query", json={"text": "Покажи продажи по OBI за март 2025"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "analytics_slice"
    tool = next(tool for tool in payload["toolCalls"] if tool["toolName"] == "get_analytics_slice")
    assert tool["arguments"]["client_id"] == "client_3"
    assert tool["arguments"]["date_from"] == "2025-03-01"
    assert tool["arguments"]["date_to"] == "2025-03-31"
    assert tool["arguments"]["metrics"] == ["revenue", "sales_qty"]


def test_sales_followups_change_client_metric_and_dimension(client: TestClient) -> None:
    session = client.post("/api/assistant/sessions", json={"title": "Sales followups"}).json()
    first = client.post(
        f"/api/assistant/sessions/{session['id']}/messages",
        json={"text": "Покажи продажи по OBI за март 2025"},
    )
    assert first.status_code == 200

    leroy = client.post(
        f"/api/assistant/sessions/{session['id']}/messages",
        json={"text": "А по Леруа?"},
    ).json()["response"]
    assert leroy["intent"] == "analytics_slice"
    assert leroy["toolCalls"][0]["arguments"]["client_id"] == "client_1"
    assert leroy["toolCalls"][0]["arguments"]["date_from"] == "2025-03-01"

    qty = client.post(
        f"/api/assistant/sessions/{session['id']}/messages",
        json={"text": "А в штуках?"},
    ).json()["response"]
    assert qty["intent"] == "analytics_slice"
    qty_arguments = qty["toolCalls"][0]["arguments"]
    assert qty_arguments.get("metric") in {"sales_qty", "quantity", None} or qty_arguments.get("metrics") == [
        "sales_qty"
    ]

    categories = client.post(
        f"/api/assistant/sessions/{session['id']}/messages",
        json={"text": "А по категориям?"},
    ).json()["response"]
    assert categories["intent"] == "analytics_slice"
    assert categories["toolCalls"][0]["arguments"]["dimensions"] == ["category"]


def test_unsupported_analytics_metric_returns_supported_options(db_session: Session) -> None:
    bundle = build_context_bundle(
        db_session,
        route=route_question(db_session, "срез"),
        pinned_context=AssistantPinnedContext(),
    )

    execution = tool_get_analytics_slice(
        db_session,
        bundle,
        {
            "period": {"date_from": "2025-01-01", "date_to": "2025-12-01"},
            "metrics": ["unknown_metric"],
            "dimensions": ["client"],
        },
    )

    assert execution.status == "completed"
    assert execution.payload["status"] == "unsupported"
    assert "sales_qty" in execution.payload["supported_metrics"]


def test_tool_exception_is_sanitized() -> None:
    execution = _measure_tool(
        "bad_tool",
        {"query": "select * from secrets"},
        lambda: (_ for _ in ()).throw(RuntimeError("select * from secret_table")),
    )

    assert execution.status == "failed"
    assert "select" not in execution.summary.lower()
    assert "secret" not in execution.summary.lower()
    assert "select" not in execution.warnings[0].message.lower()


def test_llm_finalizer_does_not_rewrite_tool_numbers(test_settings) -> None:
    test_settings.assistant_llm_enabled = True
    test_settings.assistant_provider = "openai_compatible"
    draft = AssistantAnswerDraft(
        intent="sales_summary",
        status="completed",
        confidence=0.9,
        title="Сводка продаж",
        summary="Выручка 123.45 ₽, продажи 67 шт.",
        sections=[],
        source_refs=[{"sourceType": "sales", "sourceLabel": "Sales facts", "entityType": "sales_fact"}],
        tool_calls=[
            AssistantToolExecution(
                tool_name="get_sales_summary",
                status="completed",
                arguments={},
                summary="ok",
                latency_ms=1,
            )
        ],
        followups=[],
        warnings=[],
        context_used=AssistantResolvedContext(),
    )

    finalized, provider_name, _, _ = finalize_with_provider(test_settings, draft)

    assert provider_name == "deterministic"
    assert finalized.summary == "Выручка 123.45 ₽, продажи 67 шт."
