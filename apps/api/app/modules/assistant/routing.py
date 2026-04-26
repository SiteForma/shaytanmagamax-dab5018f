from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.db.models import Category, ClientAlias, UploadFile
from apps.api.app.modules.assistant.domain import AssistantRoute, AssistantWarningData
from apps.api.app.modules.assistant.schemas import AssistantIntent
from apps.api.app.modules.mapping.service import (
    resolve_client_by_name_or_alias,
    resolve_sku_by_code_or_alias,
)

SKU_CODE_PATTERN = re.compile(r"\b[0-9A-Za-zА-Яа-я]+(?:-[0-9A-Za-zА-Яа-я]+)+\b")
MONTHS_PATTERN = re.compile(r"(\d+)\s*(?:месяц|месяца|месяцев|months?)", re.IGNORECASE)
SAFETY_PATTERN = re.compile(
    r"(?:safety|коэффициент|factor|запас)\s*[:=]?\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE
)
PRODUCT_GROUP_ABBR_PATTERN = re.compile(r"(?<![0-9a-zа-я])тг(?![0-9a-zа-я])", re.IGNORECASE)

DOMAIN_CHAT_TOKENS = (
    "magamax",
    "магамакс",
    "шайтан",
    "шайт",
    "консоль",
    "система",
    "данн",
    "сыр",
    "загруз",
    "ingestion",
    "upload",
    "mapping",
    "сопостав",
    "quality",
    "качество",
    "issue",
    "резерв",
    "reserve",
    "sku",
    "артикул",
    "клиент",
    "client",
    "diy",
    "сеть",
    "склад",
    "stock",
    "покрытие",
    "coverage",
    "дефицит",
    "shortage",
    "постав",
    "inbound",
    "eta",
    "категор",
    "category",
    "политик",
    "policy",
    "alias",
    "алиас",
    "отчет",
    "отчёт",
    "управлен",
    "товар",
    "товарн",
    "групп",
    "тг",
    "подраздел",
    "выруч",
    "заработ",
    "рентаб",
    "выгодн",
    "прибыл",
    "маржин",
    "пдз",
    "дебитор",
    "недопостав",
    "экспорт",
    "dashboard",
    "обзор",
    "расчет",
    "расчёт",
)

CONSOLE_USAGE_PHRASES = (
    "что ты умеешь",
    "как с тобой",
    "как тобой",
    "как лучше задавать",
    "какие вопросы",
    "помоги сформулировать",
    "помоги",
    "помощь",
    "help",
    "пример вопроса",
    "как пользоваться",
    "что можно спросить",
    "с чего начать",
    "что спросить",
    "что ты можешь",
    "что умеешь",
    "покажи примеры",
    "дай примеры",
)

MONTH_BUSINESS_TOKENS = (
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
)

YEAR_RESULT_PHRASES = (
    "как закрыли",
    "закрыли год",
    "год закрыли",
    "итоги года",
    "итоги 2024",
    "итоги 2025",
    "что по году",
    "что по 2024",
    "что по 2025",
    "как отработали год",
    "как в целом",
    "результаты года",
    "2024 год",
    "2025 год",
)

BROAD_BUSINESS_PHRASES = (
    "как дела",
    "что происходит",
    "что с",
    "где просели",
    "где выросли",
    "что просело",
    "что выросло",
    "что проблемное",
    "покажи проблемные",
    "что надо заказать",
    "что заказать",
    "кого заказать",
    "что в зоне риска",
    "зоне риска",
    "что хуже всего",
    "что лучше всего",
    "антитоп",
    "динамика",
    "сравни",
    "по клиентам",
    "по категориям",
    "по sku",
    "по артикулам",
)

EXTERNAL_TOPIC_TOKENS = (
    "погода",
    "политик",
    "новост",
    "рецепт",
    "анекдот",
    "евгения онегина",
    "онегин",
    "пушкин",
    "фильм",
    "сериал",
    "спорт",
    "гороскоп",
)


