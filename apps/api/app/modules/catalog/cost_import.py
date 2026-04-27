from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from apps.api.app.common.utils import utc_now
from apps.api.app.db.models import Product, Sku, SkuCost, SkuCostHistory, UploadFile
from apps.api.app.modules.catalog.brand import resolve_brand
from apps.api.app.modules.uploads.parsers import raw_row_payload, read_upload_payload
from apps.api.app.modules.uploads.storage import ObjectStorage


@dataclass(frozen=True)
class SkuCostImportSummary:
    upload_file_id: str
    file_name: str
    total_rows: int
    imported_rows: int
    skipped_rows: int
    linked_sku_rows: int
    history_rows: int


ARTICLE_HEADERS = ("артикул", "article", "sku", "sku_code")
NAME_HEADERS = ("наименование", "товар", "product_name", "name")
COST_HEADERS = ("себестоимость", "себесстоимость", "cost", "cost_rub")


def is_sku_cost_headers(headers: list[str]) -> bool:
    return bool(
        _find_column(headers, ARTICLE_HEADERS)
        and _find_column(headers, NAME_HEADERS)
        and _find_column(headers, COST_HEADERS)
    )


def _normalize_header(value: str) -> str:
    return value.strip().lower().replace(",", "").replace(".", "")


def _find_column(headers: list[str], candidates: tuple[str, ...]) -> str | None:
    normalized = {_normalize_header(header): header for header in headers}
    for candidate in candidates:
        candidate_normalized = _normalize_header(candidate)
        for header_normalized, original in normalized.items():
            if candidate_normalized in header_normalized:
                return original
    return None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float | Decimal):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    text = str(value).replace("\xa0", "").replace(" ", "").replace("−", "-")
    text = text.replace(",", ".").strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _get_or_create_product(db: Session, product_name: str, brand: str) -> Product:
    existing = db.scalars(
        select(Product).where(Product.name == product_name, Product.brand == brand)
    ).first()
    if existing is not None:
        return existing
    product = Product(name=product_name, brand=brand, active=True)
    db.add(product)
    db.flush()
    return product


def _get_or_create_sku_for_cost(
    db: Session,
    sku_by_article: dict[str, Sku],
    article: str,
    product_name: str,
) -> Sku:
    sku = sku_by_article.get(article)
    brand = resolve_brand(sku.brand if sku else None, product_name, article)
    product = _get_or_create_product(db, product_name, brand)
    if sku is None:
        sku = Sku(
            article=article,
            name=product_name,
            product_id=product.id,
            brand=brand,
            unit="pcs",
            active=True,
        )
        db.add(sku)
        db.flush()
        sku_by_article[article] = sku
        return sku

    sku.name = product_name
    sku.product_id = product.id
    sku.brand = brand
    sku.unit = sku.unit or "pcs"
    sku.active = True
    return sku


