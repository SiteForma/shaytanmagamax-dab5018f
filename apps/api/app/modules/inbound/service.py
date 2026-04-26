from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from io import StringIO
from typing import Any

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from apps.api.app.common.utils import normalize_header, utc_now
from apps.api.app.core.config import Settings
from apps.api.app.core.errors import DomainError
from apps.api.app.db.models import Client, InboundDelivery, Product, Sku
from apps.api.app.modules.audit.service import record_audit_event
from apps.api.app.modules.inbound.schemas import InboundSyncResponse, InboundTimelineResponse
from apps.api.app.modules.mapping.service import (
    normalize_mapping_token,
    resolve_client_by_name_or_alias,
    resolve_sku_by_code_or_alias,
)

GOOGLE_SHEET_SOURCE_PREFIX = "google_sheet_inbound"
BASE_COLUMNS = {
    "статус",
    "ожидаемая_дата_поступления",
    "дата_предоплаты_до",
    "номер_контейнера",
    "артикул_не_трогать_название",
    "в_пути",
    "свободный_остаток",
    "боц",
    "цена_по_предоплате",
    "итого_заказы_клиентов",
}


@dataclass(slots=True)
class ParsedInboundRow:
    row_number: int
    status_raw: str
    eta_date: date
    container_ref: str
    article: str
    in_transit_qty: float
    free_stock_after_allocation_qty: float
    client_order_qty: float
    client_allocations: dict[str, float]
    raw_payload: dict[str, object]


def google_sheet_export_url(settings: Settings) -> str:
    if settings.inbound_google_sheet_export_url:
        return settings.inbound_google_sheet_export_url
    return (
        "https://docs.google.com/spreadsheets/d/"
        f"{settings.inbound_google_sheet_id}/export?format=csv&gid={settings.inbound_google_sheet_gid}"
    )


def _clean_text(value: object) -> str:
    return str(value or "").replace("\xa0", " ").strip()


def _parse_quantity(value: object) -> float:
    text = _clean_text(value)
    if not text:
        return 0.0
    normalized = (
        text.replace("\u2212", "-")
        .replace(" ", "")
        .replace("\xa0", "")
        .replace(",", ".")
    )
    try:
        return float(normalized)
    except ValueError as exc:
        raise DomainError(
            code="invalid_inbound_sheet_quantity",
            message=f"Некорректное количество в Google Sheet: {text}",
        ) from exc


def _parse_eta(value: object) -> date:
    text = _clean_text(value)
    if not text:
        raise DomainError(
            code="invalid_inbound_sheet_date",
            message="В строке Google Sheet не указана ожидаемая дата поступления",
        )
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise DomainError(
        code="invalid_inbound_sheet_date",
        message=f"Некорректная ожидаемая дата поступления в Google Sheet: {text}",
    )


def _status_to_delivery_status(value: str) -> str:
    normalized = normalize_mapping_token(value)
    if normalized in {"оприходован", "oprihodovan", "confirmed", "подтверждено", "podtverzhdeno"}:
        return "confirmed"
    if normalized in {"задержка", "zaderzhka", "delayed"}:
        return "delayed"
    if normalized in {"неопределено", "neopredeleno", "uncertain"}:
        return "uncertain"
    return "in_transit"


def _find_header_row(rows: list[list[str]]) -> tuple[int, list[str]]:
    for index, row in enumerate(rows):
        normalized = {normalize_header(cell) for cell in row}
        if {"статус", "в_пути", "свободный_остаток"}.issubset(normalized) and any(
            value.startswith("артикул") for value in normalized
        ):
            return index, row
    raise DomainError(
        code="inbound_sheet_header_missing",
        message="В Google Sheet не найдена строка заголовков inbound-таблицы",
    )


