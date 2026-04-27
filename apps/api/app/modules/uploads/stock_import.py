from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from apps.api.app.common.utils import utc_now
from apps.api.app.db.models import Product, Sku, StockSnapshot, UploadFile
from apps.api.app.modules.catalog.brand import resolve_brand
from apps.api.app.modules.uploads.parsers import read_upload_payload
from apps.api.app.modules.uploads.storage import ObjectStorage


@dataclass(frozen=True)
class WarehouseStockImportSummary:
    upload_file_id: str
    file_name: str
    raw_rows: int
    product_rows: int
    stock_rows: int
    free_stock_rows: int
    diy_reserved_rows: int
    skipped_rows: int


ARTICLE_HEADERS = ("артикул", "article", "sku", "sku_code")
PRODUCT_HEADERS = ("номенклатура", "наименование", "товар", "product_name")
QTY_HEADERS = ("доступно", "остаток", "stock", "quantity", "qty")
FREE_WAREHOUSE_CODE = "SHELKOVO_FREE"
DIY_RESERVED_WAREHOUSE_CODE = "DIY_NETWORKS_OBOSOBKA"


def _normalize_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value or "").strip().lower().replace("ё", "е")


def _clean_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value or "").strip()
    return text or None


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        if pd.isna(value):
            return None
        return float(value)
    text = str(value).replace("\xa0", "").replace(" ", "").replace(",", ".").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _find_column(headers: list[str], candidates: tuple[str, ...]) -> str | None:
    normalized = {_normalize_text(header): header for header in headers}
    for candidate in candidates:
        candidate_normalized = _normalize_text(candidate)
        for header_normalized, original in normalized.items():
            if candidate_normalized in header_normalized:
                return original
    return None


def _quantity_column(frame: pd.DataFrame) -> str | None:
    headers = [str(column) for column in frame.columns]
    direct = _find_column(headers, QTY_HEADERS)
    if direct is not None:
        return direct
    numeric_counts: list[tuple[int, str]] = []
    for column in headers:
        count = sum(_to_float(value) is not None for value in frame[column].tolist())
        numeric_counts.append((count, column))
    numeric_counts.sort(reverse=True)
    return numeric_counts[0][1] if numeric_counts and numeric_counts[0][0] > 0 else None


def _stock_bucket(label: str) -> tuple[str, str] | None:
    normalized = _normalize_text(label)
    if "обс" in normalized and "сет" in normalized:
        return DIY_RESERVED_WAREHOUSE_CODE, "diy_reserved"
    if "склад" in normalized and "щел" in normalized:
        return FREE_WAREHOUSE_CODE, "free"
    return None


def is_warehouse_stock_frame(frame: pd.DataFrame) -> bool:
    headers = [str(column) for column in frame.columns]
    article_column = _find_column(headers, ARTICLE_HEADERS)
    product_column = _find_column(headers, PRODUCT_HEADERS)
    qty_column = _quantity_column(frame)
    if not article_column or not product_column or not qty_column:
        return False
    labels = [_normalize_text(value) for value in frame[article_column].head(80).tolist()]
    has_free = any("склад" in label and "щел" in label for label in labels)
    has_diy_reserved = any("обс" in label and "сет" in label for label in labels)
    return has_free or has_diy_reserved


def _get_or_create_product(db: Session, name: str, brand: str) -> Product:
    existing = db.scalars(
        select(Product).where(Product.name == name, Product.brand == brand)
    ).first()
    if existing is not None:
        return existing
    product = Product(name=name, brand=brand, active=True)
    db.add(product)
    db.flush()
    return product


def _get_or_create_sku(db: Session, article: str, product_name: str) -> Sku:
    sku = db.scalars(select(Sku).where(Sku.article == article)).first()
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
        return sku
    sku.name = product_name
    sku.product_id = product.id
    sku.brand = brand
    sku.active = True
    return sku


