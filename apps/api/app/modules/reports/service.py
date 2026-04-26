from __future__ import annotations

from collections import Counter
from decimal import Decimal
import re

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from apps.api.app.db.models import (
    ManagementReportImport,
    ManagementReportMetric,
    ManagementReportRow,
    OrganizationUnit,
)
from apps.api.app.modules.reports.schemas import (
    ManagementReportImportResponse,
    ManagementReportKeyMetric,
    ManagementReportMetricResponse,
    ManagementReportRowResponse,
    ManagementReportSummaryResponse,
    OrganizationUnitResponse,
)

PRODUCT_GROUP_ABBR_PATTERN = re.compile(r"(?<![0-9a-zа-я])тг(?![0-9a-zа-я])", re.IGNORECASE)


def _serialize_import(item: ManagementReportImport) -> ManagementReportImportResponse:
    return ManagementReportImportResponse(
        id=item.id,
        fileName=item.file_name,
        checksum=item.checksum,
        reportYear=item.report_year,
        sheetCount=item.sheet_count,
        rawRowCount=item.raw_row_count,
        metricCount=item.metric_count,
        createdAt=item.created_at.isoformat(),
        updatedAt=item.updated_at.isoformat(),
        metadataPayload=item.metadata_payload,
    )


def _serialize_metric(item: ManagementReportMetric) -> ManagementReportMetricResponse:
    return ManagementReportMetricResponse(
        id=item.id,
        importId=item.import_id,
        sheetName=item.sheet_name,
        rowIndex=item.row_index,
        dimensionType=item.dimension_type,
        dimensionCode=item.dimension_code,
        dimensionName=item.dimension_name,
        metricName=item.metric_name,
        metricYear=item.metric_year,
        metricValue=item.metric_value,
        metricUnit=item.metric_unit,
    )


def _serialize_row(item: ManagementReportRow) -> ManagementReportRowResponse:
    return ManagementReportRowResponse(
        id=item.id,
        importId=item.import_id,
        sheetName=item.sheet_name,
        rowIndex=item.row_index,
        isHeader=item.is_header,
        parsedMetricCount=item.parsed_metric_count,
        rawValues=item.raw_values,
        notes=item.notes,
    )


def _serialize_unit(item: OrganizationUnit) -> OrganizationUnitResponse:
    return OrganizationUnitResponse(
        id=item.id,
        unitType=item.unit_type,
        code=item.code,
        name=item.name,
        displayName=item.display_name,
        sourceImportId=item.source_import_id,
    )


def get_latest_management_report_import(db: Session) -> ManagementReportImport | None:
    return db.scalars(
        select(ManagementReportImport).order_by(ManagementReportImport.created_at.desc())
    ).first()


def list_management_report_imports(db: Session) -> list[ManagementReportImportResponse]:
    imports = db.scalars(
        select(ManagementReportImport).order_by(ManagementReportImport.created_at.desc())
    ).all()
    return [_serialize_import(item) for item in imports]


def _latest_import_id(db: Session, import_id: str | None = None) -> str | None:
    if import_id:
        return import_id
    latest = get_latest_management_report_import(db)
    return latest.id if latest else None


def _metric_query(
    *,
    import_id: str | None,
    sheet_name: str | None = None,
    dimension_type: str | None = None,
    metric_name: str | None = None,
    metric_year: int | None = None,
    search: str | None = None,
) -> Select[tuple[ManagementReportMetric]]:
    statement = select(ManagementReportMetric)
    if import_id:
        statement = statement.where(ManagementReportMetric.import_id == import_id)
    if sheet_name:
        statement = statement.where(ManagementReportMetric.sheet_name == sheet_name)
    if dimension_type:
        statement = statement.where(ManagementReportMetric.dimension_type == dimension_type)
    if metric_name:
        statement = statement.where(ManagementReportMetric.metric_name == metric_name)
    if metric_year:
        statement = statement.where(ManagementReportMetric.metric_year == metric_year)
    if search:
        statement = statement.where(ManagementReportMetric.dimension_name.ilike(f"%{search}%"))
    return statement


