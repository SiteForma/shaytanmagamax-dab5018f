from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

FORBIDDEN_REFUSAL_PHRASES = (
    "я могу помочь только",
    "запрос вне контура",
    "не относится к рабочим данным",
)


def _ask(client: TestClient, text: str) -> dict[str, Any]:
    response = client.post("/api/assistant/query", json={"text": text})
    assert response.status_code == 200, response.text
    return response.json()


def _response_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def _assert_no_canned_refusal(payload: dict[str, Any]) -> None:
    text = _response_text(payload)
    for phrase in FORBIDDEN_REFUSAL_PHRASES:
        assert phrase not in text


def _assert_business_not_unsupported(payload: dict[str, Any]) -> None:
    assert payload["intent"] != "unsupported_or_ambiguous"
    assert payload["status"] != "unsupported"
    _assert_no_canned_refusal(payload)


def test_help_is_not_unsupported(client: TestClient) -> None:
    payload = _ask(client, "помоги")

    assert payload["intent"] == "free_chat"
    assert payload["status"] == "completed"
    _assert_no_canned_refusal(payload)
    text = _response_text(payload)
    assert "продажи" in text
    assert "резерв" in text
    assert "sku" in text


def test_what_can_you_do_is_help(client: TestClient) -> None:
    payload = _ask(client, "что ты умеешь?")

    assert payload["intent"] == "free_chat"
    assert payload["status"] == "completed"
    _assert_no_canned_refusal(payload)


def test_year_close_question_is_business(client: TestClient) -> None:
    payload = _ask(client, "как в целом 2025 год закрыли?")

    assert payload["intent"] in {"management_report_summary", "analytics_slice"}
    assert payload["status"] in {"completed", "partial", "needs_clarification"}
    _assert_no_canned_refusal(payload)


def test_short_year_question_is_business(client: TestClient) -> None:
    payload = _ask(client, "что по 2025?")

    assert payload["intent"] in {"management_report_summary", "analytics_slice"}
    assert payload["status"] != "unsupported"
    _assert_no_canned_refusal(payload)


def test_month_performance_question_is_business(client: TestClient) -> None:
    payload = _ask(client, "как отработали март?")

    assert payload["intent"] in {"analytics_slice", "sales_summary"}
    assert payload["status"] in {"completed", "partial", "needs_clarification"}
    _assert_no_canned_refusal(payload)


def test_problematic_question_is_business(client: TestClient) -> None:
    payload = _ask(client, "покажи проблемные")

    assert payload["intent"] in {"stock_risk_summary", "reserve_calculation", "analytics_slice"}
    assert payload["status"] in {"completed", "partial", "needs_clarification"}
    _assert_no_canned_refusal(payload)


def test_need_to_order_question_is_business(client: TestClient) -> None:
    payload = _ask(client, "что надо заказать?")

    assert payload["intent"] in {"stock_risk_summary", "reserve_calculation", "analytics_slice"}
    assert payload["status"] in {"completed", "partial", "needs_clarification"}
    _assert_no_canned_refusal(payload)


def test_external_question_still_unsupported(client: TestClient) -> None:
    payload = _ask(client, "кто написал Евгения Онегина?")

    assert payload["intent"] == "unsupported_or_ambiguous"
    assert payload["status"] == "unsupported"


def test_weather_still_unsupported(client: TestClient) -> None:
    payload = _ask(client, "какая погода завтра?")

    assert payload["intent"] == "unsupported_or_ambiguous"
    assert payload["status"] == "unsupported"


def test_no_refusal_phrase_for_business_questions(client: TestClient) -> None:
    for question in (
        "как закрыли 2025?",
        "что по продажам?",
        "где просели?",
        "помоги",
    ):
        payload = _ask(client, question)
        _assert_business_not_unsupported(payload)
