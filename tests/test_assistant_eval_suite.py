from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.app.db.models import (
    InboundDelivery,
    ManagementReportMetric,
    ReserveRow,
    ReserveRun,
    SalesFact,
    StockSnapshot,
)

EVAL_CASES_PATH = Path(__file__).with_name("assistant_eval_cases.yaml")


def _load_cases() -> list[dict[str, Any]]:
    with EVAL_CASES_PATH.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    assert isinstance(payload, list)
    return payload


def detect_eval_capabilities(db: Session) -> set[str]:
    capabilities: set[str] = set()
    if db.scalar(select(func.count()).select_from(ManagementReportMetric)):
        capabilities.add("management_report")
        metric_names = {
            str(name or "").lower()
            for name in db.scalars(select(ManagementReportMetric.metric_name).distinct())
        }
        if metric_names.intersection({"profitability", "profitability_pct"}):
            capabilities.add("profitability")
        if metric_names.intersection({"margin", "profit", "gross_margin", "gross_profit"}):
            capabilities.add("margin")
        if metric_names.intersection({"overdue_receivables", "pdz", "пдз"}):
            capabilities.add("pdz")
    if db.scalar(
        select(func.count())
        .select_from(SalesFact)
        .where(SalesFact.period_month >= date(2024, 1, 1), SalesFact.period_month <= date(2024, 12, 31))
    ):
        capabilities.add("sales_2024")
    if db.scalar(
        select(func.count())
        .select_from(SalesFact)
        .where(SalesFact.period_month >= date(2025, 1, 1), SalesFact.period_month <= date(2025, 12, 31))
    ):
        capabilities.add("sales_2025")
    if db.scalar(select(func.count()).select_from(StockSnapshot)):
        capabilities.add("stock")
    if db.scalar(select(func.count()).select_from(ReserveRun)) or db.scalar(
        select(func.count()).select_from(ReserveRow)
    ):
        capabilities.add("reserve")
    if db.scalar(select(func.count()).select_from(InboundDelivery)):
        capabilities.add("inbound")
    return capabilities


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


