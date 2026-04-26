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
SAFETY_PATTERN = re.compile(r"(?:safety|коэффициент|factor|запас)\s*[:=]?\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)
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
    "пример вопроса",
    "как пользоваться",
    "что можно спросить",
)


def _flatten_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _is_domain_chat(question: str) -> bool:
    return any(token in question for token in DOMAIN_CHAT_TOKENS) or any(
        phrase in question for phrase in CONSOLE_USAGE_PHRASES
    )


def _is_management_report_question(question: str) -> bool:
    if any(
        token in question
        for token in (
            "управлен",
            "отчет 2025",
            "отчёт 2025",
            "2025.xlsx",
            "подраздел",
            "выруч",
            "рентаб",
            "пдз",
            "дебитор",
            "недопостав",
            "товарная группа",
            "товар",
            "товарн",
            "заработ",
            "регионы опт",
            "сети -",
        )
    ):
        return True

    if any(year in question for year in ("2024", "2025")) and any(
        token in question for token in ("товар", "продукт", "номенклатур")
    ) and any(token in question for token in ("заработ", "прибыл", "маржин", "выруч")):
        return True

    # In MAGAMAX reports, "ТГ" is the common shorthand for "товарная группа".
    # Require nearby business/report language to avoid treating generic chat about Telegram as report data.
    if PRODUCT_GROUP_ABBR_PATTERN.search(question) and any(
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
    ):
        return True
    return False


def _detect_intent(question: str) -> str:
    q = _flatten_text(question)
    if not q:
        return "unsupported_or_ambiguous"
    if _is_management_report_question(q):
        return "management_report_summary"
    if any(token in q for token in ("сравни", "сравнить", "сравнение")) and any(
        token in q for token in ("месяц", "период", "прошл")
    ):
        return "period_comparison"
    if any(token in q for token in ("продаж", "sales", "реализац")):
        return "sales_summary"
    if any(token in q for token in ("объясни", "почему", "why", "fallback")) and any(
        token in q for token in ("резерв", "дефицит", "critical", "критич", "shortage", "sku")
    ):
        return "reserve_explanation"
    if any(token in q for token in ("рассчитай", "calculate", "покажи резерв", "reserve need")):
        return "reserve_calculation"
    if "ниже резерва" in q or "under reserve" in q or "недопокрыт" in q:
        return "diy_coverage_check"
    if any(token in q for token in ("постав", "inbound", "incoming", "eta")):
        return "inbound_impact"
    if any(token in q for token in ("склад", "stock risk", "stockout", "coverage", "покрытие", "зоне риска", "зона риска")):
        return "stock_risk_summary"
    if any(token in q for token in ("качество", "quality", "issue", "проблемы данных")):
        return "quality_issue_summary"
    if any(
        token in q
        for token in ("загруз", "upload", "freshness", "обновлял", "данные использовались", "data used")
    ):
        return "upload_status_summary"
    if "sku" in q or "артикул" in q:
        return "sku_summary"
    if any(token in q for token in ("клиент", "сеть", "diy", "client", "network")):
        return "client_summary"
    if any(token in q for token in ("резерв", "reserve")):
        return "reserve_calculation"
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
    if route.intent in {"client_summary", "reserve_calculation", "diy_coverage_check"} and not route.extracted_client_id:
        route.warnings.append(
            AssistantWarningData(
                code="missing_client_reference",
                message="В вопросе не найден явный клиент, будет использован pinned context если он задан.",
            )
        )
    return route
