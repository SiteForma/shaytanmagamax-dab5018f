from __future__ import annotations

import re
from collections import OrderedDict

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from apps.api.app.common.utils import generate_id, utc_now
from apps.api.app.core.config import Settings
from apps.api.app.core.errors import DomainError
from apps.api.app.db.models import Category, Client, Sku, User, UserRole
from apps.api.app.modules.assistant.analytics_catalog import METRIC_CATALOG
from apps.api.app.modules.assistant.context import build_context_bundle
from apps.api.app.modules.assistant.domain import (
    AssistantAnswerDraft,
    AssistantContextBundle,
    AssistantResolvedContext,
    AssistantToolExecution,
    AssistantWarningData,
)
from apps.api.app.modules.assistant.periods import parse_period_text, previous_month_period
from apps.api.app.modules.assistant.permissions import require_assistant_tool_capabilities
from apps.api.app.modules.assistant.providers import (
    combine_token_usage,
    finalize_with_provider,
    plan_route_with_provider,
)
from apps.api.app.modules.assistant.registry import AssistantToolSpec, get_default_tool_registry
from apps.api.app.modules.assistant.routing import route_question
from apps.api.app.modules.assistant.schemas import (
    AssistantAnswerSection,
    AssistantFollowupSuggestion,
    AssistantPinnedContext,
    AssistantQueryRequest,
    AssistantResponse,
    AssistantSourceRef,
    AssistantTokenUsage,
    AssistantToolCall,
    AssistantWarning,
)
from apps.api.app.modules.assistant.state import (
    AssistantMissingField,
    AssistantSessionState,
    derive_state_from_history,
    merge_state,
    resolve_followup_from_state,
)


def _qty(value: float | int | None) -> str:
    if value is None:
        return "н/д"
    return f"{float(value):.1f}".rstrip("0").rstrip(".")


def _money(value: object) -> str:
    try:
        numeric = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "н/д"
    abs_value = abs(numeric)
    if abs_value >= 1_000_000_000:
        return f"{numeric / 1_000_000_000:.2f} млрд"
    if abs_value >= 1_000_000:
        return f"{numeric / 1_000_000:.1f} млн"
    if abs_value >= 1_000:
        return f"{numeric / 1_000:.1f} тыс."
    return f"{numeric:.1f}".rstrip("0").rstrip(".")


def _metric_value(value: object, unit: str) -> str:
    if unit == "rub":
        return f"{_money(value)} ₽"
    if unit == "pct":
        return f"{float(value):.2f}".rstrip("0").rstrip(".") + "%"
    if unit == "ratio":
        return f"{float(value) * 100:.1f}%"
    return _qty(float(value))


def _localize_status_reason(value: str | None) -> str:
    if not value:
        return "Причина не указана"
    replacements = {
        "Coverage is far below target reserve": "Покрытие значительно ниже целевого резерва",
        "Coverage is below target reserve": "Покрытие ниже целевого резерва",
        "Insufficient history": "Недостаточно истории",
    }
    return replacements.get(value, value)


def _localize_status_code(value: str) -> str:
    return {
        "critical": "критичный",
        "warning": "предупреждение",
        "healthy": "в норме",
        "no_history": "без истории",
        "inactive": "неактивный",
        "overstocked": "избыточный",
    }.get(value, value)


def _localize_signal(value: str) -> str:
    return {
        "falling_demand": "Спрос снижается относительно последних месяцев",
        "rising_demand": "Спрос ускоряется относительно базовой истории",
        "volatile_history": "История спроса нестабильна",
        "weak_history": "Истории продаж недостаточно для уверенной оценки",
        "no_recent_sales": "Нет недавних продаж в выбранном окне",
        "insufficient_history": "Недостаточно истории на разрешённых уровнях fallback",
        "strict_recent_fell_back_to_6m": "Строгая recent average опиралась на 6-месячное окно",
        "proxy_history_used": "Использована прокси-история вместо прямой клиентской истории",
    }.get(value, value)


def _section(
    *,
    section_type: str,
    title: str,
    body: str | None = None,
    metrics: list[dict[str, object]] | None = None,
    rows: list[dict[str, object]] | None = None,
    items: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": generate_id("asec"),
        "type": section_type,
        "title": title,
        "body": body,
        "metrics": metrics or [],
        "rows": rows or [],
        "items": items or [],
    }


def _metric(key: str, label: str, value: str, tone: str = "neutral") -> dict[str, object]:
    return {"key": key, "label": label, "value": value, "tone": tone}


def _context_schema(context: AssistantResolvedContext) -> AssistantPinnedContext:
    return AssistantPinnedContext(
        selectedClientId=context.selected_client_id,
        selectedSkuId=context.selected_sku_id,
        selectedUploadIds=context.selected_upload_ids,
        selectedReserveRunId=context.selected_reserve_run_id,
        selectedCategoryId=context.selected_category_id,
    )


def _user_for_tool_check(
    db: Session, current_user: User | None, created_by_id: str | None
) -> User | None:
    if current_user is not None:
        return current_user
    if not created_by_id:
        return None
    return db.scalar(
        select(User)
        .options(joinedload(User.roles).joinedload(UserRole.role))
        .where(User.id == created_by_id)
    )


def _period_from_question(question: str) -> dict[str, str]:
    return parse_period_text(question).as_range_params()


def _previous_month(value: str) -> str | None:
    return previous_month_period(value)


def _default_year_from_params(params: dict[str, object]) -> int | None:
    value = str(params.get("date_from") or params.get("current_period") or "")
    if len(value) >= 4 and value[:4].isdigit():
        return int(value[:4])
    period = params.get("period")
    if isinstance(period, dict):
        date_from = str(period.get("date_from") or "")
        if len(date_from) >= 4 and date_from[:4].isdigit():
            return int(date_from[:4])
    return None


def _metric_from_question(question: str) -> str | None:
    q = question.lower()
    if any(token in q for token in ("штук", "шт", "колич", "quantity", "qty")):
        return "sales_qty"
    if any(token in q for token in ("выруч", "руб", "revenue", "заработ")):
        return "revenue"
    if "свобод" in q and "остат" in q:
        return "free_stock"
    if any(token in q for token in ("остат", "склад")):
        return "stock_qty"
    if "дефицит" in q:
        return "shortage_qty"
    if "покрыт" in q:
        return "coverage_months"
    if any(token in q for token in ("постав", "inbound", "пришл", "поступил", "поступл")):
        return "inbound_qty"
    if any(token in q for token in ("рентаб", "марж")):
        return "profitability"
    return None


def _metrics_from_question(question: str) -> list[str]:
    q = question.lower()
    if any(token in q for token in ("в штуках", "в шт", "штук", "шт", "колич")):
        return ["sales_qty"]
    if any(token in q for token in ("выруч", "руб", "revenue", "заработ")):
        return ["revenue"]
    if any(token in q for token in ("продаж", "реализац", "sales")):
        return ["revenue", "sales_qty"]
    metric = _metric_from_question(question)
    return [metric] if metric else []


def _dimensions_from_question(question: str) -> list[str]:
    q = question.lower()
    dimensions: list[str] = []
    if "по категор" in q or "категор" in q:
        dimensions.append("category")
    if "по клиент" in q or "клиент" in q:
        dimensions.append("client")
    if "по sku" in q or "топ sku" in q or "sku" in q or "хуже всего продав" in q or "товар" in q:
        dimensions.extend(["sku", "article"])
    if "по артик" in q or "артикул" in q:
        dimensions.append("article")
    if "по склад" in q or "склад" in q:
        dimensions.append("warehouse")
    if "по месяц" in q or "динамик" in q:
        dimensions.append("month")
    if "по кварт" in q:
        dimensions.append("quarter")
    return list(dict.fromkeys(dimensions))


