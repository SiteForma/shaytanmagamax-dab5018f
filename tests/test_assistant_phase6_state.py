from __future__ import annotations

from apps.api.app.modules.assistant.state import (
    AssistantMissingField,
    derive_state_from_history,
    merge_state,
    resolve_followup_from_state,
)


def test_derive_state_from_history_keeps_last_entities_and_pending_fields() -> None:
    state = derive_state_from_history(
        [
            {
                "role": "assistant",
                "intent": "reserve_calculation",
                "status": "completed",
                "toolCalls": [
                    {
                        "toolName": "calculate_reserve",
                        "arguments": {"client_id": "client_3", "sku_ids": ["sku_1"]},
                    }
                ],
                "sourceRefs": [
                    {
                        "sourceType": "reserve_engine",
                        "entityType": "reserve_run",
                        "entityId": "run_1",
                        "role": "primary",
                    }
                ],
            },
            {
                "role": "assistant",
                "intent": "sales_summary",
                "status": "needs_clarification",
                "type": "clarification",
                "missingFields": [{"name": "date_from", "question": "За какой период?"}],
            },
        ]
    )

    assert state.last_intent == "reserve_calculation"
    assert state.last_tool_name == "calculate_reserve"
    assert state.last_entities.client_id == "client_3"
    assert state.last_entities.sku_ids == ["sku_1"]
    assert state.last_entities.reserve_run_id == "run_1"
    assert state.pending_intent == "sales_summary"
    assert [field.name for field in state.missing_fields] == ["date_from"]


def test_resolve_followup_from_state_reuses_previous_reserve_context() -> None:
    state = derive_state_from_history(
        [
            {
                "role": "assistant",
                "intent": "reserve_calculation",
                "status": "completed",
                "toolCalls": [
                    {
                        "toolName": "calculate_reserve",
                        "arguments": {"client_id": "client_3", "sku_ids": ["sku_1"]},
                    }
                ],
                "sourceRefs": [
                    {
                        "sourceType": "reserve_engine",
                        "entityType": "reserve_run",
                        "entityId": "run_1",
                        "role": "primary",
                    }
                ],
            }
        ]
    )

    params = resolve_followup_from_state("Почему такой резерв?", state)

    assert params["client_id"] == "client_3"
    assert params["sku_ids"] == ["sku_1"]
    assert params["reserve_run_id"] == "run_1"
    assert params["_followup_intent"] == "reserve_explanation"


def test_merge_state_records_pending_clarification() -> None:
    state = merge_state(
        derive_state_from_history([]),
        intent="sales_summary",
        missing_fields=[
            AssistantMissingField(
                name="date_from",
                label="период",
                question="За какой период посмотреть продажи?",
            )
        ],
        pending_question="Что с продажами?",
    )

    assert state.pending_intent == "sales_summary"
    assert state.pending_question == "Что с продажами?"
    assert state.missing_fields[0].name == "date_from"
