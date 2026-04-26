from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from apps.api.app.api.dependencies import get_settings_dependency, require_capability
from apps.api.app.core.config import Settings
from apps.api.app.db.models import User
from apps.api.app.db.session import get_db
from apps.api.app.modules.assistant.schemas import (
    AssistantCapabilitiesResponse,
    AssistantContextOptionsResponse,
    AssistantMessageCreateRequest,
    AssistantMessageResponse,
    AssistantPromptSuggestionsResponse,
    AssistantQueryRequest,
    AssistantResponse,
    AssistantSessionCreateRequest,
    AssistantSessionDetail,
    AssistantSessionMessageResult,
    AssistantSessionSummary,
    AssistantSessionUpdateRequest,
)
from apps.api.app.modules.assistant.service import (
    assistant_query,
    create_assistant_session,
    delete_assistant_session,
    get_assistant_capabilities,
    get_assistant_session_detail,
    get_context_options,
    get_prompt_suggestions,
    list_assistant_messages,
    list_assistant_sessions,
    post_assistant_message,
    stream_assistant_message_events,
    update_assistant_session,
)
from apps.api.app.modules.audit.service import record_audit_event

router = APIRouter(prefix="/assistant", tags=["assistant"])


def _encode_sse_event(event: dict[str, object]) -> bytes:
    event_type = str(event.get("type") or "message")
    payload = dict(event)
    payload["type"] = event_type
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event_type}\ndata: {data}\n\n".encode("utf-8")


@router.post("/sessions", response_model=AssistantSessionSummary)
def create_session_route(
    payload: AssistantSessionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_capability("assistant", "query")),
) -> AssistantSessionSummary:
    session = create_assistant_session(db, payload=payload, current_user=current_user)
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="assistant.session_created",
        target_type="assistant_session",
        target_id=session.id,
        context={"title": session.title},
    )
    db.commit()
    return session


@router.get("/sessions", response_model=list[AssistantSessionSummary])
def list_sessions_route(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_capability("assistant", "query")),
) -> list[AssistantSessionSummary]:
    return list_assistant_sessions(db, current_user=current_user)


@router.get("/sessions/{session_id}", response_model=AssistantSessionDetail)
def get_session_route(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_capability("assistant", "query")),
) -> AssistantSessionDetail:
    return get_assistant_session_detail(db, session_id=session_id, current_user=current_user)


@router.patch("/sessions/{session_id}", response_model=AssistantSessionSummary)
def update_session_route(
    session_id: str,
    payload: AssistantSessionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_capability("assistant", "query")),
) -> AssistantSessionSummary:
    session = update_assistant_session(
        db,
        session_id=session_id,
        payload=payload,
        current_user=current_user,
    )
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="assistant.session_updated",
        target_type="assistant_session",
        target_id=session_id,
        context=payload.model_dump(mode="json", exclude_none=True),
    )
    db.commit()
    return session


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session_route(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_capability("assistant", "query")),
) -> Response:
    delete_assistant_session(db, session_id=session_id, current_user=current_user)
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="assistant.session_deleted",
        target_type="assistant_session",
        target_id=session_id,
        context={},
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/sessions/{session_id}/messages", response_model=list[AssistantMessageResponse])
def list_messages_route(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_capability("assistant", "query")),
) -> list[AssistantMessageResponse]:
    return list_assistant_messages(db, session_id=session_id, current_user=current_user)


@router.post("/sessions/{session_id}/messages", response_model=AssistantSessionMessageResult)
def post_message_route(
    session_id: str,
    payload: AssistantMessageCreateRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    current_user: User = Depends(require_capability("assistant", "query")),
) -> AssistantSessionMessageResult:
    result = post_assistant_message(
        db,
        settings,
        session_id=session_id,
        payload=payload,
        current_user=current_user,
    )
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="assistant.message_posted",
        target_type="assistant_session",
        target_id=session_id,
        context={"intent": result.response.intent, "status": result.response.status},
    )
    db.commit()
    return result


@router.post("/sessions/{session_id}/messages/stream")
def stream_message_route(
    session_id: str,
    payload: AssistantMessageCreateRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    current_user: User = Depends(require_capability("assistant", "query")),
) -> StreamingResponse:
    def event_stream() -> Iterator[bytes]:
        for event in stream_assistant_message_events(
            db,
            settings,
            session_id=session_id,
            payload=payload,
            current_user=current_user,
        ):
            if event.get("type") == "done":
                result = event.get("result")
                response = result.get("response") if isinstance(result, dict) else {}
                record_audit_event(
                    db,
                    actor_user_id=current_user.id,
                    action="assistant.message_streamed",
                    target_type="assistant_session",
                    target_id=session_id,
                    context={
                        "intent": response.get("intent") if isinstance(response, dict) else None,
                        "status": response.get("status") if isinstance(response, dict) else None,
                    },
                )
                db.commit()
            yield _encode_sse_event(event)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/query", response_model=AssistantResponse)
def assistant_query_route(
    payload: AssistantQueryRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    current_user: User = Depends(require_capability("assistant", "query")),
) -> AssistantResponse:
    response = assistant_query(db, settings, payload=payload, current_user=current_user)
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="assistant.query",
        target_type="assistant_response",
        target_id=response.answer_id,
        context={"intent": response.intent, "status": response.status},
    )
    db.commit()
    return response


@router.get("/capabilities", response_model=AssistantCapabilitiesResponse)
def capabilities_route(
    settings: Settings = Depends(get_settings_dependency),
) -> AssistantCapabilitiesResponse:
    return get_assistant_capabilities(settings)


@router.get("/prompts/suggestions", response_model=AssistantPromptSuggestionsResponse)
def prompt_suggestions_route() -> AssistantPromptSuggestionsResponse:
    return get_prompt_suggestions()


@router.get("/context-options", response_model=AssistantContextOptionsResponse)
def context_options_route(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_capability("assistant", "query")),
) -> AssistantContextOptionsResponse:
    return get_context_options(db)