def _params_from_route(
    *,
    question: str,
    bundle: AssistantContextBundle,
    plan_params: dict[str, object],
    state_params: dict[str, object],
) -> dict[str, object]:
    params: dict[str, object] = {}
    params.update(state_params)
    params.update(plan_params)
    if bundle.route.extracted_client_id:
        params["client_id"] = bundle.route.extracted_client_id
    elif bundle.context.selected_client_id:
        params.setdefault("client_id", bundle.context.selected_client_id)
    if bundle.route.extracted_sku_ids:
        params["sku_ids"] = bundle.route.extracted_sku_ids
        params.setdefault("sku_id", bundle.route.extracted_sku_ids[0])
    elif bundle.context.selected_sku_id:
        params.setdefault("sku_id", bundle.context.selected_sku_id)
    if bundle.route.extracted_category_id:
        params["category_id"] = bundle.route.extracted_category_id
    elif bundle.context.selected_category_id:
        params.setdefault("category_id", bundle.context.selected_category_id)
    if bundle.context.selected_reserve_run_id:
        params.setdefault("reserve_run_id", bundle.context.selected_reserve_run_id)
    if bundle.route.extracted_client_name:
        params.setdefault("client_name", bundle.route.extracted_client_name)
    if bundle.route.reserve_months is not None:
        params.setdefault("reserve_months", bundle.route.reserve_months)
    if bundle.route.safety_factor is not None:
        params.setdefault("safety_factor", bundle.route.safety_factor)
    if bundle.route.intent == "management_report_summary":
        params.setdefault("question", question)
    if bundle.route.intent == "sales_summary":
        params.pop("metrics", None)
        params.pop("dimensions", None)
        params.pop("dimension", None)
        parsed = parse_period_text(question, default_year=_default_year_from_params(params))
        params.update(
            {key: value for key, value in parsed.as_range_params().items() if key not in params}
        )
        metric = _metric_from_question(question)
        if metric:
            params.setdefault("metric", metric)
        else:
            params.setdefault("metric", "revenue")
    if bundle.route.intent == "period_comparison":
        q = question.lower()
        metric = _metric_from_question(question)
        if metric:
            params.setdefault("metric", "quantity" if metric == "sales_qty" else metric)
        elif any(token in q for token in ("продаж", "sales")):
            params.setdefault("metric", "quantity")
        years = re.findall(r"\b(20\d{2})\b", q)
        if len(years) >= 2:
            params.setdefault("current_period", years[0])
            params.setdefault("previous_period", years[1])
        parsed = parse_period_text(question, default_year=_default_year_from_params(params))
        if parsed.current_period and not params.get("current_period"):
            params["current_period"] = parsed.current_period
        if parsed.previous_period and ("прошл" in q or not params.get("previous_period")):
            params.setdefault("previous_period", parsed.previous_period)
        current_period = str(params.get("current_period") or "")
        if "прошл" in q and current_period and not params.get("previous_period"):
            previous = _previous_month(current_period)
            if previous:
                params["previous_period"] = previous
    if bundle.route.intent == "analytics_slice":
        parsed = parse_period_text(question, default_year=_default_year_from_params(params))
        if not params.get("period") and parsed.date_from and parsed.date_to:
            params["period"] = {"date_from": parsed.date_from, "date_to": parsed.date_to}
            params.setdefault("date_from", parsed.date_from)
            params.setdefault("date_to", parsed.date_to)
        elif not params.get("period") and params.get("date_from") and params.get("date_to"):
            params["period"] = {"date_from": params["date_from"], "date_to": params["date_to"]}
        metrics = _metrics_from_question(question)
        if metrics:
            params.setdefault("metrics", metrics)
        elif not params.get("metrics") and not params.get("metric"):
            params.setdefault("metrics", ["revenue", "sales_qty"])
        dimensions = _dimensions_from_question(question)
        if dimensions:
            params.setdefault("dimensions", dimensions)
        elif not params.get("dimensions") and not params.get("dimension"):
            selected_metrics = (
                [str(item) for item in params.get("metrics", [])]
                if isinstance(params.get("metrics"), list)
                else []
            )
            metric_source = (
                METRIC_CATALOG.get(selected_metrics[0]).source
                if selected_metrics and selected_metrics[0] in METRIC_CATALOG
                else "sales"
            )
            if metric_source == "sales":
                params.setdefault("dimensions", [] if params.get("client_id") else ["client"])
            elif metric_source == "stock":
                params.setdefault("dimensions", ["sku", "article"])
            elif metric_source == "reserve":
                params.setdefault("dimensions", ["client", "sku", "article"])
            elif metric_source == "inbound":
                params.setdefault("dimensions", ["sku", "article"])
            else:
                params.setdefault("dimensions", ["product_group"])
        if "топ" in question.lower() and not params.get("limit"):
            params["limit"] = 20
        if "падени" in question.lower() or "просел" in question.lower():
            params.setdefault("sort_direction", "asc")
    return {key: value for key, value in params.items() if value not in (None, "", [])}


def _clarification_chips(missing_fields: list[AssistantMissingField]) -> list[str]:
    chips: list[str] = []
    for field in missing_fields:
        if field.name == "client_id":
            chips.extend(["Леман Про", "OBI Россия", "Леруа Мерлен"])
        elif field.name == "date_from":
            chips.extend(["2025", "последние 6 месяцев"])
        elif field.name == "period":
            chips.extend(["март 2025", "2025 год", "последние 3 месяца"])
        elif field.name == "metric":
            chips.extend(["продажи", "выручка", "резерв"])
    return list(dict.fromkeys(chips))[:6]


def _compose_clarification(
    *,
    intent: str,
    missing_fields: list[AssistantMissingField],
    bundle: AssistantContextBundle,
) -> AssistantAnswerDraft:
    question = missing_fields[0].question if missing_fields else "Уточните параметры запроса."
    return AssistantAnswerDraft(
        intent=intent,  # type: ignore[arg-type]
        status="needs_clarification",
        response_type="clarification",
        confidence=0.62,
        title="Нужно уточнение",
        summary=question,
        sections=[
            _section(
                section_type="clarification",
                title="Уточнение",
                body=question,
                items=[field.question for field in missing_fields],
            )
        ],
        source_refs=[],
        tool_calls=[],
        followups=[
            {
                "id": f"chip_{index}",
                "label": chip,
                "prompt": chip,
                "action": "query",
            }
            for index, chip in enumerate(_clarification_chips(missing_fields))
        ],
        warnings=[],
        context_used=bundle.context,
        missing_fields=[field.to_payload() for field in missing_fields],
        suggested_chips=_clarification_chips(missing_fields),
        pending_intent=intent,
    )


def _state_has_context(state: AssistantSessionState) -> bool:
    return bool(
        state.pending_intent
        or state.last_intent
        or state.last_filters
        or state.last_period
        or state.last_metrics
        or state.last_entities.to_params()
    )


def _business_clarification_spec(
    question: str,
    state: AssistantSessionState,
) -> tuple[str, str, list[str], str] | None:
    q = question.lower().replace("ё", "е").strip()
    if not q or _state_has_context(state):
        return None
    has_period_hint = any(
        token in q
        for token in (
            "январ",
            "феврал",
            "март",
            "апрел",
            "май",
            "мая",
            "июн",
            "июл",
            "август",
            "сентябр",
            "октябр",
            "ноябр",
            "декабр",
            "2024",
            "2025",
            "прошл",
            "текущ",
            "этот месяц",
            "последние",
        )
    )

    if any(
        token in q
        for token in (
            "как отработали",
            "что с март",
            "что по март",
            "что с феврал",
            "что по феврал",
        )
    ):
        return (
            "metric",
            "Что посмотреть за период: выручку, продажи в штуках, клиентов, категории или проблемные SKU?",
            ["Выручка", "Продажи в штуках", "По клиентам", "По категориям", "Проблемные SKU"],
            "analytics_slice",
        )

    if not has_period_hint and any(
        token in q
        for token in ("где просели", "что просело", "кто просел", "просели", "по падению")
    ):
        return (
            "period",
            "За какой период проверить падение?",
            ["Март 2025", "2025 год", "Последние 3 месяца", "По клиентам", "По категориям"],
            "analytics_slice",
        )

    if any(token in q for token in ("покажи проблемные", "что проблемное", "проблемные")):
        return (
            "problem_scope",
            "Проблемные по какому признаку: дефицит, остатки, падение продаж или качество данных?",
            ["Дефицит", "Остатки", "Падение продаж", "Качество данных"],
            "stock_risk_summary",
        )

    if any(token in q for token in ("что надо заказать", "что заказать", "кого заказать")):
        return (
            "order_basis",
            "Сформировать список к заказу по дефициту резерва, низкому остатку или с учётом поставок?",
            ["Дефицит резерва", "Низкий остаток", "С учётом поставок"],
            "stock_risk_summary",
        )

    if "как дела" in q or q in {"что происходит", "что с"}:
        return (
            "business_area",
            "Что посмотреть: продажи, резерв, остатки, дефицит или итоги периода?",
            ["Продажи", "Резерв", "Остатки", "Дефицит", "Итоги 2025"],
            "analytics_slice",
        )

    return None


def _compose_business_clarification(
    *,
    intent: str,
    field_name: str,
    question: str,
    chips: list[str],
    bundle: AssistantContextBundle,
) -> AssistantAnswerDraft:
    missing_field = AssistantMissingField(
        name=field_name,
        label=field_name,
        question=question,
    )
    return AssistantAnswerDraft(
        intent=intent,  # type: ignore[arg-type]
        status="needs_clarification",
        response_type="clarification",
        confidence=0.7,
        title="Уточните срез",
        summary=question,
        sections=[
            _section(
                section_type="clarification",
                title="Что уточнить",
                body=question,
                items=chips,
            )
        ],
        source_refs=[],
        tool_calls=[],
        followups=[
            {"id": f"chip_{index}", "label": chip, "prompt": chip, "action": "query"}
            for index, chip in enumerate(chips)
        ],
        warnings=[],
        context_used=bundle.context,
        missing_fields=[missing_field.to_payload()],
        suggested_chips=chips,
        pending_intent=intent,
    )


def _trace_metadata(
    *,
    resolved_intent: str,
    resolved_tool: str | None,
    missing_fields: list[AssistantMissingField],
    clarification_reason: str | None = None,
    permission_denied_tool: str | None = None,
    source_refs_count: int = 0,
) -> dict[str, object]:
    return {
        "resolved_intent": resolved_intent,
        "resolved_tool": resolved_tool,
        "missing_fields": [field.name for field in missing_fields],
        "clarification_reason": clarification_reason,
        "permission_denied_tool": permission_denied_tool,
        "source_refs_count": source_refs_count,
    }


def _validate_entity_params(db: Session, params: dict[str, object]) -> None:
    client_id = str(params.get("client_id") or "").strip()
    if client_id and db.get(Client, client_id) is None:
        raise DomainError(
            code="assistant_entity_not_available",
            message="Запрошенный клиент недоступен или не найден.",
            details={"entity": "client", "param": "client_id"},
            status_code=403,
        )

    sku_id = str(params.get("sku_id") or "").strip()
    if sku_id and db.get(Sku, sku_id) is None:
        raise DomainError(
            code="assistant_entity_not_available",
            message="Запрошенный SKU недоступен или не найден.",
            details={"entity": "sku", "param": "sku_id"},
            status_code=403,
        )

    sku_ids = params.get("sku_ids")
    if isinstance(sku_ids, list):
        for index, item in enumerate(sku_ids):
            item_id = str(item or "").strip()
            if item_id and db.get(Sku, item_id) is None:
                raise DomainError(
                    code="assistant_entity_not_available",
                    message="Один из запрошенных SKU недоступен или не найден.",
                    details={"entity": "sku", "param": f"sku_ids[{index}]"},
                    status_code=403,
                )

    category_id = str(params.get("category_id") or "").strip()
    if category_id and db.get(Category, category_id) is None:
        raise DomainError(
            code="assistant_entity_not_available",
            message="Запрошенная категория недоступна или не найдена.",
            details={"entity": "category", "param": "category_id"},
            status_code=403,
        )


