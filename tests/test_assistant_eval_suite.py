from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.app.db.models import ReserveRun

EVAL_CASES_PATH = Path(__file__).with_name("assistant_eval_cases.yaml")


def _load_cases() -> list[dict[str, Any]]:
    with EVAL_CASES_PATH.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    assert isinstance(payload, list)
    return payload


def _count_entity(db: Session, entity_name: str) -> int:
    if entity_name == "reserve_run":
        return int(db.scalar(select(func.count()).select_from(ReserveRun)) or 0)
    raise AssertionError(f"Unsupported eval mutation guard: {entity_name}")


def _response_text(response: dict[str, Any]) -> str:
    return json.dumps(response, ensure_ascii=False, sort_keys=True).lower()


def _tool_args(response: dict[str, Any], tool_name: str | None = None) -> dict[str, Any]:
    tool_calls = response.get("toolCalls") or []
    assert isinstance(tool_calls, list)
    if not tool_calls:
        return {}
    if tool_name:
        for tool_call in tool_calls:
            if tool_call.get("toolName") == tool_name:
                return dict(tool_call.get("arguments") or {})
    return dict(tool_calls[0].get("arguments") or {})


def _assert_tool_args(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    for key, expected_value in expected.items():
        assert key in actual, f"Expected tool arg {key}; actual={actual}"
        assert actual[key] == expected_value


def _assert_preserved_changed(
    *,
    first_response: dict[str, Any] | None,
    final_response: dict[str, Any],
    preserved: list[str],
    changed: list[str],
    expected_tool: str | None,
) -> None:
    if first_response is None:
        return
    first_args = _tool_args(first_response, expected_tool)
    final_args = _tool_args(final_response, expected_tool)
    if "period" in preserved:
        assert first_args.get("date_from") == final_args.get("date_from")
        assert first_args.get("date_to") == final_args.get("date_to")
    if "metric" in preserved:
        assert (first_args.get("metrics") or first_args.get("metric")) == (
            final_args.get("metrics") or final_args.get("metric")
        )
    if "client" in changed:
        assert first_args.get("client_id") != final_args.get("client_id")


def test_assistant_eval_suite_has_required_coverage() -> None:
    cases = _load_cases()

    assert len(cases) >= 40
    ids = {case["id"] for case in cases}
    assert len(ids) == len(cases)
    assert {"sales_by_client_month", "followup_change_client", "compare_sales_years", "data_overview"}.issubset(ids)


def test_assistant_eval_suite(client: TestClient, db_session: Session) -> None:
    cases = _load_cases()

    for case in cases:
        session = client.post("/api/assistant/sessions", json={"title": f"eval:{case['id']}"}).json()
        expect = case.get("expect") or {}
        must_not_create = list(expect.get("must_not_create") or [])
        expected_creates = list(expect.get("creates") or [])
        guarded_entities = list(dict.fromkeys([*must_not_create, *expected_creates]))
        before_counts = {entity: _count_entity(db_session, entity) for entity in guarded_entities}
        first_response: dict[str, Any] | None = None
        pending_seen: str | None = None
        final_response: dict[str, Any] | None = None

        for index, message in enumerate(case["messages"]):
            result = client.post(
                f"/api/assistant/sessions/{session['id']}/messages",
                json={"text": message["text"]},
            )
            assert result.status_code == 200, f"{case['id']} failed with {result.status_code}: {result.text}"
            response = result.json()["response"]
            if index == 0:
                first_response = response
            if response.get("pendingIntent"):
                pending_seen = response["pendingIntent"]
            final_response = response

        assert final_response is not None
        if expected_intent := expect.get("intent"):
            assert final_response["intent"] == expected_intent, case["id"]
        if expected_status := expect.get("status"):
            assert final_response["status"] == expected_status, case["id"]
        if expected_type := expect.get("type"):
            assert final_response["type"] == expected_type, case["id"]
        if expected_tool := expect.get("tool"):
            tool_names = [tool["toolName"] for tool in final_response.get("toolCalls", [])]
            assert expected_tool in tool_names, f"{case['id']} tool_names={tool_names}"
        if expect.get("source_refs"):
            assert final_response.get("sourceRefs"), case["id"]
        if expected_missing := expect.get("missing_fields"):
            missing_names = {field["name"] for field in final_response.get("missingFields", [])}
            assert set(expected_missing).issubset(missing_names), case["id"]
        if expected_pending := expect.get("pending_intent"):
            assert final_response.get("pendingIntent") == expected_pending, case["id"]
        if expected_pending_seen := expect.get("pending_was"):
            assert pending_seen == expected_pending_seen, case["id"]
        if expected_tool_args := expect.get("tool_args"):
            _assert_tool_args(_tool_args(final_response, expect.get("tool")), expected_tool_args)
        if expected_current := expect.get("current_period"):
            assert _tool_args(final_response, expect.get("tool")).get("current_period") == expected_current
        if expected_previous := expect.get("previous_period"):
            assert _tool_args(final_response, expect.get("tool")).get("previous_period") == expected_previous

        text = _response_text(final_response)
        for phrase in expect.get("must_include") or []:
            assert str(phrase).lower() in text, case["id"]
        for phrase in expect.get("must_not_include") or []:
            assert str(phrase).lower() not in text, case["id"]

        _assert_preserved_changed(
            first_response=first_response,
            final_response=final_response,
            preserved=list(expect.get("preserved") or []),
            changed=list(expect.get("changed") or []),
            expected_tool=expect.get("tool"),
        )

        for entity in must_not_create:
            before = before_counts[entity]
            assert _count_entity(db_session, entity) == before, case["id"]
        for entity in expected_creates:
            before = before_counts[entity]
            assert _count_entity(db_session, entity) > before, case["id"]
        if "reserve_run" in list(expect.get("creates") or []):
            assert _count_entity(db_session, "reserve_run") > before_counts.get("reserve_run", 0)
