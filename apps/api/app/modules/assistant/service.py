from __future__ import annotations

import time
from collections.abc import Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.config import Settings
from apps.api.app.db.models import Category, User
from apps.api.app.db.models import AssistantMessage
from apps.api.app.modules.assistant.orchestration import execute_assistant_query
from apps.api.app.modules.assistant.repository import (
    append_assistant_message,
    append_user_message,
    create_session,
    delete_session,
    get_session,
    list_messages,
    list_sessions,
    serialize_message,
    serialize_session,
    summarize_session_token_usage,
    update_session,
    update_session_context,
)
from apps.api.app.modules.assistant.schemas import (
    AssistantCapabilitiesResponse,
    AssistantCapability,
    AssistantContextOption,
    AssistantContextOptionsResponse,
    AssistantMessageCreateRequest,
    AssistantMessageResponse,
    AssistantPinnedContext,
    AssistantPromptSuggestion,
    AssistantPromptSuggestionsResponse,
    AssistantQueryRequest,
    AssistantResponse,
    AssistantSessionCreateRequest,
    AssistantSessionDetail,
    AssistantSessionMessageResult,
    AssistantSessionSummary,
    AssistantSessionUpdateRequest,
)
from apps.api.app.modules.catalog.service import list_skus
from apps.api.app.modules.clients.service import list_clients
from apps.api.app.modules.reserve.service import list_runs
from apps.api.app.modules.uploads.service import list_upload_files

PROMPT_SUGGESTIONS = [
    AssistantPromptSuggestion(
        id="free_chat",
        label="Возможности консоли",
        prompt="Объясни, как лучше задавать вопросы в этой консоли",
        intent="free_chat",
    ),
    AssistantPromptSuggestion(
        id="reserve_calc",
        label="Расчёт резерва по клиенту",
        prompt="Рассчитай резерв для Леман Про на 3 месяца по выбранным SKU",
        intent="reserve_calculation",
    ),
    AssistantPromptSuggestion(
        id="reserve_explain",
        label="Почему позиция critical",
        prompt="Почему этот SKU критичен и какой fallback использовался?",
        intent="reserve_explanation",
    ),
    AssistantPromptSuggestion(
        id="sku_summary",
        label="Сводка по SKU",
        prompt="Суммируй текущую ситуацию по выбранному SKU: продажи, склад, входящие поставки и резервный риск",
        intent="sku_summary",
    ),
    AssistantPromptSuggestion(
        id="inbound_impact",
        label="Влияние поставок",
        prompt="Какие входящие поставки сильнее всего снижают текущий дефицит?",
        intent="inbound_impact",
    ),
    AssistantPromptSuggestion(
        id="management_report",
        label="Управленческий отчёт 2025",
        prompt="Покажи управленческий отчёт 2025: подразделения, выручка, ПДЗ и спрос",
        intent="management_report_summary",
    ),
]


def _message_history_for_planning(messages: list[AssistantMessage]) -> list[dict[str, object]]:
    history: list[dict[str, object]] = []
    for message in messages[-8:]:
        response_payload = message.response_payload or {}
        history.append(
            {
                "role": message.role,
                "text": message.message_text[:1200],
                "intent": message.intent,
                "status": message.status,
                "title": response_payload.get("title") if isinstance(response_payload, dict) else None,
                "summary": response_payload.get("summary") if isinstance(response_payload, dict) else None,
                "type": response_payload.get("type") if isinstance(response_payload, dict) else None,
                "pendingIntent": response_payload.get("pendingIntent") if isinstance(response_payload, dict) else None,
                "missingFields": (response_payload.get("missingFields") or [])[:6]
                if isinstance(response_payload, dict)
                else [],
                "contextUsed": response_payload.get("contextUsed") if isinstance(response_payload, dict) else None,
                "sourceRefs": (response_payload.get("sourceRefs") or [])[:4]
                if isinstance(response_payload, dict)
                else [],
                "toolCalls": (response_payload.get("toolCalls") or [])[:4]
                if isinstance(response_payload, dict)
                else [],
            }
        )
    return history