def _dispatch_tool(
    db: Session,
    *,
    spec: AssistantToolSpec,
    bundle: AssistantContextBundle,
    params: dict[str, object],
    created_by_id: str | None,
    current_user: User | None,
) -> AssistantToolExecution:
    try:
        require_assistant_tool_capabilities(
            _user_for_tool_check(db, current_user, created_by_id),
            spec,
            params,
        )
    except Exception as exc:
        if getattr(exc, "code", None) == "permission_denied":
            details = dict(getattr(exc, "details", None) or {})
            details.setdefault("resolved_intent", bundle.route.intent)
            details.setdefault("resolved_tool", spec.name)
            details.setdefault("permission_denied_tool", spec.name)
            exc.details = details
        raise
    _validate_entity_params(db, params)
    execution = spec.handler(db, bundle, params, created_by_id)
    if spec.name in {"get_reserve", "explain_reserve"}:
        execution.tool_name = spec.name
    return execution


def _dedupe_source_refs(executions: list[AssistantToolExecution]) -> list[dict[str, object]]:
    seen: OrderedDict[tuple[str, str | None], dict[str, object]] = OrderedDict()
    for execution in executions:
        for ref in execution.source_refs:
            key = (str(ref.get("sourceType")), ref.get("entityId"))  # type: ignore[arg-type]
            seen.setdefault(key, ref)
    return list(seen.values())


def _collect_warnings(
    bundle: AssistantContextBundle, executions: list[AssistantToolExecution]
) -> list[AssistantWarningData]:
    warnings: list[AssistantWarningData] = [*bundle.warnings]
    for execution in executions:
        warnings.extend(execution.warnings)
    unique: OrderedDict[tuple[str, str], AssistantWarningData] = OrderedDict()
    for warning in warnings:
        unique.setdefault((warning.code, warning.message), warning)
    return list(unique.values())


def _generic_followups(intent: str, bundle: AssistantContextBundle) -> list[dict[str, object]]:
    if intent == "free_chat":
        return [
            {
                "id": "what_can_do",
                "label": "Что ты умеешь?",
                "prompt": "Что ты умеешь в этой системе и когда используешь данные?",
                "action": "query",
            },
            {
                "id": "reserve_example",
                "label": "Пример по резерву",
                "prompt": "Покажи пример вопроса для расчёта резерва по клиенту и SKU",
                "action": "query",
            },
            {
                "id": "data_sources",
                "label": "Какие данные доступны?",
                "prompt": "Какие данные и источники сейчас доступны в MAGAMAX?",
                "action": "query",
            },
        ]
    if intent == "reserve_calculation":
        return [
            {
                "id": "critical_positions",
                "label": "Показать только critical",
                "prompt": "Покажи только критичные позиции по этому расчёту резерва",
                "action": "query",
            },
            {
                "id": "reserve_3m",
                "label": "Пересчитать на 3 месяца",
                "prompt": "Пересчитай резерв на 3 месяца по тому же контексту",
                "action": "query",
            },
        ]
    if intent == "reserve_explanation":
        return [
            {
                "id": "open_sku",
                "label": "Открыть SKU",
                "prompt": "Суммируй ситуацию по этому SKU",
                "action": "query",
                "route": (
                    f"/sku?sku={bundle.context.selected_sku_id}"
                    if bundle.context.selected_sku_id
                    else None
                ),
            },
            {
                "id": "inbound_impact",
                "label": "Показать влияние поставок",
                "prompt": "Какие поставки снижают дефицит по этому SKU?",
                "action": "query",
            },
        ]
    if intent in {"sku_summary", "stock_risk_summary"}:
        return [
            {
                "id": "stock_risk",
                "label": "Показать риск покрытия",
                "prompt": "Покажи позиции с низким покрытием по этому контексту",
                "action": "query",
            },
            {
                "id": "quality_check",
                "label": "Проверить качество данных",
                "prompt": "Есть ли quality issues, влияющие на этот результат?",
                "action": "query",
            },
        ]
    if intent in {"client_summary", "diy_coverage_check"}:
        return [
            {
                "id": "below_reserve",
                "label": "Позиции ниже резерва",
                "prompt": "Покажи позиции ниже резерва по этому клиенту",
                "action": "query",
            },
            {
                "id": "top_skus",
                "label": "Топ SKU риска",
                "prompt": "Покажи SKU с наибольшим дефицитом по этому клиенту",
                "action": "query",
            },
        ]
    if intent in {"upload_status_summary", "quality_issue_summary"}:
        return [
            {
                "id": "uploads",
                "label": "Открыть загрузки",
                "prompt": "Покажи статус последних загрузок",
                "action": "open",
                "route": "/uploads",
            },
            {
                "id": "quality",
                "label": "Открыть quality",
                "prompt": "Покажи открытые quality issues",
                "action": "open",
                "route": "/quality",
            },
        ]
    if intent == "data_overview":
        return [
            {
                "id": "sales_by_client",
                "label": "Выручка по клиентам",
                "prompt": "Покажи выручку по клиентам за 2025 год",
                "action": "query",
            },
            {
                "id": "reserve_risks",
                "label": "Проблемный резерв",
                "prompt": "Покажи проблемные позиции резерва",
                "action": "query",
            },
            {
                "id": "management_report",
                "label": "Управленческий отчёт",
                "prompt": "Что полезного есть в управленческом отчёте 2025?",
                "action": "query",
            },
        ]
    if intent == "analytics_slice":
        return [
            {
                "id": "by_clients",
                "label": "А по клиентам?",
                "prompt": "А по клиентам?",
                "action": "query",
            },
            {
                "id": "by_categories",
                "label": "А по категориям?",
                "prompt": "А по категориям?",
                "action": "query",
            },
            {
                "id": "qty",
                "label": "А в штуках?",
                "prompt": "А в штуках?",
                "action": "query",
            },
            {
                "id": "compare_previous_month",
                "label": "Сравнить с прошлым месяцем",
                "prompt": "Сравни с прошлым месяцем",
                "action": "query",
            },
            {
                "id": "top_sku",
                "label": "Показать топ SKU",
                "prompt": "Покажи топ SKU",
                "action": "query",
            },
        ]
    if intent == "management_report_summary":
        return [
            {
                "id": "departments_revenue",
                "label": "Выручка подразделений",
                "prompt": "Покажи выручку и рентабельность по подразделениям за 2025",
                "action": "query",
            },
            {
                "id": "demand_shortage",
                "label": "СПРОС / недопоставки",
                "prompt": "Что известно по спросу и недопоставкам в управленческом отчёте 2025?",
                "action": "query",
            },
        ]
    return [
        {
            "id": "dashboard",
            "label": "Показать общую сводку",
            "prompt": "Покажи общую сводку по рискам и дефициту",
            "action": "query",
        }
    ]


def _reserve_rows_preview(rows: list[object], limit: int = 5) -> list[dict[str, object]]:
    preview: list[dict[str, object]] = []
    for row in rows[:limit]:
        preview.append(
            {
                "article": getattr(row, "article", ""),
                "clientName": getattr(row, "client_name", ""),
                "productName": getattr(row, "product_name", ""),
                "shortageQty": getattr(row, "shortage_qty", 0),
                "coverageMonths": getattr(row, "coverage_months", None),
                "status": getattr(row, "status", ""),
            }
        )
    return preview


def _reserve_rows_totals(rows: list[object], fallback: dict[str, object]) -> dict[str, object]:
    if not rows:
        return fallback
    positions = len(rows)
    at_risk = sum(
        1 for row in rows if getattr(row, "status", "") in {"critical", "warning", "no_history"}
    )
    total_shortage = sum(float(getattr(row, "shortage_qty", 0) or 0) for row in rows)
    coverage_values = [
        float(getattr(row, "coverage_months", 0) or 0)
        for row in rows
        if getattr(row, "coverage_months", None) is not None
    ]
    return {
        **fallback,
        "positions": positions,
        "positions_at_risk": at_risk,
        "total_shortage_qty": total_shortage,
        "avg_coverage_months": (
            sum(coverage_values) / len(coverage_values) if coverage_values else None
        ),
    }


def _compose_unsupported(bundle: AssistantContextBundle) -> AssistantAnswerDraft:
    return AssistantAnswerDraft(
        intent="unsupported_or_ambiguous",
        status="unsupported",
        confidence=0.82,
        title="Не по данным MAGAMAX",
        summary=(
            "Это вне моей рабочей зоны. Могу помочь по MAGAMAX: продажи, резерв, склад, поставки, "
            "загрузки, качество данных и управленческие отчёты."
        ),
        sections=[
            _section(
                section_type="warning_block",
                title="Если вопрос про MAGAMAX",
                items=[
                    "Сформулируйте его через клиента, SKU, период, склад, загрузку, резерв или отчёт.",
                    "Если я не понял рабочий контекст, я уточню недостающие параметры.",
                ],
            )
        ],
        source_refs=[],
        tool_calls=[],
        followups=_generic_followups("unsupported_or_ambiguous", bundle),
        warnings=bundle.warnings,
        context_used=bundle.context,
    )


def _free_chat_context_items(bundle: AssistantContextBundle) -> list[str]:
    items: list[str] = []
    if bundle.context.selected_client_id:
        items.append(f"Закреплён клиент: {bundle.context.selected_client_id}")
    if bundle.context.selected_sku_id:
        items.append(f"Закреплён SKU: {bundle.context.selected_sku_id}")
    if bundle.context.selected_category_id:
        items.append(f"Закреплена категория: {bundle.context.selected_category_id}")
    if bundle.context.selected_reserve_run_id:
        items.append(f"Закреплён reserve run: {bundle.context.selected_reserve_run_id}")
    if bundle.context.selected_upload_ids:
        items.append(f"Закреплены файлы загрузки: {', '.join(bundle.context.selected_upload_ids)}")
    return items