def parse_inbound_sheet_csv(csv_text: str) -> tuple[list[ParsedInboundRow], list[str]]:
    raw_rows = list(csv.reader(StringIO(csv_text)))
    header_index, headers = _find_header_row(raw_rows)
    normalized_headers = [normalize_header(header) for header in headers]
    index_by_header = {header: index for index, header in enumerate(normalized_headers)}

    def value(row: list[str], key: str) -> str:
        index = index_by_header[key]
        return row[index] if index < len(row) else ""

    required = {
        "статус",
        "ожидаемая_дата_поступления",
        "номер_контейнера",
        "в_пути",
        "свободный_остаток",
        "итого_заказы_клиентов",
    }
    article_key = next((key for key in normalized_headers if key.startswith("артикул")), None)
    missing = sorted(required.difference(index_by_header))
    if article_key is None:
        missing.append("артикул")
    if missing:
        raise DomainError(
            code="inbound_sheet_required_columns_missing",
            message="В Google Sheet не хватает обязательных колонок",
            details={"missing_columns": missing},
        )

    client_columns = [
        (index, headers[index].strip(), normalized)
        for index, normalized in enumerate(normalized_headers)
        if normalized and normalized not in BASE_COLUMNS and not normalized.startswith("артикул")
    ]

    parsed: list[ParsedInboundRow] = []
    warnings: list[str] = []
    for row_number, row in enumerate(raw_rows[header_index + 1 :], start=header_index + 2):
        article = _clean_text(row[index_by_header[article_key]]) if article_key else ""
        if not article:
            has_identity_fields = any(
                _clean_text(value(row, key))
                for key in ("статус", "ожидаемая_дата_поступления", "номер_контейнера")
            )
            has_positive_qty = any(
                _parse_quantity(value(row, key)) > 0
                for key in ("в_пути", "свободный_остаток", "итого_заказы_клиентов")
            )
            if has_identity_fields or has_positive_qty:
                warnings.append(f"Строка {row_number}: пропущена без артикула")
            continue
        try:
            in_transit_qty = _parse_quantity(value(row, "в_пути"))
            free_qty = _parse_quantity(value(row, "свободный_остаток"))
            client_order_qty = _parse_quantity(value(row, "итого_заказы_клиентов"))
            allocations: dict[str, float] = {}
            for index, label, _normalized in client_columns:
                qty = _parse_quantity(row[index] if index < len(row) else "")
                if qty:
                    allocations[label.strip()] = qty
            parsed.append(
                ParsedInboundRow(
                    row_number=row_number,
                    status_raw=_clean_text(value(row, "статус")),
                    eta_date=_parse_eta(value(row, "ожидаемая_дата_поступления")),
                    container_ref=_clean_text(value(row, "номер_контейнера")),
                    article=article,
                    in_transit_qty=in_transit_qty,
                    free_stock_after_allocation_qty=free_qty,
                    client_order_qty=client_order_qty,
                    client_allocations=allocations,
                    raw_payload={
                        "source": "google_sheet",
                        "row_number": row_number,
                        "headers": headers,
                        "values": row,
                    },
                )
            )
        except DomainError as exc:
            warnings.append(f"Строка {row_number}: {exc.message}")
    return parsed, warnings


def _get_or_create_sku(db: Session, article: str) -> tuple[Sku, bool]:
    sku = resolve_sku_by_code_or_alias(db, article)
    if sku is not None:
        return sku, False
    product = Product(name=article, brand="MAGAMAX", active=True)
    db.add(product)
    db.flush()
    sku = Sku(article=article, name=article, product_id=product.id, brand="MAGAMAX", unit="pcs")
    db.add(sku)
    db.flush()
    return sku, True


def _client_code(name: str) -> str:
    token = normalize_mapping_token(name) or normalize_header(name)
    return f"inbound_{token}"[:120]


def _get_or_create_client(db: Session, name: str) -> tuple[Client, bool]:
    client = resolve_client_by_name_or_alias(db, name)
    if client is not None:
        return client, False
    code = _client_code(name)
    suffix = 2
    unique_code = code
    while db.scalar(select(Client.id).where(Client.code == unique_code)) is not None:
        unique_code = f"{code[:112]}_{suffix}"
        suffix += 1
    client = Client(
        code=unique_code,
        name=name.strip(),
        region="Не указано",
        client_group="Inbound sheet",
        network_type="Inbound sheet",
        is_active=True,
    )
    db.add(client)
    db.flush()
    return client, True