def _flatten_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _is_domain_chat(question: str) -> bool:
    return any(token in question for token in DOMAIN_CHAT_TOKENS) or any(
        phrase in question for phrase in CONSOLE_USAGE_PHRASES
    )


def _is_help_question(question: str) -> bool:
    return any(phrase in question for phrase in CONSOLE_USAGE_PHRASES)


def _is_external_question(question: str) -> bool:
    return any(token in question for token in EXTERNAL_TOPIC_TOKENS)


def _is_management_report_question(question: str) -> bool:
    if any(year in question for year in ("2024", "2025")) and any(
        token in question
        for token in (
            "закрыли",
            "закрыл",
            "закрыт",
            "закрыли год",
            "итог",
            "итоги",
            "результат",
            "результаты",
            "в целом",
            "общем",
            "общий",
            "общая",
            "год закры",
            "год закон",
            "закончили",
        )
    ):
        return True

    if any(
        token in question
        for token in (
            "управлен",
            "отчет 2025",
            "отчёт 2025",
            "2025.xlsx",
            "подраздел",
            "рентаб",
            "марж",
            "пдз",
            "дебитор",
            "недопостав",
            "товарная группа",
            "заработ",
            "регионы опт",
            "сети -",
        )
    ):
        return True

    if (
        any(year in question for year in ("2024", "2025"))
        and any(token in question for token in ("товар", "продукт", "номенклатур"))
        and any(token in question for token in ("заработ", "прибыл", "маржин", "выруч"))
    ):
        return True

    # In MAGAMAX reports, "ТГ" is the common shorthand for "товарная группа".
    # Require nearby business/report language to avoid treating generic chat about Telegram as report data.
    return bool(PRODUCT_GROUP_ABBR_PATTERN.search(question)) and any(
        token in question
        for token in (
            "2024",
            "2025",
            "выгод",
            "рентаб",
            "выруч",
            "прибыл",
            "маржин",
            "самая",
            "самый",
            "лучше",
            "хуже",
        )
    )


def _is_year_result_question(question: str) -> bool:
    has_year = any(year in question for year in ("2024", "2025"))
    has_phrase = any(phrase in question for phrase in YEAR_RESULT_PHRASES)
    has_result_token = any(
        token in question
        for token in (
            "закры",
            "итог",
            "результат",
            "в целом",
            "что по",
            "как отработали год",
        )
    )
    return has_phrase or (has_year and has_result_token)


def _is_month_performance_question(question: str) -> bool:
    has_month = any(token in question for token in MONTH_BUSINESS_TOKENS)
    has_business_phrase = any(
        phrase in question
        for phrase in (
            "как отработали",
            "что с",
            "что по",
            "просел",
            "просели",
            "вырос",
            "выросли",
            "динамика",
            "хуже",
            "лучше",
        )
    )
    return has_month and has_business_phrase


def _is_problem_or_order_question(question: str) -> bool:
    return any(
        phrase in question
        for phrase in (
            "покажи проблемные",
            "что проблемное",
            "что надо заказать",
            "что заказать",
            "что в зоне риска",
            "где не хватает",
            "не хватает",
            "дефицит",
            "низкий остаток",
        )
    )


def _is_broad_business_question(question: str) -> bool:
    if _is_external_question(question):
        return False
    return (
        any(phrase in question for phrase in BROAD_BUSINESS_PHRASES)
        or _is_year_result_question(question)
        or _is_month_performance_question(question)
    )


def _is_analytics_slice_question(question: str) -> bool:
    slice_tokens = (
        "по категория",
        "по клиент",
        "по sku",
        "по артику",
        "по скла",
        "по месяц",
        "по кварт",
        "в разрезе",
        "срез",
        "топ",
    )
    metric_tokens = (
        "продаж",
        "выруч",
        "штук",
        "шт",
        "остат",
        "склад",
        "резерв",
        "дефицит",
        "покрыт",
        "постав",
    )
    return any(token in question for token in slice_tokens) and any(
        token in question for token in metric_tokens
    )