def _case_messages(case: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(case.get("conversation"), list):
        return [
            {"text": str(item.get("message") or item.get("text") or ""), "expect": item.get("expect") or {}}
            for item in case["conversation"]
        ]
    return [{"text": str(item.get("text") or ""), "expect": {}} for item in case["messages"]]


def _case_group(case: dict[str, Any]) -> str:
    if case.get("group"):
        return str(case["group"])
    case_id = str(case["id"])
    if case_id in {"help_no_refusal", "data_overview"}:
        return "A"
    if "year" in case_id or "2025" in case_id or case_id == "compare_sales_years":
        return "B"
    if case_id.startswith(("sales", "revenue", "top_", "monthly", "stock_free")):
        return "C"
    if case_id.startswith("followup"):
        return "D"
    if any(token in case_id for token in ("declined", "worst", "drop", "margin")):
        return "E"
    if case_id.startswith(("reserve", "stock_", "show_reserve")):
        return "F"
    if case_id.startswith("inbound"):
        return "G"
    if case_id.startswith("management"):
        return "H"
    if case_id.startswith(("clarify", "clarification", "ambiguous")) or case_id.endswith(
        "_no_refusal"
    ):
        return "I"
    if any(token in case_id for token in ("no_data", "nonexistent", "unsupported", "scope", "external", "weather")):
        return "J"
    return "Z"


def _assert_any(response: dict[str, Any], assertions: list[str], case_id: str) -> None:
    checks = {
        "missingFields_not_empty": bool(response.get("missingFields")),
        "followupQuestion_not_null": bool(response.get("summary")),
        "toolCalls_not_empty": bool(response.get("toolCalls")),
        "suggestedChips_not_empty": bool(response.get("suggestedChips")),
    }
    assert any(checks.get(item, False) for item in assertions), case_id


def _assert_query_plan(actual: dict[str, Any], expected: dict[str, Any], case_id: str) -> None:
    if expected_period := expected.get("period"):
        assert str(actual.get("date_from") or "").startswith(str(expected_period)), case_id
    if expected_client := expected.get("client_any"):
        haystack = json.dumps(actual, ensure_ascii=False).lower()
        assert any(str(item).lower() in haystack for item in expected_client), case_id
    if expected_limit := expected.get("limit"):
        assert actual.get("limit") == expected_limit, case_id
    if expected_current := expected.get("current_period"):
        assert actual.get("current_period") == expected_current, case_id
    if expected_previous := expected.get("previous_period"):
        assert actual.get("previous_period") == expected_previous, case_id


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

    assert len(cases) >= 50
    ids = {case["id"] for case in cases}
    assert len(ids) == len(cases)
    assert {
        "sales_by_client_month",
        "followup_change_client",
        "compare_sales_years",
        "data_overview",
    }.issubset(ids)
    assert {"H", "J"}.issubset({_case_group(case) for case in cases})


def test_assistant_eval_suite(client: TestClient, db_session: Session) -> None:
    cases = _load_cases()
    capabilities = detect_eval_capabilities(db_session)
    results: list[tuple[str, str, str]] = []
    for case in cases:
        case_id = str(case["id"])
        group = _case_group(case)
        required = set(case.get("requires_capability") or [])
        if required and not required.issubset(capabilities) and case.get("skip_if_missing"):
            results.append((case_id, group, "skipped"))
            continue
        session = client.post(
            "/api/assistant/sessions", json={"title": f"eval:{case_id}"}
        ).json()
        expect = case.get("expect") or {}
        must_not_create = list(expect.get("must_not_create") or [])
        expected_creates = list(expect.get("creates") or [])
        guarded_entities = list(dict.fromkeys([*must_not_create, *expected_creates]))
        before_counts = {entity: _count_entity(db_session, entity) for entity in guarded_entities}
        first_response: dict[str, Any] | None = None
        pending_seen: str | None = None
        final_response: dict[str, Any] | None = None
        failed_reason: str | None = None

        try:
            for index, message in enumerate(_case_messages(case)):
                result = client.post(
                    f"/api/assistant/sessions/{session['id']}/messages",
                    json={"text": message["text"]},
                )
                assert (
                    result.status_code == 200
                ), f"{case_id} failed with {result.status_code}: {result.text}"
                response = result.json()["response"]
                step_expect = message.get("expect") or {}
                if step_expect:
                    _assert_response_expect(response, step_expect, case_id, pending_seen)
                if index == 0:
                    first_response = response
                if response.get("pendingIntent"):
                    pending_seen = response["pendingIntent"]
                final_response = response

            assert final_response is not None
            _assert_response_expect(final_response, expect, case_id, pending_seen)
            _assert_preserved_changed(
                first_response=first_response,
                final_response=final_response,
                preserved=list(expect.get("preserved") or expect.get("assert_preserves") or []),
                changed=list(expect.get("changed") or []),
                expected_tool=expect.get("tool"),
            )

            for entity in must_not_create:
                before = before_counts[entity]
                assert _count_entity(db_session, entity) == before, case_id
            for entity in expected_creates:
                before = before_counts[entity]
                assert _count_entity(db_session, entity) > before, case_id
            if "reserve_run" in list(expect.get("creates") or []):
                assert _count_entity(db_session, "reserve_run") > before_counts.get(
                    "reserve_run", 0
                )
        except AssertionError as exc:
            failed_reason = str(exc) or "assertion failed"
        results.append((case_id, group, failed_reason or "passed"))

    failed = [item for item in results if item[2] not in {"passed", "skipped"}]
    non_skipped = [item for item in results if item[2] != "skipped"]
    passed = [item for item in results if item[2] == "passed"]
    assert non_skipped, "No non-skipped assistant eval cases executed"
    pass_rate = len(passed) / len(non_skipped)
    critical_groups = {"A", "B", "C", "D", "J"}
    critical_failures = [item for item in failed if item[1] in critical_groups]
    h_failures = [item for item in failed if item[1] == "H"]
    report = {
        "total": len(results),
        "non_skipped": len(non_skipped),
        "passed": len(passed),
        "skipped": len(results) - len(non_skipped),
        "failed": failed,
    }
    assert pass_rate >= 0.80, json.dumps(report, ensure_ascii=False, indent=2)
    assert not critical_failures, json.dumps(report, ensure_ascii=False, indent=2)
    assert not h_failures, json.dumps(report, ensure_ascii=False, indent=2)


def _assert_response_expect(
    response: dict[str, Any],
    expect: dict[str, Any],
    case_id: str,
    pending_seen: str | None,
) -> None:
    if expected_intent := expect.get("intent"):
        assert response["intent"] == expected_intent, case_id
    if expected_intents := expect.get("intent_in"):
        assert response["intent"] in expected_intents, case_id
    if expected_status := expect.get("status"):
        assert response["status"] == expected_status, case_id
    if expected_statuses := expect.get("status_in"):
        assert response["status"] in expected_statuses, case_id
    if forbidden_statuses := expect.get("status_not_in"):
        assert response["status"] not in forbidden_statuses, case_id
    if expected_type := expect.get("type"):
        assert response["type"] == expected_type, case_id
    if expected_tool := expect.get("tool"):
        tool_names = [tool["toolName"] for tool in response.get("toolCalls", [])]
        assert expected_tool in tool_names, f"{case_id} tool_names={tool_names}"
    if expect.get("source_refs"):
        assert response.get("sourceRefs"), case_id
    if expected_missing := expect.get("missing_fields"):
        missing_names = {field["name"] for field in response.get("missingFields", [])}
        assert set(expected_missing).issubset(missing_names), case_id
    if expected_pending := expect.get("pending_intent"):
        assert response.get("pendingIntent") == expected_pending, case_id
    if expected_pending_seen := expect.get("pending_was"):
        assert pending_seen == expected_pending_seen, case_id
    if expected_tool_args := expect.get("tool_args"):
        _assert_tool_args(_tool_args(response, expect.get("tool")), expected_tool_args)
    if query_plan := expect.get("assert_query_plan"):
        _assert_query_plan(_tool_args(response, expect.get("tool")), query_plan, case_id)
    if metrics_any := expect.get("assert_metrics_any"):
        actual = _tool_args(response, expect.get("tool")).get("metrics") or []
        assert set(actual).intersection(set(metrics_any)), case_id
    if metrics := expect.get("assert_metrics"):
        assert _tool_args(response, expect.get("tool")).get("metrics") == metrics, case_id
    if dimensions := expect.get("assert_dimensions_include"):
        actual = _tool_args(response, expect.get("tool")).get("dimensions") or []
        assert set(dimensions).issubset(set(actual)), case_id
    if dimensions_any := expect.get("assert_dimensions_include_any"):
        actual = _tool_args(response, expect.get("tool")).get("dimensions") or []
        assert set(dimensions_any).intersection(set(actual)), case_id
    if expected_current := expect.get("current_period"):
        assert _tool_args(response, expect.get("tool")).get("current_period") == expected_current
    if expected_previous := expect.get("previous_period"):
        assert _tool_args(response, expect.get("tool")).get("previous_period") == expected_previous
    if any_assertions := expect.get("assert_any"):
        _assert_any(response, list(any_assertions), case_id)
    text = _response_text(response)
    for phrase in expect.get("must_include") or []:
        assert str(phrase).lower() in text, case_id
    if phrases := expect.get("must_include_any"):
        assert any(str(phrase).lower() in text for phrase in phrases), case_id
    for phrase in expect.get("must_not_include") or []:
        assert str(phrase).lower() not in text, case_id
