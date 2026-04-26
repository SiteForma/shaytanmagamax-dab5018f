from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.db.models import Category, ClientAlias, UploadFile
from apps.api.app.modules.assistant.domain import AssistantRoute, AssistantWarningData
from apps.api.app.modules.mapping.service import (
    resolve_client_by_name_or_alias,
    resolve_sku_by_code_or_alias,
)

SKU_CODE_PATTERN = re.compile(r"\b[0-9A-Za-zА-Яа-я]+(?:-[0-9A-Za-zА-Яа-я]+)+\b")
MONTHS_PATTERN = re.compile(r"(\d+)\s*(?:месяц|месяца|месяцев|months?)", re.IGNORECASE)
SAFETY_PATTERN = re.compile(r"(?:safety|коэффициент|factor|запас)\s*[:=]?\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)


def _flatten_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _detect_intent(question: str) -> str:
    q = _flatten_text(question)
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
    if any(token in q for token in ("склад", "stock risk", "stockout", "coverage", "покрытие")):
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
    return "unsupported_or_ambiguous"


def _extract_client_id(db: Session, question: str) -> tuple[str | None, str | None]:
    q = _flatten_text(question)
    aliases = db.scalars(select(ClientAlias)).all()
    for alias in sorted(aliases, key=lambda item: len(item.alias), reverse=True):
        if alias.alias.lower() in q:
            client = resolve_client_by_name_or_alias(db, alias.alias)
            if client is not None:
                return client.id, client.name
    direct_names = {
        alias.client_id: alias.alias for alias in aliases
    }
    for _client_id, candidate in direct_names.items():
        if candidate.lower() in q:
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


def route_question(db: Session, question: str) -> AssistantRoute:
    route = AssistantRoute(intent=_detect_intent(question))  # type: ignore[arg-type]
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

    if route.intent == "unsupported_or_ambiguous":
        route.warnings.append(
            AssistantWarningData(
                code="unsupported_intent",
                message="Вопрос не удалось надёжно отнести к поддерживаемому operational intent.",
                severity="warning",
            )
        )
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