def _is_data_overview_question(question: str) -> bool:
    broad_tokens = (
        "что есть в бд",
        "что есть в базе",
        "какие данные есть",
        "какие данные доступны",
        "какие источники доступны",
        "покажи всё полезное",
        "покажи все полезное",
        "покажи всё что есть",
        "покажи все что есть",
        "обзор данных",
        "инвентаризация данных",
        "что загружено в бд",
        "что загружено в базе",
    )
    return any(token in question for token in broad_tokens)


def _detect_intent(question: str) -> str:
    q = _flatten_text(question)
    if not q:
        return "unsupported_or_ambiguous"
    if _is_help_question(q):
        return "free_chat"
    if _is_data_overview_question(q):
        return "data_overview"
    if any(token in q for token in ("постав", "inbound", "incoming", "eta")) and any(
        token in q for token in ("дефицит", "закро", "закры", "влия")
    ):
        return "inbound_impact"
    if _is_problem_or_order_question(q):
        return "stock_risk_summary"
    if any(
        token in q for token in ("рассчитай", "пересчитай", "перерассчитай", "calculate")
    ) and any(token in q for token in ("резерв", "reserve")):
        return "reserve_calculation"
    if _is_year_result_question(q):
        return "management_report_summary"
    if _is_management_report_question(q):
        return "management_report_summary"
    if _is_month_performance_question(q):
        return "analytics_slice"
    if any(phrase in q for phrase in ("как дела по ", "что по клиент", "как дела с ")):
        return "client_summary"
    if "дефицит" in q and any(token in q for token in ("товар", "sku", "артикул")):
        return "analytics_slice"
    if "топ sku" in q or "топ артик" in q or "топ" in q or "антитоп" in q:
        return "analytics_slice"
    if _is_analytics_slice_question(q):
        return "analytics_slice"
    if any(token in q for token in ("просел", "просели", "хуже всего продав", "динамик")):
        return "analytics_slice"
    if any(token in q for token in ("сравни", "сравнить", "сравнение")) and any(
        token in q for token in ("месяц", "период", "прошл", "2024", "2025", "год")
    ):
        return "period_comparison"
    if any(token in q for token in ("продаж", "sales", "реализац", "выруч", "остат")):
        return "analytics_slice"
    if any(token in q for token in ("объясни", "почему", "why", "fallback")) and any(
        token in q for token in ("резерв", "дефицит", "critical", "критич", "shortage", "sku")
    ):
        return "reserve_explanation"
    if any(token in q for token in ("рассчитай", "calculate", "покажи резерв", "reserve need")):
        return "reserve_calculation"
    if "ниже резерва" in q or "under reserve" in q or "недопокрыт" in q:
        return "diy_coverage_check"
    if any(token in q for token in ("пришл", "поступил", "поступл")) and any(
        token in q for token in ("склад", "постав", "inbound")
    ):
        return "analytics_slice"
    if any(token in q for token in ("постав", "inbound", "incoming", "eta")):
        return "inbound_impact"
    if any(token in q for token in ("critical", "критич", "проблемн")) and any(
        token in q for token in ("позици", "sku", "товар")
    ):
        return "stock_risk_summary"
    if any(
        token in q
        for token in (
            "склад",
            "stock risk",
            "stockout",
            "coverage",
            "покрытие",
            "зоне риска",
            "зона риска",
        )
    ):
        return "stock_risk_summary"
    if any(token in q for token in ("качество", "quality", "issue", "проблемы данных")):
        return "quality_issue_summary"
    if any(
        token in q
        for token in (
            "загруз",
            "upload",
            "freshness",
            "обновлял",
            "данные использовались",
            "data used",
        )
    ):
        return "upload_status_summary"
    if "sku" in q or "артикул" in q:
        return "sku_summary"
    if any(token in q for token in ("клиент", "сеть", "diy", "client", "network")):
        return "client_summary"
    if any(token in q for token in ("резерв", "reserve")):
        return "reserve_calculation"
    if _is_broad_business_question(q):
        return "analytics_slice"
    if _is_domain_chat(q):
        return "free_chat"
    return "unsupported_or_ambiguous"