def _download_sheet_csv(settings: Settings) -> tuple[str, str]:
    source_url = google_sheet_export_url(settings)
    try:
        response = httpx.get(source_url, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise DomainError(
            code="inbound_sheet_download_failed",
            message="Не удалось скачать Google Sheet с товарами в пути",
            details={"source_url": source_url},
        ) from exc
    return response.text, source_url


def sync_inbound_google_sheet(
    db: Session,
    settings: Settings,
    *,
    actor_user_id: str | None = None,
    csv_text: str | None = None,
    source_url: str | None = None,
) -> InboundSyncResponse:
    csv_payload, resolved_source_url = (
        (csv_text, source_url or "inline://test") if csv_text is not None else _download_sheet_csv(settings)
    )
    rows, warnings = parse_inbound_sheet_csv(csv_payload)
    synced_at = utc_now()

    existing_count = db.scalar(
        select(func.count(InboundDelivery.id)).where(
            InboundDelivery.external_ref.like(f"{GOOGLE_SHEET_SOURCE_PREFIX}:%")
        )
    ) or 0
    db.execute(
        delete(InboundDelivery).where(
            InboundDelivery.external_ref.like(f"{GOOGLE_SHEET_SOURCE_PREFIX}:%")
        )
    )

    sku_created = 0
    clients_created = 0
    total_in_transit_qty = 0.0
    total_free_qty = 0.0
    total_client_order_qty = 0.0

    for parsed in rows:
        sku, created_sku = _get_or_create_sku(db, parsed.article)
        sku_created += int(created_sku)
        affected_client_ids: list[str] = []
        allocation_payload: dict[str, float] = {}
        for client_name, qty in parsed.client_allocations.items():
            client, created_client = _get_or_create_client(db, client_name)
            clients_created += int(created_client)
            affected_client_ids.append(client.id)
            allocation_payload[client.name] = qty

        total_in_transit_qty += parsed.in_transit_qty
        total_free_qty += parsed.free_stock_after_allocation_qty
        total_client_order_qty += parsed.client_order_qty
        db.add(
            InboundDelivery(
                external_ref=(
                    f"{GOOGLE_SHEET_SOURCE_PREFIX}:"
                    f"{settings.inbound_google_sheet_gid}:{parsed.row_number}:{parsed.container_ref}:{parsed.article}"
                ),
                sku_id=sku.id,
                container_ref=parsed.container_ref,
                quantity=parsed.in_transit_qty,
                free_stock_after_allocation_qty=parsed.free_stock_after_allocation_qty,
                client_order_qty=parsed.client_order_qty,
                eta_date=parsed.eta_date,
                status=_status_to_delivery_status(parsed.status_raw),
                sheet_status=parsed.status_raw,
                affected_client_ids=affected_client_ids,
                reserve_impact_qty=parsed.client_order_qty,
                client_allocations=allocation_payload,
                raw_payload={
                    **parsed.raw_payload,
                    "source_url": resolved_source_url,
                    "synced_at": synced_at.isoformat(),
                    "free_stock_after_allocation_qty": parsed.free_stock_after_allocation_qty,
                    "client_order_qty": parsed.client_order_qty,
                },
            )
        )

    result = InboundSyncResponse(
        status="completed",
        source_url=resolved_source_url,
        synced_at=synced_at.isoformat(),
        rows_seen=len(rows) + len(warnings),
        rows_imported=len(rows),
        rows_skipped=len(warnings),
        deliveries_replaced=int(existing_count),
        sku_created=sku_created,
        clients_created=clients_created,
        total_in_transit_qty=round(total_in_transit_qty, 2),
        total_free_stock_after_allocation_qty=round(total_free_qty, 2),
        total_client_order_qty=round(total_client_order_qty, 2),
        warnings=warnings[:50],
    )
    record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="inbound.google_sheet_synced",
        target_type="inbound_google_sheet",
        target_id=settings.inbound_google_sheet_gid,
        context=result.model_dump(),
    )
    db.commit()
    return result


def get_inbound_timeline(db: Session) -> list[InboundTimelineResponse]:
    skus = {sku.id: sku for sku in db.scalars(select(Sku)).all()}
    inbound_rows = db.scalars(select(InboundDelivery).order_by(InboundDelivery.eta_date)).all()
    items: list[InboundTimelineResponse] = []
    for row in inbound_rows:
        sku = skus.get(row.sku_id)
        if sku is None:
            continue
        raw_payload: dict[str, Any] = dict(row.raw_payload or {})
        items.append(
            InboundTimelineResponse(
                id=row.id,
                sku_id=row.sku_id,
                article=sku.article,
                sku_name=sku.name,
                container_ref=row.container_ref,
                qty=row.quantity,
                free_stock_after_allocation=row.free_stock_after_allocation_qty,
                client_order_qty=row.client_order_qty,
                eta=row.eta_date.isoformat(),
                status=row.status,
                sheet_status=row.sheet_status,
                affected_clients=row.affected_client_ids,
                client_allocations={
                    str(key): float(value)
                    for key, value in dict(row.client_allocations or {}).items()
                    if isinstance(value, (int, float))
                },
                reserve_impact=row.reserve_impact_qty,
                source_synced_at=str(raw_payload.get("synced_at") or "") or None,
            )
        )
    return items