def import_sku_costs_from_upload(
    db: Session,
    storage: ObjectStorage,
    upload_file_id: str,
    *,
    commit: bool = True,
) -> SkuCostImportSummary:
    upload_file = db.get(UploadFile, upload_file_id)
    if upload_file is None:
        raise ValueError(f"Upload file {upload_file_id} not found")

    payload = storage.load_upload_bytes(upload_file.storage_key)
    parsed = read_upload_payload(payload, upload_file.file_name)
    headers = [str(column) for column in parsed.frame.columns]
    article_column = _find_column(headers, ARTICLE_HEADERS)
    name_column = _find_column(headers, NAME_HEADERS)
    cost_column = _find_column(headers, COST_HEADERS)
    if not article_column or not name_column or not cost_column:
        raise ValueError("SKU cost file must contain article, product name and cost columns")

    articles = {
        str(article).strip()
        for article in parsed.frame[article_column].tolist()
        if _clean_text(article)
    }
    sku_by_article = {
        sku.article: sku for sku in db.scalars(select(Sku).where(Sku.article.in_(articles))).all()
    }
    existing_by_article = {
        item.article: item
        for item in db.scalars(select(SkuCost).where(SkuCost.article.in_(articles))).all()
    }
    db.execute(delete(SkuCostHistory).where(SkuCostHistory.upload_file_id == upload_file.id))

    imported_rows = 0
    skipped_rows = 0
    linked_sku_rows = 0
    history_rows = 0
    for row_offset, (_, row) in enumerate(parsed.frame.iterrows(), start=2):
        article = _clean_text(row[article_column])
        product_name = _clean_text(row[name_column])
        cost_rub = _to_decimal(row[cost_column])
        if not article or not product_name or cost_rub is None:
            skipped_rows += 1
            continue

        sku = _get_or_create_sku_for_cost(db, sku_by_article, article, product_name)
        sku_cost = existing_by_article.get(article)
        if sku_cost is None:
            sku_cost = SkuCost(article=article, product_name=product_name, cost_rub=cost_rub)
            db.add(sku_cost)
            existing_by_article[article] = sku_cost
        raw_payload = {
            "parser": parsed.parser,
            "source_file_name": upload_file.file_name,
            "source_columns": {
                "article": article_column,
                "product_name": name_column,
                "cost_rub": cost_column,
            },
            "raw_row": raw_row_payload(row),
        }
        sku_cost.product_name = product_name
        sku_cost.cost_rub = cost_rub
        sku_cost.sku_id = sku.id if sku else None
        sku_cost.upload_file_id = upload_file.id
        sku_cost.source_row_number = row_offset
        sku_cost.raw_payload = raw_payload
        db.add(
            SkuCostHistory(
                article=article,
                product_name=product_name,
                cost_rub=cost_rub,
                sku_id=sku.id if sku else None,
                upload_file_id=upload_file.id,
                source_row_number=row_offset,
                raw_payload=raw_payload,
            )
        )
        imported_rows += 1
        history_rows += 1
        linked_sku_rows += 1

    upload_file.source_type = "sku_costs"
    upload_file.batch.source_type = "sku_costs"
    upload_file.batch.detected_source_type = "sku_costs"
    upload_file.batch.mapping_payload = {
        **upload_file.batch.mapping_payload,
        "active_mapping": {
            article_column: "article",
            name_column: "product_name",
            cost_column: "cost_rub",
        },
        "required_fields": ["article", "cost_rub", "product_name"],
        "source_detection": {
            **dict(upload_file.batch.mapping_payload.get("source_detection") or {}),
            "requires_confirmation": False,
            "confirmed": True,
            "detected_source_type": "sku_costs",
            "selected_source_type": "sku_costs",
        },
    }
    upload_file.batch.applied_rows = imported_rows
    upload_file.batch.failed_rows = skipped_rows
    upload_file.batch.total_rows = max(upload_file.batch.total_rows, imported_rows + skipped_rows)
    upload_file.batch.valid_rows = imported_rows
    upload_file.batch.warning_count = 0
    upload_file.batch.issue_count = 0
    upload_file.batch.status = "applied"
    upload_file.batch.validation_payload = {
        "validated_at": utc_now().isoformat(),
        "valid_rows": imported_rows,
        "failed_rows": skipped_rows,
        "warning_count": 0,
        "has_blocking_issues": False,
        "issue_counts": {"info": 0, "warning": 0, "error": 0, "critical": 0, "total": 0},
        "source_type": "sku_costs",
    }
    status_history = list(upload_file.batch.status_payload.get("history", []))
    status_history.append(
        {
            "status": "applied",
            "at": utc_now().isoformat(),
            "message": "Себестоимость по артикулам импортирована автоматически",
            "error": None,
        }
    )
    upload_file.batch.status_payload = {
        **upload_file.batch.status_payload,
        "history": status_history[-25:],
        "current_status_at": utc_now().isoformat(),
        "last_error": None,
        "message": "Себестоимость по артикулам импортирована в справочник SKU",
        "sku_cost_import": {
            "imported_rows": imported_rows,
            "skipped_rows": skipped_rows,
            "linked_sku_rows": linked_sku_rows,
            "history_rows": history_rows,
        },
    }
    if commit:
        db.commit()

    return SkuCostImportSummary(
        upload_file_id=upload_file.id,
        file_name=upload_file.file_name,
        total_rows=imported_rows + skipped_rows,
        imported_rows=imported_rows,
        skipped_rows=skipped_rows,
        linked_sku_rows=linked_sku_rows,
        history_rows=history_rows,
    )
