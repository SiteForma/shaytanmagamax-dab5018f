from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import pandas as pd

from apps.api.app.modules.mapping.service import normalize_mapping_token
from apps.api.app.modules.uploads.parsers import raw_row_payload, sanitize_value

SEVERITY_ORDER = ("info", "warning", "error", "critical")
INBOUND_STATUS_MAP = {
    "confirmed": "confirmed",
    "подтверждено": "confirmed",
    "in_transit": "in_transit",
    "в пути": "in_transit",
    "delayed": "delayed",
    "задержка": "delayed",
    "uncertain": "uncertain",
    "неопределено": "uncertain",
}


@dataclass(slots=True)
class ValidationIssue:
    row_number: int
    field_name: str | None
    code: str
    severity: str
    message: str
    raw_payload: dict[str, object | None] | None


@dataclass(slots=True)
class ValidationResult:
    normalized_rows: list[dict[str, object]]
    issues: list[ValidationIssue]
    valid_rows: int
    failed_rows: int
    warning_count: int


def _normalize_value(value: Any) -> Any:
    value = sanitize_value(value)
    if isinstance(value, str):
        return value.strip()
    return value


def _parse_float(value: Any) -> float | None:
    value = _normalize_value(value)
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        normalized = value.replace(" ", "").replace(",", ".")
        return float(normalized)
    return float(value)


def _parse_int(value: Any) -> int | None:
    parsed = _parse_float(value)
    if parsed is None:
        return None
    return int(parsed)


def _parse_bool(value: Any) -> bool | None:
    value = _normalize_value(value)
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        token = normalize_mapping_token(value)
        if token in {"true", "1", "yes", "active", "da"}:
            return True
        if token in {"false", "0", "no", "inactive", "net"}:
            return False
    return bool(value)


def _parse_date(value: Any) -> date | None:
    value = _normalize_value(value)
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=False)
    if pd.isna(parsed):
        return None
    return parsed.date()


def _require(
    normalized: dict[str, object],
    field_name: str,
    row_number: int,
    issues: list[ValidationIssue],
    raw_payload: dict[str, object | None],
) -> None:
    if normalized.get(field_name) in (None, ""):
        issues.append(
            ValidationIssue(
                row_number=row_number,
                field_name=field_name,
                code="required_field_missing",
                severity="error",
                message="Отсутствует обязательное поле",
                raw_payload=raw_payload,
            )
        )