def _compose_free_chat(bundle: AssistantContextBundle, question: str) -> AssistantAnswerDraft:
    context_items = _free_chat_context_items(bundle)
    sections = [
        _section(
            section_type="narrative",
            title="Чем могу помочь",
            body=(
                "Я могу помочь как внутренний аналитик MAGAMAX. Напишите обычными словами, что посмотреть: "
                "продажи и выручку, клиентов и сети DIY, SKU и категории, остатки и покрытие склада, "
                "резерв и дефицит, входящие поставки, качество данных или управленческий отчёт."
            ),
        )
    ]
    if context_items:
        sections.append(
            _section(
                section_type="source_list",
                title="Контекст сессии",
                items=context_items,
            )
        )
    sections.append(
        _section(
            section_type="next_actions",
            title="Примеры",
            items=[
                "Как в целом закрыли 2025 год?",
                "Покажи продажи по OBI за март 2025.",
                "Какие SKU в зоне риска?",
                "Почему такой резерв?",
                "Что просело по категориям?",
                "Что пришло на склад и что закрывает дефицит?",
                "Какие товары нужно заказать?",
            ],
        )
    )
    return AssistantAnswerDraft(
        intent="free_chat",
        status="completed",
        confidence=0.68,
        title="MAGAMAX AI",
        summary="Я внутренний аналитик MAGAMAX: могу смотреть продажи, резерв, SKU, склад, поставки, качество данных и отчёты.",
        sections=sections,
        source_refs=[],
        tool_calls=[],
        followups=_generic_followups("free_chat", bundle),
        warnings=bundle.warnings,
        context_used=bundle.context,
        user_text=question,
    )