def _normalized_context(
    explicit_context: AssistantPinnedContext | None,
    session_context: dict[str, object] | None = None,
) -> AssistantPinnedContext:
    if explicit_context is not None:
        return explicit_context.normalized()
    return AssistantPinnedContext(**(session_context or {})).normalized()


def create_assistant_session(
    db: Session,
    *,
    payload: AssistantSessionCreateRequest,
    current_user: User | None,
) -> AssistantSessionSummary:
    session = create_session(
        db,
        user_id=current_user.id if current_user else None,
        title=payload.title,
        preferred_mode=payload.preferred_mode,
        pinned_context=payload.pinned_context,
    )
    return serialize_session(session, token_usage=summarize_session_token_usage(db, session.id))


def list_assistant_sessions(db: Session, *, current_user: User | None) -> list[AssistantSessionSummary]:
    return [
        serialize_session(session, token_usage=summarize_session_token_usage(db, session.id))
        for session in list_sessions(db, user_id=current_user.id if current_user else None)
    ]


def get_assistant_session_detail(
    db: Session,
    *,
    session_id: str,
    current_user: User | None,
) -> AssistantSessionDetail:
    session = get_session(db, session_id, user_id=current_user.id if current_user else None)
    messages = [
        serialize_message(message)
        for message in list_messages(db, session.id, user_id=current_user.id if current_user else None)
    ]
    return AssistantSessionDetail(
        **serialize_session(
            session,
            token_usage=summarize_session_token_usage(db, session.id),
        ).model_dump(),
        messages=messages,
    )


def update_assistant_session(
    db: Session,
    *,
    session_id: str,
    payload: AssistantSessionUpdateRequest,
    current_user: User | None,
) -> AssistantSessionSummary:
    session = update_session(
        db,
        session_id,
        user_id=current_user.id if current_user else None,
        title=payload.title,
        status=payload.status,
        preferred_mode=payload.preferred_mode,
        pinned_context=payload.pinned_context.normalized() if payload.pinned_context else None,
    )
    return serialize_session(session, token_usage=summarize_session_token_usage(db, session.id))


def delete_assistant_session(
    db: Session,
    *,
    session_id: str,
    current_user: User | None,
) -> None:
    delete_session(db, session_id, user_id=current_user.id if current_user else None)


def list_assistant_messages(
    db: Session,
    *,
    session_id: str,
    current_user: User | None,
) -> list[AssistantMessageResponse]:
    return [
        serialize_message(message)
        for message in list_messages(db, session_id, user_id=current_user.id if current_user else None)
    ]


def _assistant_stream_chunks(text: str, *, chunk_size: int = 28) -> Iterator[str]:
    normalized = text or ""
    if not normalized:
        return
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + chunk_size)
        next_space = normalized.find(" ", end)
        if next_space != -1 and next_space - start <= chunk_size + 18:
            end = next_space + 1
        yield normalized[start:end]
        start = end


def _prepare_assistant_turn(
    db: Session,
    *,
    session_id: str,
    payload: AssistantMessageCreateRequest,
    current_user: User | None,
) -> tuple[list[AssistantMessage], AssistantPinnedContext, AssistantMessage]:
    session = get_session(db, session_id, user_id=current_user.id if current_user else None)
    previous_messages = list_messages(
        db,
        session.id,
        user_id=current_user.id if current_user else None,
    )
    context = _normalized_context(payload.context, session.pinned_context)
    update_session_context(
        db,
        session_id,
        user_id=current_user.id if current_user else None,
        pinned_context=context,
    )
    user_message = append_user_message(
        db,
        session_id=session_id,
        user_id=current_user.id if current_user else None,
        text=payload.text,
        context=context,
    )
    return previous_messages, context, user_message


