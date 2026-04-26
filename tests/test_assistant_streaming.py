from __future__ import annotations

import json

from fastapi.testclient import TestClient


def _events_from_stream(response) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    event_type: str | None = None
    data_lines: list[str] = []

    def flush() -> None:
        nonlocal event_type, data_lines
        if not data_lines:
            event_type = None
            return
        payload = json.loads("\n".join(data_lines))
        payload.setdefault("type", event_type or payload.get("type") or "message")
        events.append(payload)
        event_type = None
        data_lines = []

    for line in response.iter_lines():
        if not line:
            flush()
            continue
        if line.startswith("event:"):
            event_type = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].lstrip())

    flush()
    return events


def test_assistant_message_streams_deltas_and_persists_messages(client: TestClient) -> None:
    session_response = client.post("/api/assistant/sessions", json={"title": "Streaming test"})
    assert session_response.status_code == 200
    session_id = session_response.json()["id"]

    with client.stream(
        "POST",
        f"/api/assistant/sessions/{session_id}/messages/stream",
        json={"text": "Привет, как лучше работать с MAGAMAX?"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = _events_from_stream(response)

    event_types = [event["type"] for event in events]
    assert event_types[0] == "thinking"
    assert "answer_delta" in event_types
    assert event_types[-1] == "done"

    streamed_text = "".join(
        str(event.get("delta", "")) for event in events if event["type"] == "answer_delta"
    )
    final_result = events[-1]["result"]
    assert isinstance(final_result, dict)
    assert streamed_text == final_result["response"]["summary"]

    messages_response = client.get(f"/api/assistant/sessions/{session_id}/messages")
    assert messages_response.status_code == 200
    messages = messages_response.json()
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[-1]["response"]["summary"] == streamed_text


def test_assistant_stream_emits_clarification_event(client: TestClient) -> None:
    session_response = client.post("/api/assistant/sessions", json={"title": "Clarification stream"})
    assert session_response.status_code == 200
    session_id = session_response.json()["id"]

    with client.stream(
        "POST",
        f"/api/assistant/sessions/{session_id}/messages/stream",
        json={"text": "Покажи резерв"},
    ) as response:
        assert response.status_code == 200
        events = _events_from_stream(response)

    clarification = next(event for event in events if event["type"] == "clarification")
    assert clarification["pendingIntent"] == "reserve_calculation"
    assert [field["name"] for field in clarification["missingFields"]] == ["client_id"]
    assert "OBI Россия" in clarification["suggestedChips"]


def test_assistant_stream_emits_tool_events(client: TestClient) -> None:
    session_response = client.post("/api/assistant/sessions", json={"title": "Tool stream"})
    assert session_response.status_code == 200
    session_id = session_response.json()["id"]

    with client.stream(
        "POST",
        f"/api/assistant/sessions/{session_id}/messages/stream",
        json={"text": "Покажи резерв по OBI"},
    ) as response:
        assert response.status_code == 200
        events = _events_from_stream(response)

    event_types = [event["type"] for event in events]
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert any(event.get("toolName") == "calculate_reserve" for event in events)