def _compose_answer(
    bundle: AssistantContextBundle,
    executions: list[AssistantToolExecution],
    *,
    question: str,
) -> AssistantAnswerDraft:
    if bundle.route.intent == "unsupported_or_ambiguous":
        return _compose_unsupported(bundle)
    if bundle.route.intent == "free_chat":
        return _compose_free_chat(bundle, question)

    tool_map = {execution.tool_name: execution for execution in executions}
    warnings = _collect_warnings(bundle, executions)
    source_refs = _dedupe_source_refs(executions)

    if bundle.route.intent == "data_overview":
        payload = tool_map["get_data_overview"].payload or {}
        data_sections = payload.get("sections") if isinstance(payload, dict) else []
        if not isinstance(data_sections, list):
            data_sections = []
        useful_sections = [
            section
            for section in data_sections
            if isinstance(section, dict) and int(section.get("count") or 0) > 0
        ]
        narrative = (
            f"В БД сейчас есть {len(useful_sections)} наполненных аналитических блоков из {len(data_sections)} проверенных. "
            "Я показываю только read-only факты из БД и не запускаю скрытые расчёты."
        )
        sections = [
            _section(
                section_type="narrative",
                title="Что доступно",
                body=narrative,
            ),
            _section(
                section_type="source_list",
                title="Полезные источники",
                rows=[
                    {
                        "source": section.get("label"),
                        "count": section.get("count"),
                        "freshnessAt": section.get("freshnessAt"),
                        "summary": section.get("summary"),
                        "route": section.get("route"),
                    }
                    for section in useful_sections
                ],
            ),
        ]
        if not useful_sections:
            sections.append(
                _section(
                    section_type="warning_block",
                    title="Данных пока нет",
                    items=["Наполненных аналитических источников в БД не найдено."],
                )
            )
        return AssistantAnswerDraft(
            intent="data_overview",
            status="completed" if useful_sections else "partial",
            confidence=0.9 if useful_sections else 0.6,
            title="Что есть в БД",
            summary=(
                narrative
                if useful_sections
                else "В БД не найдено наполненных аналитических источников."
            ),
            sections=sections,
            source_refs=source_refs,
            tool_calls=executions,
            followups=_generic_followups("data_overview", bundle),
            warnings=warnings,
            context_used=bundle.context,
        )

    if bundle.route.intent == "reserve_calculation":
        primary_execution = tool_map.get("calculate_reserve") or tool_map.get("get_reserve")
        calculation = primary_execution.payload if primary_execution is not None else None
        if calculation is None:
            return AssistantAnswerDraft(
                intent="reserve_calculation",
                status="partial",
                confidence=0.5,
                title="Резерв не найден",
                summary="Сохранённых строк резерва по выбранному контексту нет.",
                sections=[
                    _section(
                        section_type="warning_block",
                        title="Что известно",
                        items=[warning.message for warning in warnings]
                        or ["Для пересчёта попросите: «пересчитай резерв» и укажите клиента/SKU."],
                    )
                ],
                source_refs=source_refs,
                tool_calls=executions,
                followups=_generic_followups("reserve_calculation", bundle),
                warnings=warnings,
                context_used=bundle.context,
            )
        totals = _reserve_rows_totals(calculation.rows, calculation.run.summary_payload)
        is_recalculation = (
            primary_execution.tool_name == "calculate_reserve" if primary_execution else False
        )
        sections = [
            _section(
                section_type="narrative",
                title="Вывод",
                body=(
                    f"По {'новому расчёту' if is_recalculation else 'сохранённому расчёту'} ниже целевого резерва "
                    f"{int(totals.get('positions_at_risk', 0))} позиций, "
                    f"общий дефицит составляет {_qty(totals.get('total_shortage_qty'))} шт."
                ),
            ),
            _section(
                section_type="metric_summary",
                title="Ключевые метрики",
                metrics=[
                    _metric("positions", "Позиции", str(int(totals.get("positions", 0)))),
                    _metric(
                        "at_risk",
                        "Под риском",
                        str(int(totals.get("positions_at_risk", 0))),
                        "warning" if int(totals.get("positions_at_risk", 0)) else "positive",
                    ),
                    _metric(
                        "shortage",
                        "Дефицит",
                        f"{_qty(totals.get('total_shortage_qty'))} шт.",
                        (
                            "critical"
                            if float(totals.get("total_shortage_qty", 0) or 0) > 0
                            else "positive"
                        ),
                    ),
                    _metric(
                        "coverage",
                        "Среднее покрытие",
                        f"{_qty(totals.get('avg_coverage_months'))} мес.",
                    ),
                ],
            ),
            _section(
                section_type="reserve_table_preview",
                title="Ключевые позиции",
                rows=_reserve_rows_preview(calculation.rows),
            ),
        ]
        if warnings:
            sections.append(
                _section(
                    section_type="warning_block",
                    title="Ограничения",
                    items=[warning.message for warning in warnings],
                )
            )
        return AssistantAnswerDraft(
            intent="reserve_calculation",
            status="completed" if not warnings else "partial",
            confidence=0.91 if not warnings else 0.78,
            title="Расчёт резерва выполнен" if is_recalculation else "Сохранённый резерв",
            summary=sections[0]["body"] or "",
            sections=sections,
            source_refs=source_refs,
            tool_calls=executions,
            followups=_generic_followups("reserve_calculation", bundle),
            warnings=warnings,
            context_used=bundle.context,
        )

    if bundle.route.intent == "reserve_explanation":
        payload = tool_map["get_reserve_explanation"].payload
        if payload is None:
            return AssistantAnswerDraft(
                intent="reserve_explanation",
                status="needs_clarification",
                confidence=0.4,
                title="Объяснение не собрано",
                summary="Не удалось однозначно определить reserve row для объяснения.",
                sections=[
                    _section(
                        section_type="warning_block",
                        title="Что мешает объяснению",
                        items=[warning.message for warning in warnings]
                        or ["Уточните SKU или клиента."],
                    )
                ],
                source_refs=source_refs,
                tool_calls=executions,
                followups=_generic_followups("reserve_explanation", bundle),
                warnings=warnings,
                context_used=bundle.context,
            )
        row = payload["row"]
        warning_items = list(row.explanation_payload.get("warnings", [])) + [
            warning.message for warning in warnings
        ]
        sections = [
            _section(
                section_type="narrative",
                title="Почему позиция в риске",
                body=(
                    f"{row.article} для {row.client_name} имеет статус {_localize_status_code(row.status)}: {_localize_status_reason(row.status_reason)}. "
                    f"Спрос {_qty(row.demand_per_month)} шт./мес., цель {_qty(row.target_reserve_qty)} шт., "
                    f"доступно {_qty(row.available_qty)} шт."
                ),
            ),
            _section(
                section_type="metric_summary",
                title="Основание расчёта",
                metrics=[
                    _metric("fallback", "Уровень fallback", row.fallback_level),
                    _metric("basis", "Основа спроса", row.demand_basis_type),
                    _metric("coverage", "Покрытие", f"{_qty(row.coverage_months)} мес."),
                    _metric("shortage", "Дефицит", f"{_qty(row.shortage_qty)} шт.", "critical"),
                ],
            ),
        ]
        if warning_items:
            sections.append(
                _section(
                    section_type="warning_block",
                    title="Что важно учесть",
                    items=[_localize_signal(str(item)) for item in warning_items],
                )
            )
        return AssistantAnswerDraft(
            intent="reserve_explanation",
            status="completed" if not warnings else "partial",
            confidence=0.9 if row.fallback_level == "client_sku" else 0.76,
            title=f"Объяснение по {row.article}",
            summary=sections[0]["body"] or "",
            sections=sections,
            source_refs=source_refs,
            tool_calls=executions,
            followups=_generic_followups("reserve_explanation", bundle),
            warnings=warnings,
            context_used=bundle.context,
        )

    if bundle.route.intent == "sku_summary":
        detail = tool_map["get_sku_summary"].payload
        if detail is None:
            return _compose_unsupported(bundle)
        reserve_summary = detail.reserve_summary
        sections = [
            _section(
                section_type="narrative",
                title="Текущая ситуация",
                body=(
                    f"По SKU {detail.sku.article} ({detail.sku.name}) "
                    f"дефицит {_qty(reserve_summary.shortage_qty_total if reserve_summary else 0)} шт., "
                    f"затронуто клиентов {reserve_summary.affected_clients_count if reserve_summary else 0}."
                ),
            ),
            _section(
                section_type="metric_summary",
                title="SKU в цифрах",
                metrics=[
                    _metric(
                        "free_stock",
                        "Свободный остаток",
                        f"{_qty(detail.stock.free_stock if detail.stock else 0)} шт.",
                    ),
                    _metric("inbound", "Входящие поставки", str(len(detail.inbound))),
                    _metric(
                        "coverage",
                        "Среднее покрытие",
                        f"{_qty(reserve_summary.avg_coverage_months if reserve_summary else None)} мес.",
                    ),
                    _metric(
                        "clients",
                        "Клиентов под риском",
                        str(reserve_summary.affected_clients_count if reserve_summary else 0),
                    ),
                ],
            ),
            _section(
                section_type="reserve_table_preview",
                title="Клиентский сплит",
                rows=[
                    {
                        "clientName": item.client_name,
                        "share": item.share,
                        "shortageQty": item.shortage_qty,
                        "coverageMonths": item.coverage_months,
                        "status": item.status,
                    }
                    for item in detail.client_split[:5]
                ],
            ),
        ]
        return AssistantAnswerDraft(
            intent="sku_summary",
            status="completed" if not warnings else "partial",
            confidence=0.88 if reserve_summary else 0.72,
            title=f"SKU {detail.sku.article}",
            summary=sections[0]["body"] or "",
            sections=sections,
            source_refs=source_refs,
            tool_calls=executions,
            followups=_generic_followups("sku_summary", bundle),
            warnings=warnings,
            context_used=bundle.context,
        )

    if bundle.route.intent in {"client_summary", "diy_coverage_check"}:
        payload = tool_map["get_client_summary"].payload
        if payload is None:
            dashboard = tool_map.get("get_dashboard_summary")
            summary = "Не удалось выбрать конкретного клиента. Показываю ближайшую общую картину по DIY-портфелю."
            sections = [
                _section(section_type="narrative", title="Что не определилось", body=summary),
            ]
            if dashboard and dashboard.payload is not None:
                overview = dashboard.payload
                sections.append(
                    _section(
                        section_type="metric_summary",
                        title="Общая сводка",
                        metrics=[
                            _metric(
                                "positions_at_risk",
                                "Под риском",
                                str(overview.summary.positions_at_risk),
                                "warning",
                            ),
                            _metric(
                                "shortage",
                                "Дефицит",
                                f"{_qty(overview.summary.total_shortage_qty)} шт.",
                                "critical",
                            ),
                        ],
                    )
                )
            return AssistantAnswerDraft(
                intent=bundle.route.intent,  # type: ignore[arg-type]
                status="needs_clarification",
                confidence=0.48,
                title="Нужен клиент или pinned context",
                summary=summary,
                sections=sections,
                source_refs=source_refs,
                tool_calls=executions,
                followups=_generic_followups(bundle.route.intent, bundle),
                warnings=warnings,
                context_used=bundle.context,
            )
        detail = payload["detail"]
        top_skus = payload["top_skus"]
        sections = [
            _section(
                section_type="narrative",
                title="Ситуация по клиенту",
                body=(
                    f"У {detail.name} сейчас {detail.critical_positions} critical и {detail.warning_positions} warning позиций. "
                    f"Суммарный дефицит {_qty(detail.shortage_qty)} шт., среднее покрытие {_qty(detail.coverage_months)} мес."
                ),
            ),
            _section(
                section_type="metric_summary",
                title="Ключевые показатели",
                metrics=[
                    _metric("critical", "Critical", str(detail.critical_positions), "critical"),
                    _metric("warning", "Warning", str(detail.warning_positions), "warning"),
                    _metric("shortage", "Дефицит", f"{_qty(detail.shortage_qty)} шт.", "critical"),
                    _metric("coverage", "Покрытие", f"{_qty(detail.coverage_months)} мес."),
                ],
            ),
            _section(
                section_type="reserve_table_preview",
                title="SKU с наибольшим риском",
                rows=[
                    {
                        "article": item.sku_code,
                        "productName": item.product_name,
                        "shortageQty": item.shortage_qty,
                        "coverageMonths": item.coverage_months,
                        "status": item.status,
                    }
                    for item in top_skus[:5]
                ],
            ),
        ]
        return AssistantAnswerDraft(
            intent=bundle.route.intent,  # type: ignore[arg-type]
            status="completed" if not warnings else "partial",
            confidence=0.86,
            title=f"DIY-клиент {detail.name}",
            summary=sections[0]["body"] or "",
            sections=sections,
            source_refs=source_refs,
            tool_calls=executions,
            followups=_generic_followups(bundle.route.intent, bundle),
            warnings=warnings,
            context_used=bundle.context,
        )

    if bundle.route.intent == "inbound_impact":
        rows = tool_map["get_inbound_impact"].payload or []
        total_impact = sum(getattr(item, "reserve_impact", 0) for item in rows)
        sections = [
            _section(
                section_type="narrative",
                title="Поставки с наибольшим эффектом",
                body=(
                    f"Сейчас наиболее релевантны {len(rows)} входящих поставок. "
                    f"Потенциальный relief по текущей выборке — {_qty(total_impact)} шт."
                ),
            ),
            _section(
                section_type="metric_summary",
                title="Inbound impact",
                metrics=[
                    _metric("deliveries", "Поставок", str(len(rows))),
                    _metric("impact", "Reserve impact", f"{_qty(total_impact)} шт.", "positive"),
                ],
            ),
            _section(
                section_type="reserve_table_preview",
                title="Ключевые поставки",
                rows=[
                    {
                        "article": item.article,
                        "productName": item.sku_name,
                        "eta": item.eta,
                        "status": item.status,
                        "reserveImpact": item.reserve_impact,
                    }
                    for item in rows[:6]
                ],
            ),
        ]
        return AssistantAnswerDraft(
            intent="inbound_impact",
            status="completed" if rows else "partial",
            confidence=0.82 if rows else 0.6,
            title="Влияние входящих поставок",
            summary=sections[0]["body"] or "",
            sections=sections,
            source_refs=source_refs,
            tool_calls=executions,
            followups=_generic_followups("inbound_impact", bundle),
            warnings=warnings,
            context_used=bundle.context,
        )

    if bundle.route.intent == "stock_risk_summary":
        rows = tool_map["get_stock_coverage"].payload or []
        total_shortage = sum(getattr(item, "shortage_qty_total", 0) for item in rows)
        sections = [
            _section(
                section_type="narrative",
                title="Риск склада",
                body=(
                    f"По текущей выборке рискованных позиций {len(rows)}, суммарный дефицит {_qty(total_shortage)} шт."
                ),
            ),
            _section(
                section_type="metric_summary",
                title="Ключевые метрики",
                metrics=[
                    _metric(
                        "positions", "Позиции", str(len(rows)), "warning" if rows else "positive"
                    ),
                    _metric(
                        "shortage",
                        "Дефицит",
                        f"{_qty(total_shortage)} шт.",
                        "critical" if total_shortage else "positive",
                    ),
                ],
            ),
            _section(
                section_type="reserve_table_preview",
                title="Низкое покрытие",
                rows=[
                    {
                        "article": item.article,
                        "productName": item.product_name,
                        "coverageMonths": item.coverage_months,
                        "shortageQty": item.shortage_qty_total,
                        "status": item.worst_status,
                    }
                    for item in rows[:6]
                ],
            ),
        ]
        return AssistantAnswerDraft(
            intent="stock_risk_summary",
            status="completed" if rows else "partial",
            confidence=0.84,
            title="Сводка по stock risk",
            summary=sections[0]["body"] or "",
            sections=sections,
            source_refs=source_refs,
            tool_calls=executions,
            followups=_generic_followups("stock_risk_summary", bundle),
            warnings=warnings,
            context_used=bundle.context,
        )

    if bundle.route.intent == "sales_summary":
        payload = tool_map["get_sales_summary"].payload or {}
        row_count = int(payload.get("row_count") or 0) if isinstance(payload, dict) else 0
        quantity = float(payload.get("quantity") or 0) if isinstance(payload, dict) else 0
        revenue = float(payload.get("revenue") or 0) if isinstance(payload, dict) else 0
        period = (
            f"{payload.get('date_from')} - {payload.get('date_to')}"
            if isinstance(payload, dict)
            else "период не определён"
        )
        sections = [
            _section(
                section_type="narrative",
                title="Продажи",
                body=(
                    f"За период {period} найдено {row_count} строк продаж: "
                    f"{_qty(quantity)} шт. и {_metric_value(revenue, 'rub')} выручки."
                ),
            ),
            _section(
                section_type="metric_summary",
                title="Ключевые метрики",
                metrics=[
                    _metric("quantity", "Количество", f"{_qty(quantity)} шт."),
                    _metric(
                        "revenue",
                        "Выручка",
                        _metric_value(revenue, "rub"),
                        "positive" if revenue else "neutral",
                    ),
                    _metric("rows", "Строк", str(row_count)),
                ],
            ),
        ]
        return AssistantAnswerDraft(
            intent="sales_summary",
            status="completed" if row_count else "partial",
            confidence=0.84 if row_count else 0.58,
            title="Сводка продаж",
            summary=sections[0]["body"] or "",
            sections=sections,
            source_refs=source_refs,
            tool_calls=executions,
            followups=_generic_followups("sales_summary", bundle),
            warnings=warnings,
            context_used=bundle.context,
        )

    if bundle.route.intent == "analytics_slice":
        payload = tool_map["get_analytics_slice"].payload or {}
        rows = payload.get("rows") if isinstance(payload, dict) else []
        metrics = payload.get("metrics") if isinstance(payload, dict) else []
        dimensions = payload.get("dimensions") if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            rows = []
        if not isinstance(metrics, list):
            metrics = []
        if not isinstance(dimensions, list):
            dimensions = []
        totals = payload.get("totals") if isinstance(payload, dict) else {}
        if not isinstance(totals, dict):
            totals = {}
        if isinstance(payload, dict) and payload.get("status") == "unsupported":
            supported_metrics = ", ".join(payload.get("supported_metrics") or [])
            supported_dimensions = ", ".join(payload.get("supported_dimensions") or [])
            sections = [
                _section(
                    section_type="warning_block",
                    title="Срез пока не поддерживается",
                    items=[
                        f"Доступные метрики: {supported_metrics}",
                        f"Доступные измерения: {supported_dimensions}",
                    ],
                )
            ]
            return AssistantAnswerDraft(
                intent="analytics_slice",
                status="needs_clarification",
                response_type="clarification",
                confidence=0.58,
                title="Нужно выбрать поддерживаемый срез",
                summary="Такой срез пока не поддерживается. Ниже доступны метрики и измерения.",
                sections=sections,
                source_refs=source_refs,
                tool_calls=executions,
                followups=_generic_followups("analytics_slice", bundle),
                warnings=warnings,
                context_used=bundle.context,
                missing_fields=[],
                suggested_chips=[
                    "выручка по клиентам",
                    "продажи в штуках по категориям",
                    "дефицит по SKU",
                ],
                pending_intent="analytics_slice",
            )
        primary_metric = str(metrics[0]) if metrics else "metric"
        top_row = rows[0] if rows else {}
        top_label = (
            " / ".join(str(top_row.get(dimension) or "—") for dimension in dimensions)
            if top_row
            else "нет данных"
        )
        top_value = top_row.get(primary_metric) if isinstance(top_row, dict) else None
        primary_unit = (
            METRIC_CATALOG.get(primary_metric).unit if primary_metric in METRIC_CATALOG else "qty"
        )
        metric_cards = [
            _metric(
                str(metric),
                (
                    METRIC_CATALOG.get(str(metric)).label
                    if str(metric) in METRIC_CATALOG
                    else str(metric)
                ),
                _metric_value(
                    totals.get(
                        str(metric), top_row.get(str(metric), 0) if isinstance(top_row, dict) else 0
                    ),
                    (
                        METRIC_CATALOG.get(str(metric)).unit
                        if str(metric) in METRIC_CATALOG
                        else "qty"
                    ),
                ),
                "positive" if float(totals.get(str(metric), 0) or 0) else "neutral",
            )
            for metric in metrics
        ]
        sections = [
            _section(
                section_type="narrative",
                title="Аналитический срез",
                body=(
                    f"По срезу {', '.join(map(str, metrics))} × {', '.join(map(str, dimensions))} "
                    f"получено {len(rows)} строк. Лидер: {top_label} — {_metric_value(top_value or 0, primary_unit)}."
                    if rows
                    else "По выбранному срезу данных не найдено."
                ),
            ),
            _section(
                section_type="metric_summary",
                title="Итого",
                metrics=metric_cards,
            ),
            _section(
                section_type="reserve_table_preview",
                title="Топ строк",
                rows=rows[:8],
            ),
        ]
        return AssistantAnswerDraft(
            intent="analytics_slice",
            status="completed" if rows else "partial",
            confidence=0.86 if rows else 0.58,
            title="Аналитический срез",
            summary=sections[0]["body"] or "",
            sections=sections,
            source_refs=source_refs,
            tool_calls=executions,
            followups=_generic_followups("analytics_slice", bundle),
            warnings=warnings,
            context_used=bundle.context,
        )

    if bundle.route.intent == "period_comparison":
        payload = tool_map["get_period_comparison"].payload or {}
        current_value = float(payload.get("current_value") or 0) if isinstance(payload, dict) else 0
        previous_value = (
            float(payload.get("previous_value") or 0) if isinstance(payload, dict) else 0
        )
        delta = float(payload.get("delta") or 0) if isinstance(payload, dict) else 0
        delta_pct = payload.get("delta_pct") if isinstance(payload, dict) else None
        metric = str(payload.get("metric") or "revenue") if isinstance(payload, dict) else "revenue"
        unit = "rub" if metric == "revenue" else "qty"
        delta_text = "н/д" if delta_pct is None else f"{float(delta_pct):.1f}%"
        sections = [
            _section(
                section_type="narrative",
                title="Сравнение периодов",
                body=(
                    f"Текущий период: {_metric_value(current_value, unit)}; "
                    f"предыдущий период: {_metric_value(previous_value, unit)}. "
                    f"Изменение: {_metric_value(delta, unit)} ({delta_text})."
                ),
            ),
            _section(
                section_type="metric_summary",
                title="Динамика",
                metrics=[
                    _metric("current", "Текущий", _metric_value(current_value, unit)),
                    _metric("previous", "Предыдущий", _metric_value(previous_value, unit)),
                    _metric(
                        "delta",
                        "Разница",
                        _metric_value(delta, unit),
                        "positive" if delta >= 0 else "warning",
                    ),
                    _metric("delta_pct", "Изменение", delta_text),
                ],
            ),
        ]
        return AssistantAnswerDraft(
            intent="period_comparison",
            status="completed" if payload.get("status") == "completed" else "partial",  # type: ignore[union-attr]
            confidence=0.82 if payload.get("status") == "completed" else 0.56,  # type: ignore[union-attr]
            title="Сравнение с прошлым периодом",
            summary=sections[0]["body"] or "",
            sections=sections,
            source_refs=source_refs,
            tool_calls=executions,
            followups=_generic_followups("period_comparison", bundle),
            warnings=warnings,
            context_used=bundle.context,
        )

    if bundle.route.intent == "upload_status_summary":
        details = tool_map["get_upload_status"].payload or []
        dashboard = tool_map.get("get_dashboard_summary")
        freshness_hours = (
            dashboard.payload.freshness.freshness_hours if dashboard and dashboard.payload else None
        )
        sections = [
            _section(
                section_type="narrative",
                title="Статус данных",
                body=(
                    f"Проверено {len(details)} загрузок. "
                    f"Последний известный freshness lag — {_qty(freshness_hours)} ч."
                ),
            ),
            _section(
                section_type="metric_summary",
                title="Ingestion и freshness",
                metrics=[
                    _metric("uploads", "Загрузок", str(len(details))),
                    _metric("freshness", "Freshness", f"{_qty(freshness_hours)} ч."),
                ],
            ),
            _section(
                section_type="reserve_table_preview",
                title="Последние загрузки",
                rows=[
                    {
                        "fileName": detail.file.file_name,
                        "status": detail.file.status,
                        "rows": detail.file.total_rows,
                        "issues": detail.file.issue_counts.total,
                    }
                    for detail in details[:5]
                ],
            ),
        ]
        return AssistantAnswerDraft(
            intent="upload_status_summary",
            status="completed" if details else "partial",
            confidence=0.8,
            title="Freshness и статус загрузок",
            summary=sections[0]["body"] or "",
            sections=sections,
            source_refs=source_refs,
            tool_calls=executions,
            followups=_generic_followups("upload_status_summary", bundle),
            warnings=warnings,
            context_used=bundle.context,
        )

    if bundle.route.intent == "quality_issue_summary":
        issues = tool_map["get_quality_issues"].payload or []
        sections = [
            _section(
                section_type="narrative",
                title="Quality issues",
                body=f"Сейчас найдено {len(issues)} релевантных quality issues, которые могут влиять на интерпретацию результата.",
            ),
            _section(
                section_type="reserve_table_preview",
                title="Открытые проблемы",
                rows=[
                    {
                        "type": issue.type,
                        "severity": issue.severity,
                        "entity": issue.entity,
                        "source": issue.source,
                    }
                    for issue in issues[:6]
                ],
            ),
        ]
        return AssistantAnswerDraft(
            intent="quality_issue_summary",
            status="completed" if issues else "partial",
            confidence=0.78,
            title="Сводка по качеству данных",
            summary=sections[0]["body"] or "",
            sections=sections,
            source_refs=source_refs,
            tool_calls=executions,
            followups=_generic_followups("quality_issue_summary", bundle),
            warnings=warnings,
            context_used=bundle.context,
        )

    if bundle.route.intent == "management_report_summary":
        payload = tool_map["get_management_report"].payload or {}
        latest = payload.get("latest_import") if isinstance(payload, dict) else None
        if latest is None:
            return AssistantAnswerDraft(
                intent="management_report_summary",
                status="partial",
                confidence=0.46,
                title="Управленческий отчёт не найден",
                summary="В БД нет импортированного управленческого отчёта, поэтому ответ по цифрам невозможен.",
                sections=[
                    _section(
                        section_type="warning_block",
                        title="Что нужно сделать",
                        items=[warning.message for warning in warnings]
                        or ["Импортируйте XLSX управленческого отчёта."],
                    )
                ],
                source_refs=source_refs,
                tool_calls=executions,
                followups=_generic_followups("management_report_summary", bundle),
                warnings=warnings,
                context_used=bundle.context,
            )

        summary_payload = payload.get("summary")
        metrics = payload.get("metrics") or []
        answer_focus = payload.get("answer_focus") if isinstance(payload, dict) else None
        key_metrics = getattr(summary_payload, "key_metrics", []) if summary_payload else []
        organization_units = (
            getattr(summary_payload, "organization_units", []) if summary_payload else []
        )
        metric_counts_by_sheet = (
            getattr(summary_payload, "metric_counts_by_sheet", {}) if summary_payload else {}
        )
        if (
            isinstance(answer_focus, dict)
            and answer_focus.get("kind") == "top_product_group_earnings"
        ):
            year = answer_focus.get("year") or "выбранный год"
            ranked_rows = (
                answer_focus.get("rows") if isinstance(answer_focus.get("rows"), list) else []
            )
            try:
                requested_rank = max(int(answer_focus.get("requestedRank") or 1), 1)
            except (TypeError, ValueError):
                requested_rank = 1
            selected_row = (
                ranked_rows[requested_rank - 1] if len(ranked_rows) >= requested_rank else None
            )
            metric_rows = [
                {
                    "rank": index + 1,
                    "dimensionName": item.get("dimensionName"),
                    "estimatedProfit": _metric_value(item.get("estimatedProfitRub"), "rub"),
                    "revenue": _metric_value(item.get("revenue"), "rub"),
                    "profitability": _metric_value(item.get("profitabilityPct"), "pct"),
                    "metricYear": item.get("metricYear") or "—",
                }
                for index, item in enumerate(ranked_rows[:8])
                if isinstance(item, dict)
            ]
            if isinstance(selected_row, dict):
                if requested_rank == 1:
                    summary_text = (
                        f"Если считать заработок как выручка × рентабельность, то в {year} больше всего "
                        f"заработали на товарной группе {selected_row.get('dimensionName')}: "
                        f"{_metric_value(selected_row.get('estimatedProfitRub'), 'rub')}."
                    )
                else:
                    summary_text = (
                        f"{requested_rank}-е место по расчётному заработку в {year}: "
                        f"{selected_row.get('dimensionName')} — "
                        f"{_metric_value(selected_row.get('estimatedProfitRub'), 'rub')}."
                    )
            else:
                summary_text = f"В управленческом отчёте нет {requested_rank}-го места по расчётному заработку за {year}."
            sections = [
                _section(
                    section_type="narrative",
                    title="Ответ",
                    body=summary_text,
                ),
                _section(
                    section_type="reserve_table_preview",
                    title=f"Топ товарных групп по расчётному заработку, {year}",
                    rows=metric_rows,
                ),
                _section(
                    section_type="warning_block",
                    title="Как считал",
                    items=[
                        "В загруженном отчёте нет прямой прибыли в рублях по конкретным товарам.",
                        "Поэтому запрос 'на каком товаре заработали больше всего' считается на уровне товарных групп как выручка × рентабельность, %.",
                    ],
                ),
            ]
            return AssistantAnswerDraft(
                intent="management_report_summary",
                status="completed" if selected_row is not None else "partial",
                confidence=0.9 if selected_row is not None else 0.62,
                title=(
                    f"Где заработали больше всего в {year}"
                    if requested_rank == 1
                    else f"{requested_rank}-е место по заработку, {year}"
                ),
                summary=summary_text,
                sections=sections,
                source_refs=source_refs,
                tool_calls=executions,
                followups=_generic_followups("management_report_summary", bundle),
                warnings=warnings,
                context_used=bundle.context,
            )

        if (
            isinstance(answer_focus, dict)
            and answer_focus.get("kind") == "top_product_group_profitability"
        ):
            year = answer_focus.get("year") or "выбранный год"
            try:
                requested_rank = max(int(answer_focus.get("requestedRank") or 1), 1)
            except (TypeError, ValueError):
                requested_rank = 1
            selected_metric = (
                metrics[requested_rank - 1] if len(metrics) >= requested_rank else None
            )
            metric_rows = [
                {
                    "rank": index + 1,
                    "dimensionName": item.dimension_name,
                    "profitability": _metric_value(item.metric_value, item.metric_unit),
                    "metricYear": item.metric_year or "—",
                }
                for index, item in enumerate(metrics[:8])
            ]
            if selected_metric is not None:
                selected_value = _metric_value(
                    selected_metric.metric_value, selected_metric.metric_unit
                )
                if requested_rank == 1:
                    summary_text = (
                        f"По рентабельности в {year} самая выгодная товарная группа — "
                        f"{selected_metric.dimension_name}: {selected_value}."
                    )
                else:
                    summary_text = (
                        f"{requested_rank}-е место по рентабельности в {year}: "
                        f"{selected_metric.dimension_name} — {selected_value}."
                    )
            else:
                summary_text = f"В управленческом отчёте нет {requested_rank}-го места по рентабельности товарных групп за {year}."
            sections = [
                _section(
                    section_type="narrative",
                    title="Ответ",
                    body=summary_text,
                ),
                _section(
                    section_type="reserve_table_preview",
                    title=f"Топ товарных групп по рентабельности, {year}",
                    rows=metric_rows,
                ),
                _section(
                    section_type="warning_block",
                    title="Как трактовать",
                    items=[
                        "Запрос 'самая выгодная ТГ' трактуется как максимум рентабельности, %.",
                        "Это не ранжирование по абсолютной прибыли в рублях: такой метрики в текущем импорте нет.",
                    ],
                ),
            ]
            return AssistantAnswerDraft(
                intent="management_report_summary",
                status="completed" if selected_metric is not None else "partial",
                confidence=0.91 if selected_metric is not None else 0.62,
                title=(
                    f"Самая выгодная ТГ в {year}"
                    if requested_rank == 1
                    else f"{requested_rank}-е место по рентабельности ТГ, {year}"
                ),
                summary=summary_text,
                sections=sections,
                source_refs=source_refs,
                tool_calls=executions,
                followups=_generic_followups("management_report_summary", bundle),
                warnings=warnings,
                context_used=bundle.context,
            )

        top_key_metrics = [
            _metric(
                f"key_{index}",
                item.label,
                _metric_value(item.value, item.unit),
                "positive" if item.unit in {"rub", "ratio"} else "neutral",
            )
            for index, item in enumerate(key_metrics[:4])
        ]
        metric_rows = [
            {
                "sheetName": item.sheet_name,
                "dimensionName": item.dimension_name,
                "metricName": item.metric_name,
                "metricYear": item.metric_year or "—",
                "metricValue": _metric_value(item.metric_value, item.metric_unit),
            }
            for item in metrics[:8]
        ]
        sections = [
            _section(
                section_type="narrative",
                title="Что загружено",
                body=(
                    f"В БД подключён управленческий отчёт {latest.file_name}: "
                    f"{latest.raw_row_count} raw-строк, {latest.metric_count} нормализованных метрик, "
                    f"{len(organization_units)} подразделения. Эти данные используются как отдельный контекст, "
                    "не как SKU/reserve facts."
                ),
            ),
            _section(
                section_type="metric_summary",
                title="Ключевые показатели отчёта",
                metrics=top_key_metrics,
            ),
            _section(
                section_type="reserve_table_preview",
                title="Релевантные строки по вопросу",
                rows=metric_rows,
            ),
            _section(
                section_type="source_list",
                title="Покрытие листов",
                items=[
                    f"{sheet}: {count} метрик"
                    for sheet, count in sorted(metric_counts_by_sheet.items())
                ],
            ),
        ]
        return AssistantAnswerDraft(
            intent="management_report_summary",
            status="completed" if metrics or key_metrics else "partial",
            confidence=0.87 if metrics or key_metrics else 0.65,
            title="Управленческий отчёт MAGAMAX",
            summary=sections[0]["body"] or "",
            sections=sections,
            source_refs=source_refs,
            tool_calls=executions,
            followups=_generic_followups("management_report_summary", bundle),
            warnings=warnings,
            context_used=bundle.context,
        )

    return _compose_unsupported(bundle)