def normalize_mapped_row(row: pd.Series, mapping: dict[str, str]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for source_field, canonical_field in mapping.items():
        if not canonical_field or source_field not in row.index:
            continue
        normalized[canonical_field] = _normalize_value(row[source_field])
    return normalized


def _duplicate_signature(source_type: str, normalized: dict[str, object]) -> tuple[object, ...]:
    if source_type == "sales":
        return (
            normalized.get("client_name"),
            normalized.get("sku_code"),
            normalized.get("period_date"),
        )
    if source_type == "stock":
        return (
            normalized.get("sku_code"),
            normalized.get("snapshot_date"),
            normalized.get("warehouse_name"),
        )
    if source_type == "inbound":
        return (
            normalized.get("sku_code"),
            normalized.get("eta_date"),
            normalized.get("status"),
            normalized.get("quantity"),
        )
    if source_type == "diy_clients":
        return (normalized.get("client_name"), normalized.get("active"))
    if source_type == "category_structure":
        return (
            normalized.get("sku_code"),
            normalized.get("category_level_1"),
            normalized.get("category_level_2"),
            normalized.get("category_level_3"),
        )
    return tuple(normalized.items())


def validate_frame(
    frame: pd.DataFrame, source_type: str, mapping: dict[str, str]
) -> ValidationResult:
    issues: list[ValidationIssue] = []
    normalized_rows: list[dict[str, object]] = []
    seen_signatures: set[tuple[object, ...]] = set()
    seen_active_clients: set[str] = set()

    for index, row in frame.iterrows():
        row_number = int(index) + 2
        raw_payload = raw_row_payload(row)
        normalized = normalize_mapped_row(row, mapping)
        if not normalized or all(value in (None, "") for value in normalized.values()):
            issues.append(
                ValidationIssue(
                    row_number=row_number,
                    field_name=None,
                    code="empty_normalized_row",
                    severity="warning",
                    message="После сопоставления строка становится пустой",
                    raw_payload=raw_payload,
                )
            )
            continue

        row_issues: list[ValidationIssue] = []
        if source_type == "sales":
            for required in ("period_date", "client_name", "sku_code", "quantity"):
                _require(normalized, required, row_number, row_issues, raw_payload)
            period_date = _parse_date(normalized.get("period_date"))
            if normalized.get("period_date") not in (None, "") and period_date is None:
                row_issues.append(
                    ValidationIssue(
                        row_number=row_number,
                        field_name="period_date",
                        code="invalid_date",
                        severity="error",
                        message="Некорректная дата периода продаж",
                        raw_payload=raw_payload,
                    )
                )
            elif period_date and period_date > date.today():
                row_issues.append(
                    ValidationIssue(
                        row_number=row_number,
                        field_name="period_date",
                        code="future_period",
                        severity="error",
                        message="Период продаж не может быть в будущем",
                        raw_payload=raw_payload,
                    )
                )
            normalized["period_date"] = period_date
            try:
                normalized["quantity"] = _parse_float(normalized.get("quantity"))
            except (TypeError, ValueError):
                row_issues.append(
                    ValidationIssue(
                        row_number=row_number,
                        field_name="quantity",
                        code="invalid_numeric",
                        severity="error",
                        message="Количество должно быть числом",
                        raw_payload=raw_payload,
                    )
                )
            if normalized.get("revenue") not in (None, ""):
                try:
                    normalized["revenue"] = _parse_float(normalized.get("revenue"))
                except (TypeError, ValueError):
                    row_issues.append(
                        ValidationIssue(
                            row_number=row_number,
                            field_name="revenue",
                            code="invalid_numeric",
                            severity="warning",
                            message="Не удалось разобрать значение выручки",
                            raw_payload=raw_payload,
                        )
                    )

        elif source_type == "stock":
            for required in ("snapshot_date", "sku_code", "stock_free"):
                _require(normalized, required, row_number, row_issues, raw_payload)
            snapshot_date = _parse_date(normalized.get("snapshot_date"))
            if normalized.get("snapshot_date") not in (None, "") and snapshot_date is None:
                row_issues.append(
                    ValidationIssue(
                        row_number=row_number,
                        field_name="snapshot_date",
                        code="invalid_date",
                        severity="error",
                        message="Некорректная дата снимка",
                        raw_payload=raw_payload,
                    )
                )
            elif snapshot_date and snapshot_date > date.today():
                row_issues.append(
                    ValidationIssue(
                        row_number=row_number,
                        field_name="snapshot_date",
                        code="future_snapshot",
                        severity="error",
                        message="Дата снимка не может быть в будущем",
                        raw_payload=raw_payload,
                    )
                )
            normalized["snapshot_date"] = snapshot_date
            for field_name in ("stock_total", "stock_free"):
                if normalized.get(field_name) in (None, ""):
                    continue
                try:
                    normalized[field_name] = _parse_float(normalized.get(field_name))
                except (TypeError, ValueError):
                    row_issues.append(
                        ValidationIssue(
                            row_number=row_number,
                            field_name=field_name,
                            code="invalid_numeric",
                            severity="error",
                            message="Значение должно быть числом",
                            raw_payload=raw_payload,
                        )
                    )
            if isinstance(normalized.get("stock_free"), float) and normalized["stock_free"] < 0:
                row_issues.append(
                    ValidationIssue(
                        row_number=row_number,
                        field_name="stock_free",
                        code="negative_stock",
                        severity="warning",
                        message="Обнаружен отрицательный свободный остаток",
                        raw_payload=raw_payload,
                    )
                )

        elif source_type == "diy_clients":
            for required in ("client_name", "reserve_months", "safety_factor"):
                _require(normalized, required, row_number, row_issues, raw_payload)
            try:
                normalized["reserve_months"] = _parse_int(normalized.get("reserve_months"))
            except (TypeError, ValueError):
                normalized["reserve_months"] = None
            if normalized.get("reserve_months") not in {2, 3}:
                row_issues.append(
                    ValidationIssue(
                        row_number=row_number,
                        field_name="reserve_months",
                        code="invalid_reserve_months",
                        severity="error",
                        message="Горизонт резерва должен быть 2 или 3 месяца",
                        raw_payload=raw_payload,
                    )
                )
            try:
                normalized["safety_factor"] = _parse_float(normalized.get("safety_factor"))
            except (TypeError, ValueError):
                normalized["safety_factor"] = None
            if normalized.get("safety_factor") is None:
                row_issues.append(
                    ValidationIssue(
                        row_number=row_number,
                        field_name="safety_factor",
                        code="invalid_numeric",
                        severity="error",
                        message="Коэффициент запаса должен быть числом",
                        raw_payload=raw_payload,
                    )
                )
            elif isinstance(normalized["safety_factor"], float) and not (
                0.5 <= normalized["safety_factor"] <= 3.0
            ):
                row_issues.append(
                    ValidationIssue(
                        row_number=row_number,
                        field_name="safety_factor",
                        code="out_of_range",
                        severity="warning",
                        message="Коэффициент запаса вне рекомендованного диапазона",
                        raw_payload=raw_payload,
                    )
                )
            normalized["priority"] = _parse_int(normalized.get("priority")) or 1
            normalized["active"] = (
                True if normalized.get("active") is None else _parse_bool(normalized.get("active"))
            )
            if normalized.get("active") and normalized.get("client_name"):
                client_key = str(normalized["client_name"]).strip().lower()
                if client_key in seen_active_clients:
                    row_issues.append(
                        ValidationIssue(
                            row_number=row_number,
                            field_name="client_name",
                            code="duplicate_active_policy",
                            severity="error",
                            message="Для клиента уже есть активная политика DIY",
                            raw_payload=raw_payload,
                        )
                    )
                seen_active_clients.add(client_key)

        elif source_type == "category_structure":
            if normalized.get("sku_code") in (None, "") and normalized.get("product_name") in (
                None,
                "",
            ):
                row_issues.append(
                    ValidationIssue(
                        row_number=row_number,
                        field_name="sku_code",
                        code="missing_reference",
                        severity="error",
                        message="Нужен либо SKU, либо название товара",
                        raw_payload=raw_payload,
                    )
                )
            if normalized.get("category_level_3") and not normalized.get("category_level_2"):
                row_issues.append(
                    ValidationIssue(
                        row_number=row_number,
                        field_name="category_level_3",
                        code="broken_hierarchy",
                        severity="error",
                        message="Категория 3 уровня требует заполненный 2 уровень",
                        raw_payload=raw_payload,
                    )
                )
            if normalized.get("category_level_2") and not normalized.get("category_level_1"):
                row_issues.append(
                    ValidationIssue(
                        row_number=row_number,
                        field_name="category_level_2",
                        code="broken_hierarchy",
                        severity="error",
                        message="Категория 2 уровня требует заполненный 1 уровень",
                        raw_payload=raw_payload,
                    )
                )

        elif source_type == "inbound":
            for required in ("sku_code", "eta_date", "quantity", "status"):
                _require(normalized, required, row_number, row_issues, raw_payload)
            eta_date = _parse_date(normalized.get("eta_date"))
            if normalized.get("eta_date") not in (None, "") and eta_date is None:
                row_issues.append(
                    ValidationIssue(
                        row_number=row_number,
                        field_name="eta_date",
                        code="invalid_date",
                        severity="error",
                        message="Некорректная дата поставки",
                        raw_payload=raw_payload,
                    )
                )
            normalized["eta_date"] = eta_date
            try:
                normalized["quantity"] = _parse_float(normalized.get("quantity"))
            except (TypeError, ValueError):
                normalized["quantity"] = None
            if normalized.get("quantity") is None:
                row_issues.append(
                    ValidationIssue(
                        row_number=row_number,
                        field_name="quantity",
                        code="invalid_numeric",
                        severity="error",
                        message="Количество поставки должно быть числом",
                        raw_payload=raw_payload,
                    )
                )
            raw_status = normalized.get("status")
            normalized_status = INBOUND_STATUS_MAP.get(normalize_mapping_token(str(raw_status)))
            if normalized.get("status") not in (None, "") and normalized_status is None:
                row_issues.append(
                    ValidationIssue(
                        row_number=row_number,
                        field_name="status",
                        code="invalid_status",
                        severity="error",
                        message="Статус поставки не распознан",
                        raw_payload=raw_payload,
                    )
                )
            normalized["status"] = normalized_status

        signature = _duplicate_signature(source_type, normalized)
        if signature in seen_signatures:
            row_issues.append(
                ValidationIssue(
                    row_number=row_number,
                    field_name=None,
                    code="duplicate_row",
                    severity="warning",
                    message="Внутри загрузки найден потенциальный дубликат строки",
                    raw_payload=raw_payload,
                )
            )
        else:
            seen_signatures.add(signature)

        issues.extend(row_issues)
        if any(issue.severity in {"error", "critical"} for issue in row_issues):
            continue
        normalized_rows.append(normalized)

    warning_count = sum(issue.severity == "warning" for issue in issues)
    return ValidationResult(
        normalized_rows=normalized_rows,
        issues=issues,
        valid_rows=len(normalized_rows),
        failed_rows=max(len(frame.index) - len(normalized_rows), 0),
        warning_count=warning_count,
    )