def _top_metrics(
    db: Session,
    *,
    import_id: str,
    sheet_name: str,
    dimension_type: str,
    metric_name: str,
    metric_year: int,
    limit: int = 8,
) -> list[ManagementReportMetricResponse]:
    statement = (
        _metric_query(
            import_id=import_id,
            sheet_name=sheet_name,
            dimension_type=dimension_type,
            metric_name=metric_name,
            metric_year=metric_year,
        )
        .where(ManagementReportMetric.dimension_name != "Итого")
        .order_by(ManagementReportMetric.metric_value.desc(), ManagementReportMetric.dimension_name)
        .limit(max(min(limit, 50), 1))
    )
    return [_serialize_metric(row) for row in db.scalars(statement).all()]


def _top_product_group_earnings(
    db: Session,
    *,
    import_id: str,
    metric_year: int,
    limit: int = 8,
) -> list[dict[str, object]]:
    rows = db.scalars(
        select(ManagementReportMetric)
        .where(
            ManagementReportMetric.import_id == import_id,
            ManagementReportMetric.sheet_name == "Товарная группа",
            ManagementReportMetric.dimension_type == "product_group",
            ManagementReportMetric.metric_year == metric_year,
            ManagementReportMetric.metric_name.in_(("revenue", "profitability_pct")),
            ManagementReportMetric.dimension_name != "Итого",
        )
        .order_by(ManagementReportMetric.row_index)
    ).all()
    grouped: dict[str, dict[str, object]] = {}
    for metric in rows:
        item = grouped.setdefault(
            metric.dimension_name,
            {
                "dimensionName": metric.dimension_name,
                "metricYear": metric_year,
                "revenue": Decimal("0"),
                "profitabilityPct": Decimal("0"),
            },
        )
        if metric.metric_name == "revenue":
            item["revenue"] = metric.metric_value
        elif metric.metric_name == "profitability_pct":
            item["profitabilityPct"] = metric.metric_value

    ranked: list[dict[str, object]] = []
    for item in grouped.values():
        revenue = item["revenue"]
        profitability_pct = item["profitabilityPct"]
        if not isinstance(revenue, Decimal) or not isinstance(profitability_pct, Decimal):
            continue
        estimated_profit = revenue * profitability_pct / Decimal("100")
        ranked.append(
            {
                **item,
                "estimatedProfitRub": estimated_profit,
                "basis": "revenue_x_profitability_pct",
            }
        )
    ranked.sort(key=lambda item: item["estimatedProfitRub"], reverse=True)  # type: ignore[index]
    return ranked[: max(min(limit, 50), 1)]


def list_management_report_metrics(
    db: Session,
    *,
    import_id: str | None = None,
    sheet_name: str | None = None,
    dimension_type: str | None = None,
    metric_name: str | None = None,
    metric_year: int | None = None,
    search: str | None = None,
    limit: int = 100,
) -> list[ManagementReportMetricResponse]:
    selected_import_id = _latest_import_id(db, import_id)
    if selected_import_id is None:
        return []
    statement = _metric_query(
        import_id=selected_import_id,
        sheet_name=sheet_name,
        dimension_type=dimension_type,
        metric_name=metric_name,
        metric_year=metric_year,
        search=search,
    ).order_by(
        ManagementReportMetric.sheet_name,
        ManagementReportMetric.row_index,
        ManagementReportMetric.metric_year.nulls_last(),
        ManagementReportMetric.metric_name,
    )
    rows = db.scalars(statement.limit(max(min(limit, 500), 1))).all()
    return [_serialize_metric(row) for row in rows]


def list_management_report_rows(
    db: Session,
    *,
    import_id: str | None = None,
    sheet_name: str | None = None,
    limit: int = 100,
) -> list[ManagementReportRowResponse]:
    selected_import_id = _latest_import_id(db, import_id)
    if selected_import_id is None:
        return []
    statement = select(ManagementReportRow).where(ManagementReportRow.import_id == selected_import_id)
    if sheet_name:
        statement = statement.where(ManagementReportRow.sheet_name == sheet_name)
    rows = db.scalars(
        statement.order_by(ManagementReportRow.sheet_name, ManagementReportRow.row_index).limit(
            max(min(limit, 500), 1)
        )
    ).all()
    return [_serialize_row(row) for row in rows]


def list_organization_units(db: Session, *, import_id: str | None = None) -> list[OrganizationUnitResponse]:
    selected_import_id = _latest_import_id(db, import_id)
    statement = select(OrganizationUnit).where(OrganizationUnit.unit_type == "department")
    if selected_import_id:
        statement = statement.where(OrganizationUnit.source_import_id == selected_import_id)
    rows = db.scalars(statement.order_by(OrganizationUnit.code)).all()
    return [_serialize_unit(row) for row in rows]