def _complete_assistant_turn(
    db: Session,
    settings: Settings,
    *,
    session_id: str,
    payload: AssistantMessageCreateRequest,
    current_user: User | None,
    previous_messages: list[AssistantMessage],
    context: AssistantPinnedContext,
) -> tuple[AssistantResponse, AssistantMessage]:
    response = execute_assistant_query(
        db,
        settings,
        payload=AssistantQueryRequest(
            text=payload.text,
            sessionId=session_id,
            preferredMode=payload.preferred_mode,
            context=context,
        ),
        created_by_id=current_user.id if current_user else None,
        current_user=current_user,
        history=_message_history_for_planning(previous_messages),
    )
    assistant_message = append_assistant_message(
        db,
        session_id=session_id,
        user_id=current_user.id if current_user else None,
        text=response.summary,
        intent=response.intent,
        status=response.status,
        provider=response.provider,
        confidence=response.confidence,
        trace_id=response.trace_id,
        context=context,
        response=response,
    )
    return response, assistant_message


def _assistant_turn_result(
    db: Session,
    *,
    session_id: str,
    current_user: User | None,
    user_message: AssistantMessage,
    assistant_message: AssistantMessage,
    response: AssistantResponse,
) -> AssistantSessionMessageResult:
    updated_session = get_session(db, session_id, user_id=current_user.id if current_user else None)
    return AssistantSessionMessageResult(
        session=serialize_session(
            updated_session,
            token_usage=summarize_session_token_usage(db, updated_session.id),
        ),
        userMessage=serialize_message(user_message),
        assistantMessage=serialize_message(assistant_message),
        response=response,
    )


def post_assistant_message(
    db: Session,
    settings: Settings,
    *,
    session_id: str,
    payload: AssistantMessageCreateRequest,
    current_user: User | None,
) -> AssistantSessionMessageResult:
    previous_messages, context, user_message = _prepare_assistant_turn(
        db,
        session_id=session_id,
        payload=payload,
        current_user=current_user,
    )
    response, assistant_message = _complete_assistant_turn(
        db,
        settings,
        session_id=session_id,
        payload=payload,
        current_user=current_user,
        previous_messages=previous_messages,
        context=context,
    )
    db.commit()
    return _assistant_turn_result(
        db,
        session_id=session_id,
        current_user=current_user,
        user_message=user_message,
        assistant_message=assistant_message,
        response=response,
    )


def stream_assistant_message_events(
    db: Session,
    settings: Settings,
    *,
    session_id: str,
    payload: AssistantMessageCreateRequest,
    current_user: User | None,
) -> Iterator[dict[str, object]]:
    yield {
        "type": "thinking",
        "sessionId": session_id,
        "stage": "received",
        "message": "Запрос принят. Собираю контекст MAGAMAX.",
    }
    try:
        previous_messages, context, user_message = _prepare_assistant_turn(
            db,
            session_id=session_id,
            payload=payload,
            current_user=current_user,
        )
        yield {
            "type": "thinking",
            "sessionId": session_id,
            "stage": "planning",
            "message": "Определяю смысл запроса и нужные инструменты MAGAMAX.",
            "userMessage": serialize_message(user_message).model_dump(by_alias=True),
        }
        response, assistant_message = _complete_assistant_turn(
            db,
            settings,
            session_id=session_id,
            payload=payload,
            current_user=current_user,
            previous_messages=previous_messages,
            context=context,
        )
        result = _assistant_turn_result(
            db,
            session_id=session_id,
            current_user=current_user,
            user_message=user_message,
            assistant_message=assistant_message,
            response=response,
        )
        db.commit()

        if response.response_type == "clarification" or response.status == "needs_clarification":
            yield {
                "type": "clarification",
                "messageId": assistant_message.id,
                "responseId": response.answer_id,
                "intent": response.intent,
                "summary": response.summary,
                "missingFields": response.missing_fields,
                "suggestedChips": response.suggested_chips,
                "pendingIntent": response.pending_intent,
            }

        for tool_call in response.tool_calls:
            yield {
                "type": "tool_call",
                "messageId": assistant_message.id,
                "responseId": response.answer_id,
                "toolName": tool_call.tool_name,
                "arguments": tool_call.arguments,
            }
            yield {
                "type": "tool_result",
                "messageId": assistant_message.id,
                "responseId": response.answer_id,
                "toolName": tool_call.tool_name,
                "status": tool_call.status,
                "summary": tool_call.summary,
                "latencyMs": tool_call.latency_ms,
            }

        for delta in _assistant_stream_chunks(response.summary):
            yield {
                "type": "answer_delta",
                "messageId": assistant_message.id,
                "responseId": response.answer_id,
                "delta": delta,
            }
            time.sleep(0.018)

        yield {
            "type": "done",
            "result": result.model_dump(by_alias=True),
        }
    except Exception as exc:
        db.rollback()
        yield {
            "type": "error",
            "code": getattr(exc, "code", "assistant_stream_failed"),
            "message": getattr(exc, "message", str(exc)),
        }