FOLLOWUP_DETAIL_TOKENS = (
    "подробнее",
    "подробней",
    "развернут",
    "развёрнут",
    "детал",
    "расшифр",
    "покажи строки",
    "покажи таблицу",
    "дай данные",
    "больше данных",
)

FOLLOWUP_CONTEXT_TOKENS = (
    "а по ",
    "а для ",
    "а теперь",
    "теперь по ",
    "в штуках",
    "в шт",
    "по категориям",
    "по категории",
    "по sku",
    "по артикулам",
    "прошлый месяц",
    "прошлым месяц",
    "только проблем",
    "проблемные",
    "второе место",
    "второй",
    "вторая",
    "вторую",
    "2 место",
    "2-е место",
    "третье место",
    "третий",
    "третья",
    "3 место",
    "3-е место",
    "следующее",
    "следующий",
    "следующая",
    "кто дальше",
    "что дальше",
    "а дальше",
)

FOLLOWUP_REPAIR_TOKENS = (
    "теперь ответ",
    "теперь ответишь",
    "ответишь",
    "ответь",
    "попробуй",
    "попробуй еще",
    "попробуй ещё",
    "еще раз",
    "ещё раз",
    "ну а теперь",
)


def _last_domain_history_item(history: list[dict[str, object]]) -> dict[str, object] | None:
    for item in reversed(history):
        intent = str(item.get("intent") or "")
        if item.get("role") == "assistant" and intent not in {
            "",
            "free_chat",
            "unsupported_or_ambiguous",
        }:
            return item
    return None