def _first_metric(
    db: Session,
    *,
    import_id: str,
    sheet_name: str | None = None,
    dimension_type: str | None = None,
    dimension_name: str | None = None,
    metric_name: str,
    metric_year: int | None = None,
    order_desc: bool = False,
) -> ManagementReportMetric | None:
    statement = _metric_query(
        import_id=import_id,
        sheet_name=sheet_name,
        dimension_type=dimension_type,
        metric_name=metric_name,
        metric_year=metric_year,
        search=dimension_name,
    )
    if order_desc:
        statement = statement.order_by(ManagementReportMetric.metric_value.desc())
    else:
        statement = statement.order_by(ManagementReportMetric.row_index)
    return db.scalars(statement).first()


def _key_metric(
    label: str,
    metric: ManagementReportMetric | None,
) -> ManagementReportKeyMetric | None:
    if metric is None:
        return None
    return ManagementReportKeyMetric(
        label=label,
        value=metric.metric_value if isinstance(metric.metric_value, Decimal) else Decimal(str(metric.metric_value)),
        unit=metric.metric_unit,
        year=metric.metric_year,
        dimension=metric.dimension_name,
        sheetName=metric.sheet_name,
    )


def get_management_report_summary(db: Session) -> ManagementReportSummaryResponse:
    latest = get_latest_management_report_import(db)
    if latest is None:
        return ManagementReportSummaryResponse(
            latestImport=None,
            organizationUnits=[],
            keyMetrics=[],
            metricCountsBySheet={},
        )

    metrics = db.scalars(
        select(ManagementReportMetric).where(ManagementReportMetric.import_id == latest.id)
    ).all()
    metric_counts_by_sheet = dict(Counter(metric.sheet_name for metric in metrics))
    key_metrics = [
        item
        for item in [
            _key_metric(
                "Выручка подразделений 2025",
                _first_metric(
                    db,
                    import_id=latest.id,
                    sheet_name="Подразделение",
                    dimension_type="total",
                    metric_name="revenue",
                    metric_year=2025,
                ),
            ),
            _key_metric(
                "СПРОС / недопоставки 2025",
                _first_metric(
                    db,
                    import_id=latest.id,
                    sheet_name="СПРОС (недопоставки)",
                    dimension_type="demand_shortage",
                    metric_name="demand_shortage",
                    metric_year=2025,
                ),
            ),
            _key_metric(
                "Крупнейшая сеть по выручке 2025",
                _first_metric(
                    db,
                    import_id=latest.id,
                    sheet_name="Сети - разбивка по сетям",
                    dimension_type="network",
                    metric_name="revenue",
                    metric_year=2025,
                    order_desc=True,
                ),
            ),
            _key_metric(
                "Крупнейшая товарная группа 2025",
                _first_metric(
                    db,
                    import_id=latest.id,
                    sheet_name="Товарная группа",
                    dimension_type="product_group",
                    metric_name="revenue",
                    metric_year=2025,
                    order_desc=True,
                ),
            ),
            _key_metric(
                "Просроченная дебиторка 2025",
                _first_metric(
                    db,
                    import_id=latest.id,
                    sheet_name="ПДЗ",
                    dimension_type="total",
                    metric_name="overdue_receivables",
                    metric_year=2025,
                ),
            ),
        ]
        if item is not None
    ]
    return ManagementReportSummaryResponse(
        latestImport=_serialize_import(latest),
        organizationUnits=list_organization_units(db, import_id=latest.id),
        keyMetrics=key_metrics,
        metricCountsBySheet=metric_counts_by_sheet,
    )


def _is_product_group_question(question: str) -> bool:
    return (
        PRODUCT_GROUP_ABBR_PATTERN.search(question) is not None
        or "товарная группа" in question
        or ("товар" in question and "груп" in question)
        or any(token in question for token in ("товар", "продукт", "номенклатур"))
    )


def _is_profitability_question(question: str) -> bool:
    return any(token in question for token in ("выгод", "рентаб", "прибыл", "маржин"))


def _is_earnings_question(question: str) -> bool:
    return any(token in question for token in ("заработ", "прибыл", "доход", "маржин"))