def assistant_query(
    db: Session,
    settings: Settings,
    *,
    payload: AssistantQueryRequest,
    current_user: User | None,
) -> AssistantResponse:
    if payload.session_id:
        result = post_assistant_message(
            db,
            settings,
            session_id=payload.session_id,
            payload=AssistantMessageCreateRequest(
                text=payload.prompt_text(),
                preferredMode=payload.preferred_mode,
                context=payload.context,
            ),
            current_user=current_user,
        )
        return result.response
    return execute_assistant_query(
        db,
        settings,
        payload=payload,
        created_by_id=current_user.id if current_user else None,
        current_user=current_user,
    )


def get_assistant_capabilities(settings: Settings) -> AssistantCapabilitiesResponse:
    return AssistantCapabilitiesResponse(
        provider=settings.assistant_provider if settings.assistant_llm_enabled else "deterministic",
        deterministicFallback=True,
        intents=[
            AssistantCapability(key="free_chat", label="MAGAMAX AI"),
            AssistantCapability(key="reserve_calculation", label="Расчёт резерва"),
            AssistantCapability(key="reserve_explanation", label="Объяснение строки резерва"),
            AssistantCapability(key="sku_summary", label="Сводка по SKU"),
            AssistantCapability(key="client_summary", label="Сводка по DIY-клиенту"),
            AssistantCapability(key="inbound_impact", label="Влияние поставок"),
            AssistantCapability(key="stock_risk_summary", label="Риск покрытия"),
            AssistantCapability(key="upload_status_summary", label="Freshness и ingestion-контур"),
            AssistantCapability(key="quality_issue_summary", label="Качество данных"),
            AssistantCapability(key="management_report_summary", label="Управленческий отчёт 2025"),
            AssistantCapability(key="sales_summary", label="Сводка продаж"),
            AssistantCapability(key="period_comparison", label="Сравнение периодов"),
        ],
        sessionSupport=True,
        pinnedContextSupport=True,
    )


def get_prompt_suggestions() -> AssistantPromptSuggestionsResponse:
    return AssistantPromptSuggestionsResponse(items=PROMPT_SUGGESTIONS)


def get_context_options(db: Session) -> AssistantContextOptionsResponse:
    clients = [
        AssistantContextOption(id=item.id, label=item.name, hint=item.region)
        for item in list_clients(db)
    ]
    skus = [
        AssistantContextOption(id=item.id, label=f"{item.article} · {item.name}", hint=item.category)
        for item in list_skus(db)[:60]
    ]
    uploads = [
        AssistantContextOption(id=item.id, label=item.file_name, hint=item.status)
        for item in list_upload_files(db)[:25]
    ]
    reserve_runs = [
        AssistantContextOption(id=item.id, label=f"{item.id} · {item.scope_type}", hint=item.created_at)
        for item in list_runs(db)[:20]
    ]
    categories = [
        AssistantContextOption(id=category.id, label=category.name, hint=category.code)
        for category in db.scalars(select(Category).order_by(Category.name)).all()
    ]
    return AssistantContextOptionsResponse(
        clients=clients,
        skus=skus,
        uploads=uploads,
        reserveRuns=reserve_runs,
        categories=categories,
    )