def _previous_user_text(history: list[dict[str, object]]) -> str | None:
    for item in reversed(history):
        if item.get("role") == "user":
            text = str(item.get("text") or "").strip()
            if text:
                return text
    return None


def _previous_domain_tool_question(item: dict[str, object] | None) -> str | None:
    if item is None:
        return None
    tool_calls = item.get("toolCalls")
    if not isinstance(tool_calls, list):
        return None
    for tool_call in reversed(tool_calls):
        if not isinstance(tool_call, dict):
            continue
        arguments = tool_call.get("arguments")
        if not isinstance(arguments, dict):
            continue
        question = str(arguments.get("question") or "").strip()
        if question:
            return question
    return None


def _previous_substantive_domain_tool_question(history: list[dict[str, object]]) -> str | None:
    for item in reversed(history):
        intent = str(item.get("intent") or "")
        if item.get("role") != "assistant" or intent in {
            "",
            "free_chat",
            "unsupported_or_ambiguous",
        }:
            continue
        question = _previous_domain_tool_question(item)
        if not question:
            continue
        # Skip repair/meta questions that accidentally produced a generic domain answer.
        if _is_repair_followup_request(question) or len(question.strip()) < 30:
            continue
        return question
    return None


def _previous_contextual_user_text(history: list[dict[str, object]]) -> str | None:
    for item in reversed(history):
        if item.get("role") != "user":
            continue
        text = str(item.get("text") or "").strip()
        if text and _is_repair_followup_request(text):
            continue
        if text and _is_contextual_followup_request(text):
            return text
    return None


def _is_followup_detail_request(question: str) -> bool:
    q = question.lower()
    return any(token in q for token in FOLLOWUP_DETAIL_TOKENS)


def _is_contextual_followup_request(question: str) -> bool:
    q = question.lower().strip()
    return _is_followup_detail_request(q) or any(token in q for token in FOLLOWUP_CONTEXT_TOKENS)


def _is_repair_followup_request(question: str) -> bool:
    q = question.lower().strip()
    return any(token in q for token in FOLLOWUP_REPAIR_TOKENS)