def _question_year(question: str, fallback: int | None) -> int:
    if "2024" in question:
        return 2024
    if "2025" in question:
        return 2025
    return fallback or 2025


def _requested_rank(question: str) -> int:
    q = question.lower()
    rank_patterns = (
        (1, (r"\b1\b", r"1[-\s]?е", r"перв")),
        (2, (r"\b2\b", r"2[-\s]?е", r"втор")),
        (3, (r"\b3\b", r"3[-\s]?е", r"трет")),
        (4, (r"\b4\b", r"4[-\s]?е", r"четв")),
        (5, (r"\b5\b", r"5[-\s]?е", r"пят")),
    )
    # Follow-up text should win over the original question. If the last follow-up
    # is only a repair phrase ("ну а теперь ответишь?"), scan earlier segments.
    segments = [part.strip() for part in q.split("follow-up:") if part.strip()]
    for segment in reversed(segments or [q]):
        for rank, patterns in rank_patterns:
            if any(re.search(pattern, segment) for pattern in patterns):
                return rank
    return 1


def get_management_report_assistant_context(db: Session, question: str) -> dict[str, object]:
    summary = get_management_report_summary(db)
    latest = summary.latest_import
    if latest is None:
        return {"latest_import": None, "metrics": [], "summary": summary}

    q = question.lower()
    selected_year = _question_year(q, latest.report_year)
    requested_rank = _requested_rank(q)
    if _is_product_group_question(q) and _is_earnings_question(q):
        ranked_rows = _top_product_group_earnings(
            db,
            import_id=latest.id,
            metric_year=selected_year,
            limit=8,
        )
        return {
            "latest_import": latest,
            "summary": summary,
            "metrics": [],
            "filters": {
                "sheet_name": "Товарная группа",
                "metric_year": selected_year,
                "limit": 8,
                "sort": "estimated_profit_desc",
            },
            "answer_focus": {
                "kind": "top_product_group_earnings",
                "year": selected_year,
                "basis": "Расчётная маржа: выручка × рентабельность, %",
                "rows": ranked_rows,
                "requestedRank": requested_rank,
            },
        }

    if _is_product_group_question(q) and _is_profitability_question(q):
        metrics = _top_metrics(
            db,
            import_id=latest.id,
            sheet_name="Товарная группа",
            dimension_type="product_group",
            metric_name="profitability_pct",
            metric_year=selected_year,
            limit=8,
        )
        return {
            "latest_import": latest,
            "summary": summary,
            "metrics": metrics,
            "filters": {
                "sheet_name": "Товарная группа",
                "metric_name": "profitability_pct",
                "metric_year": selected_year,
                "limit": 8,
                "sort": "metric_value_desc",
            },
            "answer_focus": {
                "kind": "top_product_group_profitability",
                "year": selected_year,
                "basis": "Максимальная рентабельность, % на листе 'Товарная группа'",
                "requestedRank": requested_rank,
            },
        }

    filters: dict[str, object] = {"import_id": latest.id, "limit": 12}
    if "подраздел" in q or "отдел" in q:
        filters.update({"sheet_name": "Подразделение"})
    elif "пдз" in q or "дебитор" in q:
        filters.update({"sheet_name": "ПДЗ"})
    elif "спрос" in q or "недопостав" in q:
        filters.update({"dimension_type": "demand_shortage"})
    elif "сети" in q or "леман" in q or "контраг" in q:
        filters.update({"sheet_name": "Сети - разбивка по сетям"})
    elif "регион" in q:
        filters.update({"sheet_name": "Регионы ОПТ"})
    elif "товар" in q or "групп" in q:
        filters.update({"sheet_name": "Товарная группа"})

    if "2024" in q or "2025" in q:
        filters["metric_year"] = selected_year
    if "выруч" in q:
        filters["metric_name"] = "revenue"
    elif _is_profitability_question(q):
        filters["metric_name"] = "profitability_pct"
    elif "доля" in q:
        filters["metric_name"] = "distribution_share"

    metrics = list_management_report_metrics(db, **filters)  # type: ignore[arg-type]
    return {
        "latest_import": latest,
        "summary": summary,
        "metrics": metrics,
        "filters": {key: value for key, value in filters.items() if key != "import_id"},
    }


def count_management_report_imports(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(ManagementReportImport)) or 0
