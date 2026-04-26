from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from apps.api.app.db.models import AssistantMessage, AssistantSession


def _create_portfolio_reserve_run(client: TestClient) -> str:
    response = client.post(
        "/api/reserve/calculate",
        headers={"X-Dev-User": "user_admin"},
        json={
            "include_inbound": True,
            "inbound_statuses_to_count": ["confirmed"],
            "demand_strategy": "weighted_recent_average",
            "horizon_days": 60,
        },
    )
    assert response.status_code == 200
    return response.json()["run"]["id"]


@pytest.mark.parametrize(
    ("path", "method"),
    [
        ("/api/dashboard/summary", "get"),
        ("/api/dashboard/overview", "get"),
        ("/api/catalog/skus", "get"),
        ("/api/catalog/skus/sku_1/reserve-summary", "get"),
        ("/api/clients/diy", "get"),
        ("/api/sales/monthly", "get"),
        ("/api/stock/coverage", "get"),
        ("/api/stock/potential-stockout", "get"),
        ("/api/inbound/timeline", "get"),
        ("/api/reserve/runs", "get"),
        ("/api/uploads/files", "get"),
        ("/api/uploads/batches", "get"),
        ("/api/mapping/templates", "get"),
        ("/api/mapping/aliases/skus", "get"),
        ("/api/quality/issues", "get"),
        ("/api/assistant/capabilities", "get"),
        ("/api/assistant/prompts/suggestions", "get"),
        ("/api/assistant/context-options", "get"),
        ("/api/exports/jobs", "get"),
        ("/api/admin/users", "get"),
        ("/api/admin/system/freshness", "get"),
    ],
)
def test_protected_read_endpoints_require_authenticated_user(
    anonymous_client: TestClient, path: str, method: str
) -> None:
    response = getattr(anonymous_client, method)(path)
    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


@pytest.mark.parametrize("path", ["/api/health/live", "/api/health/ready"])
def test_intentionally_open_health_routes_remain_anonymous(anonymous_client: TestClient, path: str) -> None:
    response = anonymous_client.get(path)
    assert response.status_code in {200, 503}
    assert response.status_code != 401


def test_dashboard_summary_endpoint(client: TestClient) -> None:
    _create_portfolio_reserve_run(client)
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_skus_tracked"] >= 6
    assert payload["positions_at_risk"] >= 0
    assert "assistant_api_cost_rub" in payload


def test_dashboard_summary_includes_assistant_api_cost(
    client: TestClient,
    db_session: Session,
) -> None:
    _create_portfolio_reserve_run(client)
    session = AssistantSession(created_by_id="user_admin", title="Cost check")
    db_session.add(session)
    db_session.flush()
    db_session.add(
        AssistantMessage(
            session_id=session.id,
            created_by_id="user_admin",
            role="assistant",
            message_text="answer",
            response_payload={
                "tokenUsage": {
                    "inputTokens": 1000,
                    "outputTokens": 3000,
                    "totalTokens": 4000,
                    "estimatedCostUsd": 0.04,
                    "estimatedCostRub": 12.0,
                }
            },
        )
    )
    db_session.commit()

    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    assert response.json()["assistant_api_cost_rub"] == 12.0


@pytest.mark.parametrize(
    ("user_id", "path"),
    [
        ("user_viewer", "/api/exports/jobs"),
        ("user_viewer", "/api/admin/users"),
        ("user_analyst", "/api/admin/users"),
        ("user_operator", "/api/sales/monthly"),
    ],
)
def test_low_role_access_is_denied_for_insufficient_capabilities(
    client: TestClient,
    user_id: str,
    path: str,
) -> None:
    response = client.get(path, headers={"X-Dev-User": user_id})
    assert response.status_code == 403
    payload = response.json()
    assert payload["code"] == "permission_denied"
    assert "resource" in payload["details"]
    assert "action" in payload["details"]


@pytest.mark.parametrize(
    ("user_id", "path"),
    [
        ("user_viewer", "/api/dashboard/summary"),
        ("user_viewer", "/api/catalog/skus"),
        ("user_viewer", "/api/clients/diy"),
        ("user_viewer", "/api/reserve/runs"),
        ("user_viewer", "/api/uploads/files"),
        ("user_viewer", "/api/mapping/templates"),
        ("user_viewer", "/api/stock/potential-stockout"),
        ("user_viewer", "/api/inbound/timeline"),
        ("user_viewer", "/api/assistant/capabilities"),
        ("user_analyst", "/api/sales/monthly"),
        ("user_operator", "/api/uploads/files"),
        ("user_operator", "/api/exports/jobs"),
        ("user_operator", "/api/admin/users"),
    ],
)
def test_allowed_roles_can_access_read_surfaces(
    client: TestClient,
    user_id: str,
    path: str,
) -> None:
    if path == "/api/dashboard/summary":
        _create_portfolio_reserve_run(client)
    response = client.get(path, headers={"X-Dev-User": user_id})
    assert response.status_code == 200


def test_reserve_calculate_persists_run_for_one_client_and_selected_skus(client: TestClient) -> None:
    payload = {
        "client_ids": ["client_2"],
        "sku_ids": ["sku_1", "sku_3"],
        "reserve_months": 3,
        "safety_factor": 1.1,
        "demand_strategy": "weighted_recent_average",
        "horizon_days": 60,
    }
    response = client.post(
        "/api/reserve/calculate",
        headers={"X-Dev-User": "user_admin"},
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    run_id = body["run"]["id"]

    assert body["run"]["row_count"] == 2
    assert {row["client_id"] for row in body["rows"]} == {"client_2"}
    assert {row["sku_id"] for row in body["rows"]} == {"sku_1", "sku_3"}

    run_response = client.get(f"/api/reserve/runs/{run_id}")
    assert run_response.status_code == 200
    assert run_response.json()["scope_type"] == "client_sku_list"

    rows_response = client.get(f"/api/reserve/runs/{run_id}/rows")
    assert rows_response.status_code == 200
    assert len(rows_response.json()) == 2

    summary_response = client.get(f"/api/reserve/runs/{run_id}/summary")
    assert summary_response.status_code == 200
    assert summary_response.json()["totals"]["positions"] == 2

    second_response = client.post(
        "/api/reserve/calculate",
        headers={"X-Dev-User": "user_admin"},
        json=payload,
    )
    assert second_response.status_code == 200
    assert second_response.json()["run"]["id"] != run_id


def test_diy_client_summary_endpoints(client: TestClient) -> None:
    _create_portfolio_reserve_run(client)
    list_response = client.get("/api/clients/diy")
    assert list_response.status_code == 200
    clients = list_response.json()
    assert len(clients) >= 3
    assert "warning_positions" in clients[0]

    detail_response = client.get("/api/clients/diy/client_1/reserve-summary")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == "client_1"
    assert detail["policy_active"] is True


def test_sku_and_stock_phase3_endpoints(client: TestClient) -> None:
    _create_portfolio_reserve_run(client)
    sku_response = client.get("/api/catalog/skus/sku_1/reserve-summary")
    assert sku_response.status_code == 200
    sku_payload = sku_response.json()
    assert sku_payload["sku_id"] == "sku_1"
    assert sku_payload["affected_clients_count"] >= 1

    stock_response = client.get("/api/stock/potential-stockout")
    assert stock_response.status_code == 200
    stock_payload = stock_response.json()
    assert len(stock_payload) >= 1
    assert {"client_id", "sku_id", "status"}.issubset(stock_payload[0].keys())
