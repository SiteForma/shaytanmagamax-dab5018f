from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.errors import DomainError
from apps.api.app.core.security import hash_password
from apps.api.app.db.models import AccessPolicy, Role, User, UserRole
from apps.api.app.modules.assistant.permissions import require_assistant_tool_capabilities
from apps.api.app.modules.assistant.registry import get_default_tool_registry


def _create_assistant_only_user(db: Session) -> None:
    role = Role(code="assistant_only", name="Assistant only")
    user = User(
        id="user_assistant_only",
        email="assistant-only@magamax.local",
        full_name="Assistant Only",
        password_hash=hash_password("pass"),
        is_active=True,
    )
    db.add_all(
        [
            role,
            user,
            AccessPolicy(role_code="assistant_only", resource="assistant", action="query", effect="allow"),
        ]
    )
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()


def test_assistant_tool_requires_its_own_capability(db_session: Session) -> None:
    _create_assistant_only_user(db_session)
    user = db_session.scalar(select(User).where(User.id == "user_assistant_only"))
    spec = get_default_tool_registry().lookup("get_stock_coverage")

    with pytest.raises(DomainError) as denied:
        require_assistant_tool_capabilities(user, spec)

    assert denied.value.code == "permission_denied"
    assert denied.value.details == {
        "tool": "get_stock_coverage",
        "permission_denied_tool": "get_stock_coverage",
        "resource": "stock",
        "action": "read",
    }


def test_user_without_stock_read_cannot_use_stock_tool_through_assistant(
    client: TestClient,
    db_session: Session,
) -> None:
    _create_assistant_only_user(db_session)
    client.headers.update({"X-Dev-User": "user_assistant_only"})

    response = client.post("/api/assistant/query", json={"text": "Какие SKU в зоне риска?"})

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"
    assert response.json()["details"]["permission_denied_tool"] == "get_stock_coverage"


def test_user_without_reserve_read_cannot_use_reserve_tool_through_assistant(
    client: TestClient,
    db_session: Session,
) -> None:
    _create_assistant_only_user(db_session)
    client.headers.update({"X-Dev-User": "user_assistant_only"})

    response = client.post("/api/assistant/query", json={"text": "Покажи резерв по OBI"})

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"
    assert response.json()["details"]["permission_denied_tool"] == "get_reserve"
    assert response.json()["details"]["resolved_intent"] == "reserve_calculation"
    assert response.json()["details"]["resolved_tool"] == "get_reserve"


def test_user_without_reports_read_cannot_use_management_report_tool_through_assistant(
    client: TestClient,
    db_session: Session,
) -> None:
    _create_assistant_only_user(db_session)
    client.headers.update({"X-Dev-User": "user_assistant_only"})

    response = client.post("/api/assistant/query", json={"text": "какая ТГ самая выгодная в 2025"})

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"
    assert response.json()["details"]["permission_denied_tool"] == "get_management_report"


def test_user_without_sales_read_cannot_use_sales_tool_through_assistant(
    client: TestClient,
    db_session: Session,
) -> None:
    _create_assistant_only_user(db_session)
    client.headers.update({"X-Dev-User": "user_assistant_only"})

    response = client.post("/api/assistant/query", json={"text": "Что с продажами в 2025?"})

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"
    assert response.json()["details"]["permission_denied_tool"] == "get_analytics_slice"