def _extract_client_id(db: Session, question: str) -> tuple[str | None, str | None]:
    q = _flatten_text(question)
    aliases = db.scalars(select(ClientAlias)).all()
    for alias in sorted(aliases, key=lambda item: len(item.alias), reverse=True):
        if alias.alias.lower() in q:
            client = resolve_client_by_name_or_alias(db, alias.alias)
            if client is not None:
                return client.id, client.name
    for alias in aliases:
        candidate = alias.alias
        candidate_normalized = candidate.lower()
        candidate_tokens = [token for token in candidate_normalized.split() if len(token) >= 3]
        if candidate_normalized in q or any(
            re.search(rf"(?<!\w){re.escape(token)}(?!\w)", q) for token in candidate_tokens
        ):
            client = resolve_client_by_name_or_alias(db, candidate)
            if client is not None:
                return client.id, client.name
    return None, None


def _extract_sku_refs(db: Session, question: str) -> tuple[list[str], list[str]]:
    found_codes: list[str] = []
    found_ids: list[str] = []
    for match in SKU_CODE_PATTERN.findall(question):
        sku = resolve_sku_by_code_or_alias(db, match)
        if sku is None:
            continue
        if sku.id not in found_ids:
            found_ids.append(sku.id)
            found_codes.append(sku.article)
    return found_ids, found_codes


def _extract_category(db: Session, question: str) -> tuple[str | None, str | None]:
    q = _flatten_text(question)
    categories = db.scalars(select(Category).order_by(Category.level.desc(), Category.name)).all()
    for category in sorted(categories, key=lambda item: len(item.name), reverse=True):
        if category.name.lower() in q:
            return category.id, category.name
    return None, None


def _extract_upload_ids(db: Session, question: str) -> list[str]:
    q = _flatten_text(question)
    file_ids: list[str] = []
    files = db.scalars(select(UploadFile).order_by(UploadFile.created_at.desc())).all()
    for file in files:
        if file.file_name.lower() in q and file.id not in file_ids:
            file_ids.append(file.id)
    return file_ids


def route_question(
    db: Session,
    question: str,
    *,
    forced_intent: AssistantIntent | None = None,
) -> AssistantRoute:
    route = AssistantRoute(intent=forced_intent or _detect_intent(question))  # type: ignore[arg-type]
    if route.intent == "free_chat":
        return route
    if route.intent == "unsupported_or_ambiguous":
        route.warnings.append(
            AssistantWarningData(
                code="out_of_scope_or_ambiguous",
                message=(
                    "Запрос не относится к рабочим данным MAGAMAX или сформулирован слишком неопределённо."
                ),
                severity="warning",
            )
        )
        return route

    route.extracted_client_id, route.extracted_client_name = _extract_client_id(db, question)
    route.extracted_sku_ids, route.extracted_sku_codes = _extract_sku_refs(db, question)
    route.extracted_category_id, route.extracted_category_name = _extract_category(db, question)
    route.extracted_upload_ids = _extract_upload_ids(db, question)

    months_match = MONTHS_PATTERN.search(question)
    if months_match:
        route.reserve_months = int(months_match.group(1))
    safety_match = SAFETY_PATTERN.search(question)
    if safety_match:
        route.safety_factor = float(safety_match.group(1).replace(",", "."))

    if route.intent in {"reserve_explanation", "sku_summary"} and not route.extracted_sku_ids:
        route.warnings.append(
            AssistantWarningData(
                code="missing_sku_reference",
                message="В вопросе не найден явный SKU, будет использован pinned context если он задан.",
            )
        )
    if (
        route.intent in {"client_summary", "reserve_calculation", "diy_coverage_check"}
        and not route.extracted_client_id
    ):
        route.warnings.append(
            AssistantWarningData(
                code="missing_client_reference",
                message="В вопросе не найден явный клиент, будет использован pinned context если он задан.",
            )
        )
    return route