def import_warehouse_stock_from_upload(
    db: Session,
    storage: ObjectStorage,
    upload_file_id: str,
    *,
    commit: bool = True,
) -> WarehouseStockImportSummary:
    upload_file = db.get(UploadFile, upload_file_id)
    if upload_file is None:
        raise ValueError(f"Upload file {upload_file_id} not found")

    payload = storage.load_upload_bytes(upload_file.storage_key)
    parsed = read_upload_payload(payload, upload_file.file_name)
    frame = parsed.frame
    headers = [str(column) for column in frame.columns]
    article_column = _find_column(headers, ARTICLE_HEADERS)
    product_column = _find_column(headers, PRODUCT_HEADERS)
    qty_column = _quantity_column(frame)
    if not article_column or not product_column or not qty_column:
        raise ValueError("Warehouse stock file must contain article, product and quantity columns")

    db.execute(delete(StockSnapshot).where(StockSnapshot.source_batch_id == upload_file.batch_id))

    current_sku: Sku | None = None
    current_article: str | None = None
    current_product_name: str | None = None
    product_rows = 0
    stock_rows = 0
    free_stock_rows = 0
    diy_reserved_rows = 0
    skipped_rows = 0
    snapshot_at = upload_file.created_at or utc_now()

    for _, row in frame.iterrows():
        label = _clean_text(row[article_column])
        product_name = _clean_text(row[product_column])
        qty = _to_float(row[qty_column])
        if not label:
            skipped_rows += 1
            continue

        if product_name:
            current_article = label
            current_product_name = product_name
            current_sku = _get_or_create_sku(db, current_article, current_product_name)
            product_rows += 1
            continue

        bucket = _stock_bucket(label)
        if bucket is None or current_sku is None or qty is None:
            skipped_rows += 1
            continue

        warehouse_code, bucket_kind = bucket
        free_qty = qty if bucket_kind == "free" else 0.0
        reserved_qty = qty if bucket_kind == "diy_reserved" else 0.0
        db.add(
            StockSnapshot(
                source_batch_id=upload_file.batch_id,
                sku_id=current_sku.id,
                warehouse_code=warehouse_code,
                snapshot_at=snapshot_at,
                free_stock_qty=free_qty,
                reserved_like_qty=reserved_qty,
            )
        )
        stock_rows += 1
        if bucket_kind == "free":
            free_stock_rows += 1
        else:
            diy_reserved_rows += 1

    upload_file.source_type = "stock"
    upload_file.batch.source_type = "stock"
    upload_file.batch.detected_source_type = "stock"
    upload_file.batch.total_rows = len(frame.index)
    upload_file.batch.valid_rows = product_rows
    upload_file.batch.applied_rows = stock_rows
    upload_file.batch.failed_rows = 0
    upload_file.batch.warning_count = 0
    upload_file.batch.issue_count = 0
    upload_file.batch.status = "applied"
    upload_file.batch.mapping_payload = {
        **upload_file.batch.mapping_payload,
        "active_mapping": {
            article_column: "sku_code",
            product_column: "product_name",
            qty_column: "stock_free",
        },
        "stock_adapter": {
            "name": "warehouse_hierarchy_v1",
            "free_warehouse_code": FREE_WAREHOUSE_CODE,
            "diy_reserved_warehouse_code": DIY_RESERVED_WAREHOUSE_CODE,
            "stock_policy": {
                FREE_WAREHOUSE_CODE: "Свободный остаток склада Щелково",
                DIY_RESERVED_WAREHOUSE_CODE: "Обособка СЕТИ: отдельный DIY bucket",
            },
        },
        "source_detection": {
            **dict(upload_file.batch.mapping_payload.get("source_detection") or {}),
            "requires_confirmation": False,
            "confirmed": True,
            "detected_source_type": "stock",
            "selected_source_type": "stock",
        },
    }
    upload_file.batch.validation_payload = {
        "validated_at": utc_now().isoformat(),
        "valid_rows": product_rows,
        "failed_rows": 0,
        "warning_count": 0,
        "has_blocking_issues": False,
        "issue_counts": {"info": 0, "warning": 0, "error": 0, "critical": 0, "total": 0},
        "source_type": "stock",
        "adapter": "warehouse_hierarchy_v1",
        "stock_rows": stock_rows,
        "free_stock_rows": free_stock_rows,
        "diy_reserved_rows": diy_reserved_rows,
        "skipped_non_data_rows": skipped_rows,
    }
    history = list(upload_file.batch.status_payload.get("history", []))
    history.append(
        {
            "status": "applied",
            "at": utc_now().isoformat(),
            "message": "Склад Щелково и обособка СЕТИ импортированы отдельными stock bucket",
            "error": None,
        }
    )
    upload_file.batch.status_payload = {
        **upload_file.batch.status_payload,
        "history": history[-25:],
        "current_status_at": utc_now().isoformat(),
        "last_error": None,
        "message": "Остатки импортированы с разделением склада Щелково и обособки СЕТИ",
        "warehouse_stock_import": {
            "product_rows": product_rows,
            "stock_rows": stock_rows,
            "free_stock_rows": free_stock_rows,
            "diy_reserved_rows": diy_reserved_rows,
            "skipped_non_data_rows": skipped_rows,
        },
    }
    if commit:
        db.commit()

    return WarehouseStockImportSummary(
        upload_file_id=upload_file.id,
        file_name=upload_file.file_name,
        raw_rows=len(frame.index),
        product_rows=product_rows,
        stock_rows=stock_rows,
        free_stock_rows=free_stock_rows,
        diy_reserved_rows=diy_reserved_rows,
        skipped_rows=skipped_rows,
    )