def _apply_history_fallback_plan(
    *,
    question: str,
    deterministic_intent: str,
    planned_intent: str | None,
    planned_tool_question: str | None,
    history: list[dict[str, object]],
) -> tuple[str, str]:
    intent = planned_intent or deterministic_intent
    tool_question = planned_tool_question or question

    if (
        deterministic_intent not in {"free_chat", "unsupported_or_ambiguous"}
        and intent == "unsupported_or_ambiguous"
    ):
        intent = deterministic_intent
        tool_question = question

    previous_contextual_user_text = _previous_contextual_user_text(history)
    should_repair_previous_followup = (
        _is_repair_followup_request(question) and previous_contextual_user_text is not None
    )
    should_apply_context = (
        _is_contextual_followup_request(question) or should_repair_previous_followup
    )

    if deterministic_intent in {"free_chat", "unsupported_or_ambiguous"} and should_apply_context:
        previous_domain = _last_domain_history_item(history)
        if previous_domain is not None:
            intent = str(previous_domain.get("intent") or intent)
            base_question = (
                _previous_substantive_domain_tool_question(history)
                or _previous_domain_tool_question(previous_domain)
                or _previous_user_text(history)
            )
            semantic_followup = (
                previous_contextual_user_text if should_repair_previous_followup else question
            )
            if base_question:
                tool_question = f"{base_question}. Follow-up: {semantic_followup}"
    return intent, tool_question


def _tool_plan(intent: str) -> list[str]:
    return get_default_tool_registry().default_plan_for_intent(intent)


def _is_reserve_recalculation_request(question: str) -> bool:
    q = question.lower()
    return any(
        token in q
        for token in (
            "пересчитай",
            "перерассчитай",
            "рассчитай",
            "посчитай",
            "calculate",
            "recalculate",
        )
    )


def _execution_plan(
    intent: str,
    planned_tool_names: list[str],
    question: str,
    params: dict[str, object] | None = None,
) -> list[str]:
    """Keep required tools deterministic, while allowing LLM to add safe support tools."""
    force_tool = str((params or {}).get("_force_tool") or "")
    if intent == "reserve_calculation" and (
        _is_reserve_recalculation_request(question) or force_tool == "calculate_reserve"
    ):
        required = ["calculate_reserve", "get_quality_issues", "get_upload_status"]
    else:
        required = _tool_plan(intent)
    if intent in {"free_chat", "unsupported_or_ambiguous"}:
        return []
    allowed = set(required)
    if intent in {
        "reserve_calculation",
        "reserve_explanation",
        "sku_summary",
        "client_summary",
        "diy_coverage_check",
        "inbound_impact",
        "stock_risk_summary",
    }:
        allowed.update({"get_quality_issues", "get_upload_status", "get_dashboard_summary"})
    if (
        intent == "reserve_calculation"
        and not _is_reserve_recalculation_request(question)
        and force_tool != "calculate_reserve"
    ):
        allowed.discard("calculate_reserve")
    if intent == "management_report_summary":
        allowed.update({"get_upload_status", "get_quality_issues"})

    plan = list(required)
    for tool_name in planned_tool_names:
        if tool_name in allowed and tool_name not in plan:
            plan.append(tool_name)
    return plan


def execute_assistant_query(
    db: Session,
    settings: Settings,
    *,
    payload: AssistantQueryRequest,
    created_by_id: str | None,
    current_user: User | None = None,
    history: list[dict[str, object]] | None = None,
) -> AssistantResponse:
    trace_id = generate_id("trace")
    question = payload.prompt_text()
    history_items = history or []
    session_state = derive_state_from_history(history_items)  # type: ignore[arg-type]
    deterministic_route = route_question(db, question)
    plan = plan_route_with_provider(
        settings,
        question=question,
        deterministic_intent=deterministic_route.intent,
        history=history_items,
    )
    state_params = resolve_followup_from_state(question, session_state, plan.params)
    if state_params.get("_pending_intent") and plan.intent in {
        "free_chat",
        "unsupported_or_ambiguous",
    }:
        plan.intent = str(state_params["_pending_intent"])  # type: ignore[assignment]
    if state_params.get("_followup_intent") and (
        plan.intent in {"free_chat", "unsupported_or_ambiguous"}
        or _is_contextual_followup_request(question)
    ):
        plan.intent = str(state_params["_followup_intent"])  # type: ignore[assignment]
    planned_intent, tool_question = _apply_history_fallback_plan(
        question=question,
        deterministic_intent=deterministic_route.intent,
        planned_intent=plan.intent,
        planned_tool_question=plan.tool_question,
        history=history_items,
    )
    route = route_question(
        db,
        tool_question,
        forced_intent=planned_intent,  # type: ignore[arg-type]
    )
    bundle = build_context_bundle(db, route=route, pinned_context=payload.context)
    registry = get_default_tool_registry()
    params = _params_from_route(
        question=tool_question,
        bundle=bundle,
        plan_params=plan.params,
        state_params=state_params,
    )
    business_clarification = _business_clarification_spec(question, session_state)
    if business_clarification:
        field_name, clarification_question, suggested_chips, pending_intent = business_clarification
        draft = _compose_business_clarification(
            intent=pending_intent,
            field_name=field_name,
            question=clarification_question,
            chips=suggested_chips,
            bundle=bundle,
        )
        draft.trace_metadata = _trace_metadata(
            resolved_intent=pending_intent,
            resolved_tool=None,
            missing_fields=[
                AssistantMissingField(
                    name=field_name,
                    label=field_name,
                    question=clarification_question,
                )
            ],
            clarification_reason="broad_business_question",
            source_refs_count=0,
        )
        token_usage = combine_token_usage(plan.token_usage)
        return _response_from_draft(
            payload=payload,
            draft=draft,
            provider_name="deterministic",
            token_usage=token_usage,
            trace_id=trace_id,
        )

    tool_names = _execution_plan(route.intent, plan.tool_names, tool_question, params)
    primary_tool_name = tool_names[0] if tool_names else None
    missing_fields: list[AssistantMissingField] = []
    if primary_tool_name:
        missing_fields.extend(registry.validate(primary_tool_name, params))
    for item in plan.missing_fields:
        field = AssistantMissingField(
            name=str(item.get("name") or item.get("field") or ""),
            label=str(item.get("label") or item.get("name") or item.get("field") or ""),
            question=str(item.get("question") or plan.followup_question or ""),
        )
        if field.name and all(existing.name != field.name for existing in missing_fields):
            missing_fields.append(field)
    session_state = merge_state(
        session_state,
        intent=route.intent,
        params=params,
        missing_fields=missing_fields,
        pending_question=question,
    )
    if missing_fields:
        draft = _compose_clarification(
            intent=route.intent,
            missing_fields=missing_fields,
            bundle=bundle,
        )
        draft.trace_metadata = _trace_metadata(
            resolved_intent=route.intent,
            resolved_tool=primary_tool_name,
            missing_fields=missing_fields,
            clarification_reason="required_fields_missing",
            source_refs_count=len(draft.source_refs),
        )
        draft, provider_name, _provider_warnings, finalize_usage = finalize_with_provider(
            settings, draft
        )
        token_usage = combine_token_usage(plan.token_usage, finalize_usage)
        return _response_from_draft(
            payload=payload,
            draft=draft,
            provider_name=provider_name,
            token_usage=token_usage,
            trace_id=trace_id,
        )

    executions: list[AssistantToolExecution] = []
    for tool_name in tool_names:
        spec = registry.lookup(tool_name)
        tool_params = (
            params if spec.intent == route.intent or tool_name == primary_tool_name else {}
        )
        executions.append(
            _dispatch_tool(
                db,
                spec=spec,
                bundle=bundle,
                params=tool_params,
                created_by_id=created_by_id,
                current_user=current_user,
            )
        )

    draft = _compose_answer(bundle, executions, question=question)
    draft.trace_metadata = _trace_metadata(
        resolved_intent=route.intent,
        resolved_tool=primary_tool_name,
        missing_fields=[],
        source_refs_count=len(draft.source_refs),
    )
    draft, provider_name, _provider_warnings, finalize_usage = finalize_with_provider(
        settings, draft
    )
    token_usage = combine_token_usage(plan.token_usage, finalize_usage)

    return _response_from_draft(
        payload=payload,
        draft=draft,
        provider_name=provider_name,
        token_usage=token_usage,
        trace_id=trace_id,
    )


def _response_from_draft(
    *,
    payload: AssistantQueryRequest,
    draft: AssistantAnswerDraft,
    provider_name: str,
    token_usage: object,
    trace_id: str,
) -> AssistantResponse:
    return AssistantResponse(
        answerId=generate_id("ans"),
        sessionId=payload.session_id,
        type=draft.response_type,  # type: ignore[arg-type]
        intent=draft.intent,
        status=draft.status,  # type: ignore[arg-type]
        confidence=round(draft.confidence, 2),
        title=draft.title,
        summary=draft.summary,
        sections=[AssistantAnswerSection(**section) for section in draft.sections],
        sourceRefs=[AssistantSourceRef(**item) for item in draft.source_refs],
        toolCalls=[
            AssistantToolCall(
                toolName=execution.tool_name,
                status=execution.status,  # type: ignore[arg-type]
                arguments=execution.arguments,
                summary=execution.summary,
                latencyMs=execution.latency_ms,
            )
            for execution in draft.tool_calls
        ],
        followups=[AssistantFollowupSuggestion(**item) for item in draft.followups],
        warnings=[
            AssistantWarning(
                code=warning.code,
                message=warning.message,
                severity=warning.severity,  # type: ignore[arg-type]
            )
            for warning in draft.warnings
        ],
        generatedAt=utc_now().isoformat(),
        traceId=trace_id,
        provider=provider_name,
        tokenUsage=AssistantTokenUsage(
            inputTokens=token_usage.input_tokens,  # type: ignore[attr-defined]
            outputTokens=token_usage.output_tokens,  # type: ignore[attr-defined]
            totalTokens=token_usage.total_tokens,  # type: ignore[attr-defined]
            estimatedCostUsd=token_usage.estimated_cost_usd,  # type: ignore[attr-defined]
            estimatedCostRub=token_usage.estimated_cost_rub,  # type: ignore[attr-defined]
        ),
        contextUsed=_context_schema(draft.context_used),
        missingFields=draft.missing_fields,
        suggestedChips=draft.suggested_chips,
        pendingIntent=draft.pending_intent,  # type: ignore[arg-type]
        traceMetadata=draft.trace_metadata,
    )
