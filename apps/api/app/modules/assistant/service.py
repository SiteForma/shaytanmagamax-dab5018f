from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.config import Settings
from apps.api.app.db.models import Category, User
from apps.api.app.modules.assistant.orchestration import execute_assistant_query
from apps.api.app.modules.assistant.repository import (
    append_assistant_message,
    append_user_message,
    create_session,
    get_session,
    list_messages,
    list_sessions,
    serialize_message,
    serialize_session,
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
]


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
    return serialize_session(session)


def list_assistant_sessions(db: Session, *, current_user: User | None) -> list[AssistantSessionSummary]:
    return [
        serialize_session(session)
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
    return AssistantSessionDetail(**serialize_session(session).model_dump(), messages=messages)


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
    return serialize_session(session)


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


def post_assistant_message(
    db: Session,
    settings: Settings,
    *,
    session_id: str,
    payload: AssistantMessageCreateRequest,
    current_user: User | None,
) -> AssistantSessionMessageResult:
    session = get_session(db, session_id, user_id=current_user.id if current_user else None)
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
    db.commit()
    updated_session = get_session(db, session_id, user_id=current_user.id if current_user else None)
    return AssistantSessionMessageResult(
        session=serialize_session(updated_session),
        userMessage=serialize_message(user_message),
        assistantMessage=serialize_message(assistant_message),
        response=response,
    )


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
    )


def get_assistant_capabilities(settings: Settings) -> AssistantCapabilitiesResponse:
    return AssistantCapabilitiesResponse(
        provider=settings.assistant_provider if settings.assistant_llm_enabled else "deterministic",
        deterministicFallback=True,
        intents=[
            AssistantCapability(key="reserve_calculation", label="Расчёт резерва"),
            AssistantCapability(key="reserve_explanation", label="Объяснение строки резерва"),
            AssistantCapability(key="sku_summary", label="Сводка по SKU"),
            AssistantCapability(key="client_summary", label="Сводка по DIY-клиенту"),
            AssistantCapability(key="inbound_impact", label="Влияние поставок"),
            AssistantCapability(key="stock_risk_summary", label="Риск покрытия"),
            AssistantCapability(key="upload_status_summary", label="Freshness и ingestion-контур"),
            AssistantCapability(key="quality_issue_summary", label="Качество данных"),
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
