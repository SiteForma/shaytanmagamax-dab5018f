from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
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
    update_assistant_session,
)
from apps.api.app.modules.audit.service import record_audit_event

router = APIRouter(prefix="/assistant", tags=["assistant"])


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
