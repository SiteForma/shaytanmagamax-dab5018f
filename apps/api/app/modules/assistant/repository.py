from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.common.utils import utc_now
from apps.api.app.core.errors import DomainError
from apps.api.app.db.models import AssistantMessage, AssistantSession
from apps.api.app.modules.assistant.schemas import (
    AssistantMessageResponse,
    AssistantPinnedContext,
    AssistantResponse,
    AssistantSessionSummary,
    AssistantTokenUsage,
)


def _session_or_404(db: Session, session_id: str, *, user_id: str | None) -> AssistantSession:
    session = db.get(AssistantSession, session_id)
    if session is None or (user_id and session.created_by_id != user_id):
        raise DomainError(code="assistant_session_not_found", message="Assistant session not found")
    return session


def create_session(
    db: Session,
    *,
    user_id: str | None,
    title: str | None,
    preferred_mode: str,
    pinned_context: AssistantPinnedContext | None,
) -> AssistantSession:
    session = AssistantSession(
        created_by_id=user_id,
        title=(title or "Новая сессия").strip(),
        preferred_mode=preferred_mode,
        provider="deterministic",
        pinned_context=(pinned_context or AssistantPinnedContext())
        .normalized()
        .model_dump(by_alias=True),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_sessions(db: Session, *, user_id: str | None) -> list[AssistantSession]:
    stmt = select(AssistantSession).order_by(
        AssistantSession.last_message_at.desc().nullslast(),
        AssistantSession.created_at.desc(),
    )
    if user_id:
        stmt = stmt.where(AssistantSession.created_by_id == user_id)
    return db.scalars(stmt).all()


def summarize_session_token_usage(db: Session, session_id: str) -> AssistantTokenUsage:
    messages = db.scalars(
        select(AssistantMessage).where(
            AssistantMessage.session_id == session_id,
            AssistantMessage.role == "assistant",
        )
    ).all()
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    cost_usd = 0.0
    cost_rub = 0.0
    for message in messages:
        response = message.response_payload or {}
        usage = response.get("tokenUsage") if isinstance(response, dict) else None
        if not isinstance(usage, dict):
            continue
        input_tokens += int(usage.get("inputTokens") or usage.get("input_tokens") or 0)
        output_tokens += int(usage.get("outputTokens") or usage.get("output_tokens") or 0)
        total_tokens += int(usage.get("totalTokens") or usage.get("total_tokens") or 0)
        cost_usd += float(usage.get("estimatedCostUsd") or usage.get("estimated_cost_usd") or 0)
        cost_rub += float(usage.get("estimatedCostRub") or usage.get("estimated_cost_rub") or 0)
    return AssistantTokenUsage(
        inputTokens=input_tokens,
        outputTokens=output_tokens,
        totalTokens=total_tokens,
        estimatedCostUsd=round(cost_usd, 8),
        estimatedCostRub=round(cost_rub, 4),
    )


def get_session(db: Session, session_id: str, *, user_id: str | None) -> AssistantSession:
    return _session_or_404(db, session_id, user_id=user_id)


def list_messages(
    db: Session,
    session_id: str,
    *,
    user_id: str | None,
) -> list[AssistantMessage]:
    session = _session_or_404(db, session_id, user_id=user_id)
    return db.scalars(
        select(AssistantMessage)
        .where(AssistantMessage.session_id == session.id)
        .order_by(AssistantMessage.created_at.asc())
    ).all()


def update_session_context(
    db: Session,
    session_id: str,
    *,
    user_id: str | None,
    pinned_context: AssistantPinnedContext,
) -> AssistantSession:
    session = _session_or_404(db, session_id, user_id=user_id)
    session.pinned_context = pinned_context.normalized().model_dump(by_alias=True)
    session.updated_at = utc_now()
    db.add(session)
    db.flush()
    return session


def update_session(
    db: Session,
    session_id: str,
    *,
    user_id: str | None,
    title: str | None = None,
    status: str | None = None,
    preferred_mode: str | None = None,
    pinned_context: AssistantPinnedContext | None = None,
) -> AssistantSession:
    session = _session_or_404(db, session_id, user_id=user_id)
    if title is not None:
        normalized_title = title.strip()
        if not normalized_title:
            raise DomainError(
                code="assistant_session_title_required",
                message="Assistant session title cannot be empty",
            )
        session.title = normalized_title
    if status is not None:
        session.status = status
    if preferred_mode is not None:
        session.preferred_mode = preferred_mode
    if pinned_context is not None:
        session.pinned_context = pinned_context.normalized().model_dump(by_alias=True)
    session.updated_at = utc_now()
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def delete_session(
    db: Session,
    session_id: str,
    *,
    user_id: str | None,
) -> None:
    session = _session_or_404(db, session_id, user_id=user_id)
    db.delete(session)
    db.commit()


def append_user_message(
    db: Session,
    *,
    session_id: str,
    user_id: str | None,
    text: str,
    context: AssistantPinnedContext,
) -> AssistantMessage:
    session = _session_or_404(db, session_id, user_id=user_id)
    message = AssistantMessage(
        session_id=session.id,
        created_by_id=user_id,
        role="user",
        message_text=text,
        context_payload=context.normalized().model_dump(by_alias=True),
        generated_at=utc_now(),
    )
    session.last_message_at = message.generated_at
    session.message_count += 1
    if session.title == "Новая сессия":
        session.title = text[:80]
    db.add(message)
    db.add(session)
    db.flush()
    return message


def append_assistant_message(
    db: Session,
    *,
    session_id: str,
    user_id: str | None,
    text: str,
    intent: str,
    status: str,
    provider: str,
    confidence: float,
    trace_id: str,
    context: AssistantPinnedContext,
    response: AssistantResponse,
) -> AssistantMessage:
    session = _session_or_404(db, session_id, user_id=user_id)
    generated_at = utc_now()
    message = AssistantMessage(
        session_id=session.id,
        created_by_id=user_id,
        role="assistant",
        message_text=text,
        intent=intent,
        status=status,
        provider=provider,
        confidence=confidence,
        trace_id=trace_id,
        context_payload=context.normalized().model_dump(by_alias=True),
        response_payload=response.model_dump(by_alias=True),
        source_refs=[item.model_dump(by_alias=True) for item in response.source_refs],
        tool_calls=[item.model_dump(by_alias=True) for item in response.tool_calls],
        warnings=[item.model_dump() for item in response.warnings],
        generated_at=generated_at,
    )
    session.last_message_at = generated_at
    session.message_count += 1
    session.last_intent = intent
    session.provider = provider
    session.latest_trace_id = trace_id
    session.pinned_context = context.normalized().model_dump(by_alias=True)
    db.add(message)
    db.add(session)
    db.flush()
    return message


def serialize_message(message: AssistantMessage) -> AssistantMessageResponse:
    response = None
    if message.role == "assistant" and message.response_payload:
        response = AssistantResponse(**message.response_payload)
    return AssistantMessageResponse(
        id=message.id,
        sessionId=message.session_id,
        role=message.role,  # type: ignore[arg-type]
        text=message.message_text,
        createdAt=message.generated_at.isoformat(),
        intent=message.intent,  # type: ignore[arg-type]
        status=message.status,
        provider=message.provider,
        confidence=message.confidence,
        traceId=message.trace_id,
        context=AssistantPinnedContext(**(message.context_payload or {})),
        response=response,
    )


def serialize_session(
    session: AssistantSession,
    *,
    token_usage: AssistantTokenUsage | None = None,
) -> AssistantSessionSummary:
    usage = token_usage or AssistantTokenUsage()
    return AssistantSessionSummary(
        id=session.id,
        title=session.title,
        status=session.status,
        createdAt=session.created_at.isoformat(),
        updatedAt=session.updated_at.isoformat(),
        lastMessageAt=session.last_message_at.isoformat() if session.last_message_at else None,
        messageCount=session.message_count,
        pinnedContext=AssistantPinnedContext(**(session.pinned_context or {})),
        lastIntent=session.last_intent,  # type: ignore[arg-type]
        preferredMode=session.preferred_mode,
        provider=session.provider,
        latestTraceId=session.latest_trace_id,
        tokenUsage=usage,
        estimatedCostRub=usage.estimated_cost_rub,
    )
