from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from time import perf_counter
from types import SimpleNamespace

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.app.db.models import (
    Category,
    Client,
    InboundDelivery,
    ManagementReportImport,
    ManagementReportMetric,
    QualityIssue,
    ReserveRow,
    ReserveRun,
    SalesFact,
    Sku,
    SkuCost,
    StockSnapshot,
    UploadBatch,
)
from apps.api.app.modules.assistant.analytics_catalog import (
    DIMENSION_CATALOG,
    METRIC_CATALOG,
    metric_source,
    normalize_dimension_name,
    normalize_metric_name,
    unsupported_dimensions,
    unsupported_dimensions_for_metrics,
    unsupported_metrics,
)
from apps.api.app.modules.assistant.domain import (
    AssistantContextBundle,
    AssistantToolExecution,
    AssistantWarningData,
)
from apps.api.app.modules.catalog.service import get_sku_detail
from apps.api.app.modules.clients.service import (
    get_client,
    get_client_reserve_rows,
    get_client_top_skus,
)
from apps.api.app.modules.dashboard.service import get_dashboard_overview
from apps.api.app.modules.inbound.service import get_inbound_timeline
from apps.api.app.modules.quality.service import list_quality_issues
from apps.api.app.modules.reports.service import get_management_report_assistant_context
from apps.api.app.modules.reserve.domain import ReserveCalculationInput
from apps.api.app.modules.reserve.schemas import ReserveRowResponse
from apps.api.app.modules.reserve.service import (
    calculate_and_persist,
    get_portfolio_rows,
    get_run_detail,
    get_run_rows,
)
from apps.api.app.modules.stock.service import get_stock_coverage
from apps.api.app.modules.uploads.service import get_upload_file_detail, list_upload_files

logger = logging.getLogger(__name__)

ANALYTICS_METRIC_CATALOG = METRIC_CATALOG
ANALYTICS_DIMENSION_CATALOG = {key: spec.label for key, spec in DIMENSION_CATALOG.items()}


def _status_label(value: str) -> str:
    return {
        "critical": "критичный",
        "warning": "предупреждение",
        "healthy": "в норме",
        "no_history": "без истории",
        "inactive": "неактивный",
        "overstocked": "избыточный",
    }.get(value, value)


def _measure_tool(
    name: str,
    arguments: dict[str, object],
    fn: Callable[[], tuple[object, str, list[dict[str, object]], list[AssistantWarningData]]],
) -> AssistantToolExecution:
    started = perf_counter()
    try:
        payload, summary, source_refs, warnings = fn()
        return AssistantToolExecution(
            tool_name=name,
            status="completed",
            arguments=arguments,
            summary=summary,
            latency_ms=max(int((perf_counter() - started) * 1000), 1),
            payload=payload,
            warnings=warnings,
            source_refs=source_refs,
        )
    except Exception:  # pragma: no cover - defensive for operational fallback
        logger.exception(
            "Assistant tool failed",
            extra={"assistant_tool": name, "argument_keys": sorted(arguments.keys())},
        )
        return AssistantToolExecution(
            tool_name=name,
            status="failed",
            arguments=arguments,
            summary=f"Инструмент {name} временно недоступен. Детали сохранены в backend logs.",
            latency_ms=max(int((perf_counter() - started) * 1000), 1),
            warnings=[
                AssistantWarningData(
                    code=f"{name}_failed",
                    message=f"Инструмент {name} завершился ошибкой. Передайте traceId администратору.",
                    severity="error",
                )
            ],
        )


def _source_ref(
    *,
    source_type: str,
    source_label: str,
    entity_type: str,
    entity_id: str | None = None,
    external_key: str | None = None,
    freshness_at: str | None = None,
    role: str = "supporting",
    route: str | None = None,
    detail: str | None = None,
) -> dict[str, object]:
    return {
        "sourceType": source_type,
        "sourceLabel": source_label,
        "entityType": entity_type,
        "entityId": entity_id,
        "externalKey": external_key,
        "freshnessAt": freshness_at,
        "role": role,
        "route": route,
        "detail": detail,
    }


def _parse_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    if len(text) == 7:
        text = f"{text}-01"
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def _period_bounds(value: object) -> tuple[date | None, date | None]:
    if isinstance(value, str) and len(value.strip()) == 4 and value.strip().isdigit():
        year = int(value.strip())
        return date(year, 1, 1), date(year + 1, 1, 1)
    start = _parse_date(value)
    if start is None:
        return None, None
    end = date(start.year + 1, 1, 1) if start.month == 12 else date(start.year, start.month + 1, 1)
    return start, end


def tool_calculate_reserve(
    db: Session,
    bundle: AssistantContextBundle,
    *,
    created_by_id: str | None,
) -> AssistantToolExecution:
    client_id = bundle.context.selected_client_id
    sku_ids = list(bundle.route.extracted_sku_ids)
    if bundle.context.selected_sku_id and bundle.context.selected_sku_id not in sku_ids:
        sku_ids.append(bundle.context.selected_sku_id)
    category_ids = (
        [bundle.context.selected_category_id] if bundle.context.selected_category_id else None
    )
    return _measure_tool(
        "calculate_reserve",
        {
            "client_id": client_id,
            "sku_ids": sku_ids,
            "category_ids": category_ids or [],
            "reserve_months": bundle.route.reserve_months,
            "safety_factor": bundle.route.safety_factor,
        },
        lambda: _calculate_reserve_payload(
            db,
            client_id=client_id,
            sku_ids=sku_ids,
            category_ids=category_ids,
            reserve_months=bundle.route.reserve_months,
            safety_factor=bundle.route.safety_factor,
            created_by_id=created_by_id,
        ),
    )


def tool_get_reserve(
    db: Session,
    bundle: AssistantContextBundle,
    params: dict[str, object] | None = None,
) -> AssistantToolExecution:
    params = params or {}
    client_id = bundle.context.selected_client_id
    sku_ids = list(bundle.route.extracted_sku_ids)
    if bundle.context.selected_sku_id and bundle.context.selected_sku_id not in sku_ids:
        sku_ids.append(bundle.context.selected_sku_id)
    problematic_only = str(params.get("status") or params.get("risk") or "").lower() in {
        "problematic",
        "problematic_only",
        "at_risk",
        "critical",
        "warning",
    }
    return _measure_tool(
        "get_reserve",
        {
            "client_id": client_id,
            "sku_ids": sku_ids,
            "category_id": bundle.context.selected_category_id,
            "status": "problematic" if problematic_only else None,
        },
        lambda: _get_reserve_payload(
            db,
            client_id=client_id,
            sku_ids=sku_ids,
            category_id=bundle.context.selected_category_id,
            problematic_only=problematic_only,
        ),
    )


def _filter_reserve_rows(
    db: Session,
    rows: list[ReserveRowResponse],
    *,
    client_id: str | None,
    sku_ids: list[str],
    category_id: str | None,
    problematic_only: bool,
) -> list[ReserveRowResponse]:
    filtered = rows
    if client_id:
        filtered = [row for row in filtered if row.client_id == client_id]
    if sku_ids:
        selected = set(sku_ids)
        filtered = [row for row in filtered if row.sku_id in selected]
    if category_id:
        sku_ids_for_category = set(
            db.scalars(select(Sku.id).where(Sku.category_id == category_id)).all()
        )
        filtered = [row for row in filtered if row.sku_id in sku_ids_for_category]
    if problematic_only:
        filtered = [row for row in filtered if row.status in {"critical", "warning", "no_history"}]
    return sorted(
        filtered, key=lambda row: (row.shortage_qty, row.target_reserve_qty), reverse=True
    )


def _get_reserve_payload(
    db: Session,
    *,
    client_id: str | None,
    sku_ids: list[str],
    category_id: str | None,
    problematic_only: bool,
) -> tuple[object, str, list[dict[str, object]], list[AssistantWarningData]]:
    run, rows = get_portfolio_rows(db)
    if run is None:
        return (
            None,
            "Сохранённый portfolio reserve run не найден",
            [],
            [
                AssistantWarningData(
                    code="reserve_run_missing",
                    message="Нет сохранённого расчёта резерва. Для пересчёта запросите «пересчитай резерв».",
                    severity="warning",
                )
            ],
        )
    filtered = _filter_reserve_rows(
        db,
        rows,
        client_id=client_id,
        sku_ids=sku_ids,
        category_id=category_id,
        problematic_only=problematic_only,
    )
    detail = get_run_detail(db, run.id)
    run_summary = detail.run if detail is not None else None
    if run_summary is None:
        return (
            None,
            "Сводка reserve run недоступна",
            [],
            [
                AssistantWarningData(
                    code="reserve_run_summary_missing",
                    message="Сохранённый reserve run найден, но его сводка недоступна.",
                    severity="warning",
                )
            ],
        )
    refs = [
        _source_ref(
            source_type="reserve_engine",
            source_label=f"Сохранённый резерв {run.id}",
            entity_type="reserve_run",
            entity_id=run.id,
            freshness_at=(
                run.created_at.isoformat()
                if hasattr(run.created_at, "isoformat")
                else str(run.created_at)
            ),
            role="primary",
            route=f"/reserve?run={run.id}",
            detail=f"{len(filtered)} строк после фильтров, новых расчётов не запускалось",
        )
    ]
    warnings = []
    if not filtered:
        warnings.append(
            AssistantWarningData(
                code="reserve_no_rows",
                message="По выбранным фильтрам сохранённых строк резерва не найдено.",
                severity="warning",
            )
        )
    return (
        SimpleNamespace(run=run_summary, rows=filtered),
        f"Прочитан сохранённый reserve run {run.id}: {len(filtered)} строк",
        refs,
        warnings,
    )


def _calculate_reserve_payload(
    db: Session,
    *,
    client_id: str | None,
    sku_ids: list[str],
    category_ids: list[str] | None,
    reserve_months: int | None,
    safety_factor: float | None,
    created_by_id: str | None,
) -> tuple[object, str, list[dict[str, object]], list[AssistantWarningData]]:
    if client_id is None:
        return (
            None,
            "Клиент для расчёта не определён",
            [],
            [
                AssistantWarningData(
                    code="missing_client",
                    message="Для расчёта резерва нужен клиент или pinned context по клиенту.",
                    severity="warning",
                )
            ],
        )
    payload = ReserveCalculationInput(
        client_ids=[client_id],
        sku_ids=sku_ids or None,
        category_ids=category_ids,
        reserve_months_override=reserve_months,
        safety_factor_override=safety_factor,
        demand_strategy="weighted_recent_average",
        include_inbound=True,
        inbound_statuses_to_count=["confirmed"],
        persist_run=True,
        horizon_days=60,
    )
    result = calculate_and_persist(
        db,
        payload,
        created_by_id=created_by_id,
        reuse_existing=False,
    )
    refs = [
        _source_ref(
            source_type="reserve_engine",
            source_label=f"Запуск резерва {result.run.id}",
            entity_type="reserve_run",
            entity_id=result.run.id,
            freshness_at=result.run.created_at,
            role="primary",
            route=f"/reserve?run={result.run.id}",
            detail=f"{result.run.row_count} строк расчёта",
        )
    ]
    return (
        result,
        f"Сформирован reserve run {result.run.id} по {result.run.row_count} строкам",
        refs,
        [],
    )


def tool_reserve_explanation(db: Session, bundle: AssistantContextBundle) -> AssistantToolExecution:
    return _measure_tool(
        "get_reserve_explanation",
        {
            "client_id": bundle.context.selected_client_id,
            "sku_id": bundle.context.selected_sku_id,
            "run_id": bundle.context.selected_reserve_run_id,
        },
        lambda: _reserve_explanation_payload(db, bundle),
    )


def _pick_reserve_row(
    rows: list[ReserveRowResponse],
    *,
    client_id: str | None,
    sku_id: str | None,
) -> ReserveRowResponse | None:
    filtered = rows
    if sku_id:
        filtered = [row for row in filtered if row.sku_id == sku_id]
    if client_id:
        client_filtered = [row for row in filtered if row.client_id == client_id]
        if client_filtered:
            filtered = client_filtered
    if not filtered:
        return None
    return sorted(
        filtered, key=lambda row: (row.shortage_qty, row.target_reserve_qty), reverse=True
    )[0]


def _reserve_explanation_payload(
    db: Session,
    bundle: AssistantContextBundle,
) -> tuple[object, str, list[dict[str, object]], list[AssistantWarningData]]:
    run = None
    rows: list[ReserveRowResponse]
    if bundle.context.selected_reserve_run_id:
        run = get_run_detail(db, bundle.context.selected_reserve_run_id)
        rows = get_run_rows(db, bundle.context.selected_reserve_run_id)
    else:
        reserve_run, rows = get_portfolio_rows(db)
        run = get_run_detail(db, reserve_run.id) if reserve_run else None
    if not rows:
        return (
            None,
            "Нет сохранённого расчёта резерва для объяснения",
            [],
            [
                AssistantWarningData(
                    code="reserve_run_missing",
                    message="Сначала выполните расчёт резерва или закрепите конкретный reserve run.",
                    severity="warning",
                )
            ],
        )
    row = _pick_reserve_row(
        rows,
        client_id=bundle.context.selected_client_id,
        sku_id=bundle.context.selected_sku_id,
    )
    if row is None:
        return (
            None,
            "Подходящая reserve row не найдена",
            [],
            [
                AssistantWarningData(
                    code="reserve_row_not_found",
                    message="Для объяснения не удалось найти подходящую reserve row по выбранному контексту.",
                )
            ],
        )
    refs = []
    if run is not None:
        refs.append(
            _source_ref(
                source_type="reserve_engine",
                source_label=f"Запуск резерва {run.run.id}",
                entity_type="reserve_run",
                entity_id=run.run.id,
                freshness_at=run.run.created_at,
                role="primary",
                route=f"/reserve?run={run.run.id}",
                detail=f"Статус строки: {_status_label(row.status)}",
            )
        )
    refs.append(
        _source_ref(
            source_type="diy_policy",
            source_label=f"Политика клиента {row.client_name}",
            entity_type="diy_policy",
            entity_id=row.policy_id,
            role="supporting",
            route=f"/clients?client={row.client_id}",
            detail=f"Резерв {row.reserve_months} мес., коэффициент {row.safety_factor}",
        )
    )
    return {"row": row, "run": run}, f"Найдена строка для {row.article}", refs, []


def tool_get_sku_summary(db: Session, bundle: AssistantContextBundle) -> AssistantToolExecution:
    sku_id = bundle.context.selected_sku_id
    return _measure_tool(
        "get_sku_summary",
        {"sku_id": sku_id},
        lambda: _sku_summary_payload(db, sku_id),
    )


def _sku_summary_payload(
    db: Session,
    sku_id: str | None,
) -> tuple[object, str, list[dict[str, object]], list[AssistantWarningData]]:
    if sku_id is None:
        return (
            None,
            "SKU для сводки не определён",
            [],
            [
                AssistantWarningData(
                    code="missing_sku", message="Для SKU-сводки нужен SKU или pinned context."
                )
            ],
        )
    detail = get_sku_detail(db, sku_id)
    if detail is None:
        return (
            None,
            "SKU не найден",
            [],
            [
                AssistantWarningData(
                    code="sku_not_found", message="Запрошенный SKU не найден.", severity="error"
                )
            ],
        )
    refs = [
        _source_ref(
            source_type="catalog",
            source_label=f"SKU {detail.sku.article}",
            entity_type="sku",
            entity_id=detail.sku.id,
            external_key=detail.sku.article,
            role="primary",
            route=f"/sku?sku={detail.sku.id}",
            detail=detail.sku.name,
        )
    ]
    if detail.stock:
        refs.append(
            _source_ref(
                source_type="stock_snapshot",
                source_label=f"Склад {detail.stock.warehouse}",
                entity_type="stock_snapshot",
                entity_id=detail.sku.id,
                freshness_at=detail.stock.updated_at,
                role="supporting",
                route=f"/stock?sku={detail.sku.id}",
                detail=f"Свободный остаток {detail.stock.free_stock}",
            )
        )
    if detail.reserve_summary:
        refs.append(
            _source_ref(
                source_type="reserve_engine",
                source_label=f"Резервная сводка {detail.sku.article}",
                entity_type="sku",
                entity_id=detail.sku.id,
                role="supporting",
                route=f"/sku?sku={detail.sku.id}",
                detail=f"Дефицит {detail.reserve_summary.shortage_qty_total:.0f}",
            )
        )
    refs.append(
        _source_ref(
            source_type="sales_history",
            source_label=f"Продажи по {detail.sku.article}",
            entity_type="sales_history",
            entity_id=detail.sku.id,
            role="supporting",
            route=f"/sku?sku={detail.sku.id}",
            detail=f"{len(detail.sales)} мес. истории",
        )
    )
    return detail, f"Получена SKU-сводка для {detail.sku.article}", refs, []


def tool_get_client_summary(db: Session, bundle: AssistantContextBundle) -> AssistantToolExecution:
    client_id = bundle.context.selected_client_id
    return _measure_tool(
        "get_client_summary",
        {"client_id": client_id},
        lambda: _client_summary_payload(db, client_id),
    )


def _client_summary_payload(
    db: Session,
    client_id: str | None,
) -> tuple[object, str, list[dict[str, object]], list[AssistantWarningData]]:
    if client_id is None:
        return (
            None,
            "Клиент для сводки не определён",
            [],
            [
                AssistantWarningData(
                    code="missing_client", message="Для client summary нужен клиент."
                )
            ],
        )
    detail = get_client(db, client_id)
    if detail is None:
        return (
            None,
            "Клиент не найден",
            [],
            [
                AssistantWarningData(
                    code="client_not_found",
                    message="Запрошенный клиент не найден.",
                    severity="error",
                )
            ],
        )
    rows = get_client_reserve_rows(db, client_id)
    top_skus = get_client_top_skus(db, client_id)
    refs = [
        _source_ref(
            source_type="diy_policy",
            source_label=f"Политика {detail.name}",
            entity_type="client",
            entity_id=detail.id,
            role="primary",
            route=f"/clients?client={detail.id}",
            detail=f"Резерв {detail.reserve_months} мес., safety {detail.safety_factor}",
        ),
        _source_ref(
            source_type="reserve_engine",
            source_label=f"Reserve rows {detail.name}",
            entity_type="client",
            entity_id=detail.id,
            role="supporting",
            route=f"/clients?client={detail.id}",
            detail=f"{len(rows)} позиций, дефицит {detail.shortage_qty:.0f}",
        ),
    ]
    return (
        {
            "detail": detail,
            "rows": rows,
            "top_skus": top_skus,
        },
        f"Получена сводка по клиенту {detail.name}",
        refs,
        [],
    )


def tool_get_inbound_impact(db: Session, bundle: AssistantContextBundle) -> AssistantToolExecution:
    return _measure_tool(
        "get_inbound_impact",
        {
            "client_id": bundle.context.selected_client_id,
            "sku_id": bundle.context.selected_sku_id,
        },
        lambda: _inbound_impact_payload(db, bundle),
    )


def _inbound_impact_payload(
    db: Session,
    bundle: AssistantContextBundle,
) -> tuple[object, str, list[dict[str, object]], list[AssistantWarningData]]:
    timeline = get_inbound_timeline(db)
    if bundle.context.selected_sku_id:
        timeline = [item for item in timeline if item.sku_id == bundle.context.selected_sku_id]
    if bundle.context.selected_client_id:
        timeline = [
            item for item in timeline if bundle.context.selected_client_id in item.affected_clients
        ]
    timeline = sorted(timeline, key=lambda item: (item.reserve_impact, item.qty), reverse=True)
    refs = [
        _source_ref(
            source_type="inbound",
            source_label="Входящие поставки",
            entity_type="inbound_timeline",
            role="primary",
            route="/inbound",
            detail=f"{len(timeline)} релевантных поставок",
        )
    ]
    return timeline[:8], f"Найдено {len(timeline[:8])} релевантных поставок", refs, []


def tool_get_stock_risk(db: Session, bundle: AssistantContextBundle) -> AssistantToolExecution:
    return _measure_tool(
        "get_stock_coverage",
        {
            "category_id": bundle.context.selected_category_id,
            "sku_id": bundle.context.selected_sku_id,
        },
        lambda: _stock_risk_payload(db, bundle),
    )


def _stock_risk_payload(
    db: Session,
    bundle: AssistantContextBundle,
) -> tuple[object, str, list[dict[str, object]], list[AssistantWarningData]]:
    rows = get_stock_coverage(db, risk="low_stock")
    if bundle.route.extracted_category_name:
        rows = [row for row in rows if row.category_name == bundle.route.extracted_category_name]
    if bundle.context.selected_sku_id:
        rows = [row for row in rows if row.sku_id == bundle.context.selected_sku_id]
    refs = [
        _source_ref(
            source_type="stock_snapshot",
            source_label="Покрытие склада",
            entity_type="stock_coverage",
            role="primary",
            route="/stock",
            detail=f"{len(rows)} рискованных позиций",
        )
    ]
    return rows[:8], f"Найдено {len(rows[:8])} рискованных позиций", refs, []


def tool_get_upload_status(db: Session, bundle: AssistantContextBundle) -> AssistantToolExecution:
    return _measure_tool(
        "get_upload_status",
        {"upload_ids": bundle.context.selected_upload_ids},
        lambda: _upload_status_payload(db, bundle.context.selected_upload_ids),
    )


def _upload_status_payload(
    db: Session,
    upload_ids: list[str],
) -> tuple[object, str, list[dict[str, object]], list[AssistantWarningData]]:
    details = []
    if upload_ids:
        for upload_id in upload_ids[:3]:
            details.append(get_upload_file_detail(db, upload_id))
    else:
        details = [get_upload_file_detail(db, item.id) for item in list_upload_files(db)[:3]]
    refs = [
        _source_ref(
            source_type="upload_batch",
            source_label=detail.file.file_name,
            entity_type="upload_file",
            entity_id=detail.file.id,
            freshness_at=detail.file.uploaded_at,
            role="primary" if index == 0 else "supporting",
            route=f"/uploads?file={detail.file.id}",
            detail=f"Статус {detail.file.status}, проблем {detail.file.issue_counts.total}",
        )
        for index, detail in enumerate(details)
    ]
    return details, f"Собран статус по {len(details)} загрузкам", refs, []


def tool_get_quality_issues(db: Session, bundle: AssistantContextBundle) -> AssistantToolExecution:
    return _measure_tool(
        "get_quality_issues",
        {"sku_id": bundle.context.selected_sku_id},
        lambda: _quality_payload(db, bundle),
    )


def _quality_payload(
    db: Session,
    bundle: AssistantContextBundle,
) -> tuple[object, str, list[dict[str, object]], list[AssistantWarningData]]:
    search = None
    if bundle.context.selected_sku_id:
        sku_detail = get_sku_detail(db, bundle.context.selected_sku_id)
        if sku_detail is not None:
            search = sku_detail.sku.article
    issues = list_quality_issues(db, search=search)
    refs = [
        _source_ref(
            source_type="quality",
            source_label="Контур качества данных",
            entity_type="quality_issue",
            role="warning",
            route="/quality",
            detail=f"{len(issues[:6])} открытых проблем",
        )
    ]
    return issues[:6], f"Получено {len(issues[:6])} quality issues", refs, []


def tool_get_dashboard_summary(db: Session) -> AssistantToolExecution:
    return _measure_tool(
        "get_dashboard_summary",
        {},
        lambda: _dashboard_payload(db),
    )


def _dashboard_payload(
    db: Session,
) -> tuple[object, str, list[dict[str, object]], list[AssistantWarningData]]:
    overview = get_dashboard_overview(db)
    refs = [
        _source_ref(
            source_type="dashboard",
            source_label="Исполнительная сводка",
            entity_type="dashboard_summary",
            role="supporting",
            route="/",
            detail=f"Рискованных позиций {overview.summary.positions_at_risk}",
        )
    ]
    return overview, "Получена dashboard summary", refs, []


def tool_get_data_overview(db: Session) -> AssistantToolExecution:
    return _measure_tool(
        "get_data_overview",
        {},
        lambda: _data_overview_payload(db),
    )


def _count_rows(db: Session, model: type[object]) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def _data_overview_payload(
    db: Session,
) -> tuple[object, str, list[dict[str, object]], list[AssistantWarningData]]:
    active_clients = int(
        db.scalar(select(func.count()).select_from(Client).where(Client.is_active.is_(True))) or 0
    )
    active_skus = int(
        db.scalar(select(func.count()).select_from(Sku).where(Sku.active.is_(True))) or 0
    )
    category_count = _count_rows(db, Category)

    sales_count, sales_qty, sales_revenue, sales_min, sales_max = db.execute(
        select(
            func.count(SalesFact.id),
            func.coalesce(func.sum(SalesFact.quantity), 0),
            func.coalesce(func.sum(SalesFact.revenue_amount), 0),
            func.min(SalesFact.period_month),
            func.max(SalesFact.period_month),
        )
    ).one()

    stock_count, free_stock, latest_stock_at = db.execute(
        select(
            func.count(StockSnapshot.id),
            func.coalesce(func.sum(StockSnapshot.free_stock_qty), 0),
            func.max(StockSnapshot.snapshot_at),
        )
    ).one()

    inbound_count, inbound_qty, next_eta = db.execute(
        select(
            func.count(InboundDelivery.id),
            func.coalesce(func.sum(InboundDelivery.quantity), 0),
            func.min(InboundDelivery.eta_date),
        )
    ).one()

    reserve_run_count = _count_rows(db, ReserveRun)
    latest_run = db.scalars(
        select(ReserveRun).order_by(ReserveRun.created_at.desc()).limit(1)
    ).first()
    reserve_rows_count = _count_rows(db, ReserveRow)
    latest_reserve_shortage = 0.0
    latest_reserve_rows = 0
    if latest_run is not None:
        latest_reserve_rows, latest_reserve_shortage = db.execute(
            select(
                func.count(ReserveRow.id),
                func.coalesce(func.sum(ReserveRow.shortage_qty), 0),
            ).where(ReserveRow.run_id == latest_run.id)
        ).one()

    upload_count = _count_rows(db, UploadBatch)
    latest_upload = db.scalars(
        select(UploadBatch).order_by(UploadBatch.created_at.desc()).limit(1)
    ).first()
    upload_statuses = {
        status: int(count)
        for status, count in db.execute(
            select(UploadBatch.status, func.count(UploadBatch.id)).group_by(UploadBatch.status)
        ).all()
    }

    open_quality_count = int(
        db.scalar(
            select(func.count()).select_from(QualityIssue).where(QualityIssue.status == "open")
        )
        or 0
    )
    quality_by_severity = {
        severity: int(count)
        for severity, count in db.execute(
            select(QualityIssue.severity, func.count(QualityIssue.id))
            .where(QualityIssue.status == "open")
            .group_by(QualityIssue.severity)
        ).all()
    }

    latest_report = db.scalars(
        select(ManagementReportImport).order_by(ManagementReportImport.created_at.desc()).limit(1)
    ).first()
    report_metric_count = _count_rows(db, ManagementReportMetric)

    sections = [
        {
            "key": "catalog",
            "label": "Справочники",
            "route": "/sku",
            "count": active_clients + active_skus + category_count,
            "freshnessAt": None,
            "summary": f"{active_clients} активных клиентов, {active_skus} активных SKU, {category_count} категорий.",
        },
        {
            "key": "sales",
            "label": "Продажи",
            "route": "/stock",
            "count": int(sales_count or 0),
            "freshnessAt": sales_max.isoformat() if sales_max else None,
            "summary": (
                f"{int(sales_count or 0)} строк, период "
                f"{sales_min.isoformat() if sales_min else 'н/д'} — {sales_max.isoformat() if sales_max else 'н/д'}, "
                f"{float(sales_qty or 0):.1f} шт., {float(sales_revenue or 0):.2f} ₽."
            ),
        },
        {
            "key": "stock",
            "label": "Склад",
            "route": "/stock",
            "count": int(stock_count or 0),
            "freshnessAt": latest_stock_at.isoformat() if latest_stock_at else None,
            "summary": f"{int(stock_count or 0)} snapshots, свободный остаток {float(free_stock or 0):.1f} шт.",
        },
        {
            "key": "reserve",
            "label": "Резерв",
            "route": "/reserve",
            "count": int(reserve_rows_count or 0),
            "freshnessAt": latest_run.created_at.isoformat() if latest_run else None,
            "summary": (
                f"{reserve_run_count} reserve runs, {int(latest_reserve_rows or 0)} строк в последнем run, "
                f"дефицит последнего run {float(latest_reserve_shortage or 0):.1f} шт."
            ),
        },
        {
            "key": "inbound",
            "label": "Поставки",
            "route": "/inbound",
            "count": int(inbound_count or 0),
            "freshnessAt": next_eta.isoformat() if next_eta else None,
            "summary": f"{int(inbound_count or 0)} поставок, суммарно {float(inbound_qty or 0):.1f} шт.",
        },
        {
            "key": "uploads",
            "label": "Загрузки",
            "route": "/uploads",
            "count": int(upload_count or 0),
            "freshnessAt": latest_upload.created_at.isoformat() if latest_upload else None,
            "summary": f"{upload_count} batches, статусы: {upload_statuses or {}}.",
        },
        {
            "key": "quality",
            "label": "Качество данных",
            "route": "/quality",
            "count": open_quality_count,
            "freshnessAt": None,
            "summary": f"{open_quality_count} открытых issues, severity: {quality_by_severity or {}}.",
        },
        {
            "key": "management_report",
            "label": "Управленческий отчёт",
            "route": "/reports/management/summary",
            "count": int(report_metric_count or 0),
            "freshnessAt": latest_report.created_at.isoformat() if latest_report else None,
            "summary": (
                f"{latest_report.file_name}: {latest_report.raw_row_count} raw-строк, "
                f"{latest_report.metric_count} метрик."
                if latest_report
                else "Импортированный управленческий отчёт не найден."
            ),
        },
    ]
    populated_sections = [section for section in sections if int(section["count"] or 0) > 0]
    refs = [
        _source_ref(
            source_type=str(section["key"]),
            source_label=str(section["label"]),
            entity_type="data_overview",
            freshness_at=str(section["freshnessAt"]) if section.get("freshnessAt") else None,
            role=(
                "primary"
                if section["key"] in {"sales", "reserve", "management_report"}
                else "supporting"
            ),
            route=str(section["route"]),
            detail=str(section["summary"]),
        )
        for section in populated_sections
    ]
    warnings = []
    if not populated_sections:
        warnings.append(
            AssistantWarningData(
                code="data_overview_empty",
                message="В БД не найдено наполненных аналитических источников.",
                severity="warning",
            )
        )
    return (
        {
            "status": "completed" if populated_sections else "no_data",
            "sections": sections,
            "available_sections": [str(section["key"]) for section in populated_sections],
            "principles": [
                "read_only",
                "no_hidden_calculation",
                "source_refs_required",
                "no_synthetic_numbers",
            ],
        },
        f"Проверено {len(sections)} read-only источников, наполнено {len(populated_sections)}.",
        refs,
        warnings,
    )


def tool_get_management_report(db: Session, question: str) -> AssistantToolExecution:
    return _measure_tool(
        "get_management_report",
        {"question": question},
        lambda: _management_report_payload(db, question),
    )


def _management_report_payload(
    db: Session,
    question: str,
) -> tuple[object, str, list[dict[str, object]], list[AssistantWarningData]]:
    payload = get_management_report_assistant_context(db, question)
    latest = payload.get("latest_import")
    if latest is None:
        return (
            payload,
            "Управленческий отчёт не найден",
            [],
            [
                AssistantWarningData(
                    code="management_report_missing",
                    message="В БД нет импортированного управленческого отчёта.",
                    severity="warning",
                )
            ],
        )
    refs = [
        _source_ref(
            source_type="management_report",
            source_label=f"Управленческий отчёт {latest.file_name}",
            entity_type="management_report_import",
            entity_id=latest.id,
            external_key=latest.checksum[:12],
            freshness_at=latest.created_at,
            role="primary",
            route="/reports/management/summary",
            detail=f"{latest.raw_row_count} raw-строк, {latest.metric_count} метрик",
        )
    ]
    metrics = payload.get("metrics") or []
    return (
        payload,
        f"Собран контекст управленческого отчёта: {len(metrics)} релевантных метрик",
        refs,
        [],
    )


def tool_get_sales_summary(
    db: Session,
    bundle: AssistantContextBundle,
    params: dict[str, object],
) -> AssistantToolExecution:
    return _measure_tool(
        "get_sales_summary",
        {
            "date_from": params.get("date_from"),
            "date_to": params.get("date_to"),
            "client_id": params.get("client_id") or bundle.context.selected_client_id,
            "sku_id": params.get("sku_id") or bundle.context.selected_sku_id,
        },
        lambda: _sales_summary_payload(db, bundle, params),
    )


def _sales_summary_payload(
    db: Session,
    bundle: AssistantContextBundle,
    params: dict[str, object],
) -> tuple[object, str, list[dict[str, object]], list[AssistantWarningData]]:
    date_from = _parse_date(params.get("date_from"))
    date_to = _parse_date(params.get("date_to"))
    if date_from is None or date_to is None:
        return (
            {"status": "missing_fields"},
            "Для сводки продаж нужен корректный период",
            [],
            [
                AssistantWarningData(
                    code="missing_period", message="Укажите период продаж.", severity="warning"
                )
            ],
        )
    statement = select(
        func.coalesce(func.sum(SalesFact.quantity), 0),
        func.coalesce(func.sum(SalesFact.revenue_amount), 0),
        func.count(SalesFact.id),
    ).where(SalesFact.period_month >= date_from, SalesFact.period_month <= date_to)
    client_id = str(params.get("client_id") or bundle.context.selected_client_id or "") or None
    sku_id = str(params.get("sku_id") or bundle.context.selected_sku_id or "") or None
    if client_id:
        statement = statement.where(SalesFact.client_id == client_id)
    if sku_id:
        statement = statement.where(SalesFact.sku_id == sku_id)

    total_qty, total_revenue, row_count = db.execute(statement).one()
    client = db.get(Client, client_id) if client_id else None
    sku = db.get(Sku, sku_id) if sku_id else None
    payload = {
        "status": "completed" if row_count else "no_data",
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "client_id": client_id,
        "client_name": client.name if client else None,
        "sku_id": sku_id,
        "sku_article": sku.article if sku else None,
        "quantity": float(total_qty or 0),
        "revenue": float(total_revenue or 0),
        "row_count": int(row_count or 0),
    }
    refs = [
        _source_ref(
            source_type="sales",
            source_label="Sales facts",
            entity_type="sales_fact",
            entity_id=client_id or sku_id,
            role="primary",
            route="/sales",
            detail=f"{payload['row_count']} строк за период",
        )
    ]
    warnings = []
    if not row_count:
        warnings.append(
            AssistantWarningData(
                code="sales_no_data",
                message="За выбранный период и фильтры продаж не найдено.",
                severity="warning",
            )
        )
    return payload, f"Сводка продаж: {payload['row_count']} строк", refs, warnings


def tool_get_period_comparison(
    db: Session,
    bundle: AssistantContextBundle,
    params: dict[str, object],
) -> AssistantToolExecution:
    return _measure_tool(
        "get_period_comparison",
        {
            "metric": params.get("metric"),
            "current_period": params.get("current_period"),
            "previous_period": params.get("previous_period"),
            "client_id": params.get("client_id") or bundle.context.selected_client_id,
            "sku_id": params.get("sku_id") or bundle.context.selected_sku_id,
        },
        lambda: _period_comparison_payload(db, bundle, params),
    )


def _period_sales_value(
    db: Session,
    *,
    metric: str,
    period: object,
    client_id: str | None,
    sku_id: str | None,
) -> tuple[float, int]:
    start, end_exclusive = _period_bounds(period)
    if start is None or end_exclusive is None:
        return 0.0, 0
    field = SalesFact.quantity if metric == "quantity" else SalesFact.revenue_amount
    statement = select(func.coalesce(func.sum(field), 0), func.count(SalesFact.id)).where(
        SalesFact.period_month >= start,
        SalesFact.period_month < end_exclusive,
    )
    if client_id:
        statement = statement.where(SalesFact.client_id == client_id)
    if sku_id:
        statement = statement.where(SalesFact.sku_id == sku_id)
    value, row_count = db.execute(statement).one()
    if isinstance(value, Decimal):
        value = float(value)
    return float(value or 0), int(row_count or 0)


def _period_comparison_payload(
    db: Session,
    bundle: AssistantContextBundle,
    params: dict[str, object],
) -> tuple[object, str, list[dict[str, object]], list[AssistantWarningData]]:
    metric = str(params.get("metric") or "revenue").strip()
    metric = "quantity" if metric in {"qty", "quantity", "sales_qty", "продажи"} else "revenue"
    client_id = str(params.get("client_id") or bundle.context.selected_client_id or "") or None
    sku_id = str(params.get("sku_id") or bundle.context.selected_sku_id or "") or None
    current_value, current_count = _period_sales_value(
        db,
        metric=metric,
        period=params.get("current_period"),
        client_id=client_id,
        sku_id=sku_id,
    )
    previous_value, previous_count = _period_sales_value(
        db,
        metric=metric,
        period=params.get("previous_period"),
        client_id=client_id,
        sku_id=sku_id,
    )
    delta = current_value - previous_value
    delta_pct = None if previous_value == 0 else delta / previous_value * 100
    payload = {
        "status": "completed" if current_count or previous_count else "no_data",
        "metric": metric,
        "current_period": params.get("current_period"),
        "previous_period": params.get("previous_period"),
        "current_value": current_value,
        "previous_value": previous_value,
        "delta": delta,
        "delta_pct": delta_pct,
        "current_row_count": current_count,
        "previous_row_count": previous_count,
        "client_id": client_id,
        "sku_id": sku_id,
    }
    refs = [
        _source_ref(
            source_type="sales",
            source_label="Sales period comparison",
            entity_type="sales_fact",
            entity_id=client_id or sku_id,
            role="primary",
            route="/sales",
            detail=f"{current_count + previous_count} строк в сравнении",
        )
    ]
    warnings = []
    if not current_count and not previous_count:
        warnings.append(
            AssistantWarningData(
                code="comparison_no_data",
                message="Для выбранных периодов данных продаж не найдено.",
                severity="warning",
            )
        )
    return payload, "Сравнение периодов по продажам собрано", refs, warnings


def tool_get_analytics_slice(
    db: Session,
    bundle: AssistantContextBundle,
    params: dict[str, object],
) -> AssistantToolExecution:
    return _measure_tool(
        "get_analytics_slice",
        {
            "metrics": params.get("metrics") or params.get("metric"),
            "dimensions": params.get("dimensions") or params.get("dimension"),
            "filters": params.get("filters"),
            "period": params.get("period"),
            "date_from": params.get("date_from"),
            "date_to": params.get("date_to"),
            "client_id": params.get("client_id") or bundle.context.selected_client_id,
            "sku_id": params.get("sku_id") or bundle.context.selected_sku_id,
            "category_id": params.get("category_id") or bundle.context.selected_category_id,
            "sort_by": params.get("sort_by"),
            "sort_direction": params.get("sort_direction"),
            "limit": params.get("limit"),
        },
        lambda: _analytics_slice_payload(db, bundle, params),
    )


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _normalize_metric_name(value: str) -> str:
    return normalize_metric_name(value)


def _normalize_dimension_name(value: str) -> str:
    return normalize_dimension_name(value)


def _period_filter(params: dict[str, object]) -> tuple[date | None, date | None]:
    period = params.get("period")
    if isinstance(period, dict):
        date_from = period.get("date_from") or period.get("from")
        date_to = period.get("date_to") or period.get("to")
        if not date_from and not date_to:
            year = period.get("year")
            month = period.get("month")
            if str(year).isdigit() and str(month).isdigit():
                month_int = int(str(month))
                year_int = int(str(year))
                if 1 <= month_int <= 12:
                    next_year = year_int + (1 if month_int == 12 else 0)
                    next_month = 1 if month_int == 12 else month_int + 1
                    start = date(year_int, month_int, 1)
                    end = date(next_year, next_month, 1)
                    return start, date.fromordinal(end.toordinal() - 1)
    else:
        date_from = params.get("date_from")
        date_to = params.get("date_to")
    return _parse_date(date_from), _parse_date(date_to)


def _filter_value(params: dict[str, object], key: str) -> object | None:
    filters = params.get("filters")
    if isinstance(filters, dict) and filters.get(key) is not None:
        return filters.get(key)
    return params.get(key)


def _group_key(values: dict[str, object], dimensions: list[str]) -> tuple[object, ...]:
    return tuple(values.get(dimension) for dimension in dimensions)


def _row_from_group(
    dimensions: list[str], key: tuple[object, ...], metrics: dict[str, float]
) -> dict[str, object]:
    row = {dimension: value for dimension, value in zip(dimensions, key, strict=False)}
    row.update({name: round(value, 4) for name, value in metrics.items()})
    return row


def _quarter_for_month(month: int) -> str:
    return f"Q{((month - 1) // 3) + 1}"


def _analytics_slice_payload(
    db: Session,
    bundle: AssistantContextBundle,
    params: dict[str, object],
) -> tuple[object, str, list[dict[str, object]], list[AssistantWarningData]]:
    metrics = [
        _normalize_metric_name(item)
        for item in _string_list(params.get("metrics") or params.get("metric"))
    ]
    dimensions = [
        _normalize_dimension_name(item)
        for item in _string_list(params.get("dimensions") or params.get("dimension"))
    ]
    if not metrics:
        metrics = ["revenue"]
    if not dimensions:
        dimensions = ["client"]

    unknown_metrics = unsupported_metrics(metrics)
    unknown_dimensions = unsupported_dimensions(dimensions)
    unsupported_for_source = (
        unsupported_dimensions_for_metrics(metrics, dimensions)
        if not unknown_metrics and not unknown_dimensions
        else []
    )
    if unknown_metrics or unknown_dimensions or unsupported_for_source:
        return (
            {
                "status": "unsupported",
                "unsupported_metrics": unknown_metrics,
                "unsupported_dimensions": unknown_dimensions + unsupported_for_source,
                "supported_metrics": sorted(ANALYTICS_METRIC_CATALOG),
                "supported_dimensions": sorted(ANALYTICS_DIMENSION_CATALOG),
                "metric_catalog": {
                    key: {"label": spec.label, "unit": spec.unit, "source": spec.source}
                    for key, spec in METRIC_CATALOG.items()
                },
                "dimension_catalog": {
                    key: {"label": spec.label, "source": spec.source}
                    for key, spec in DIMENSION_CATALOG.items()
                },
            },
            "Запрошенный аналитический срез пока не поддерживается",
            [],
            [
                AssistantWarningData(
                    code="analytics_slice_unsupported",
                    message="Срез не поддерживается. В ответе перечислены доступные метрики и измерения.",
                    severity="warning",
                )
            ],
        )

    source = metric_source(metrics)
    if source is None:
        return (
            {
                "status": "unsupported",
                "supported_metrics": sorted(ANALYTICS_METRIC_CATALOG),
                "supported_dimensions": sorted(ANALYTICS_DIMENSION_CATALOG),
                "reason": "cross_source_slice_not_supported",
            },
            "Срез из нескольких источников пока нужно запрашивать отдельными вопросами",
            [],
            [
                AssistantWarningData(
                    code="cross_source_slice_not_supported",
                    message="Пока поддерживаются срезы внутри одного источника: sales, stock, reserve, inbound, catalog или management report.",
                    severity="warning",
                )
            ],
        )

    limit = max(min(int(params.get("limit") or 20), 100), 1)
    if source == "sales":
        rows = _analytics_sales_rows(db, bundle, params, metrics, dimensions, limit)
        source_ref = _source_ref(
            source_type="sales",
            source_label="Sales facts",
            entity_type="sales_fact",
            role="primary",
            route="/sales",
            detail=f"{len(rows)} агрегированных строк",
        )
        source_refs = [source_ref]
        if set(metrics).intersection({"cost_amount", "gross_profit", "gross_margin_pct"}):
            source_refs.append(
                _source_ref(
                    source_type="sku_costs",
                    source_label="Справочник себестоимости SKU",
                    entity_type="sku_cost",
                    role="supporting",
                    route="/sku",
                    detail="Себестоимость по артикулам из загруженного файла",
                )
            )
    elif source == "stock":
        rows = _analytics_stock_rows(db, bundle, params, metrics, dimensions, limit)
        source_ref = _source_ref(
            source_type="stock_snapshot",
            source_label="Stock snapshots",
            entity_type="stock_snapshot",
            role="primary",
            route="/stock",
            detail=f"{len(rows)} агрегированных строк",
        )
        source_refs = [source_ref]
    elif source == "reserve":
        rows = _analytics_reserve_rows(db, bundle, params, metrics, dimensions, limit)
        source_ref = _source_ref(
            source_type="reserve_engine",
            source_label="Сохранённые reserve rows",
            entity_type="reserve_row",
            role="primary",
            route="/reserve",
            detail=f"{len(rows)} агрегированных строк",
        )
        source_refs = [source_ref]
    elif source == "inbound":
        rows = _analytics_inbound_rows(db, bundle, params, metrics, dimensions, limit)
        source_ref = _source_ref(
            source_type="inbound",
            source_label="Inbound deliveries",
            entity_type="inbound_delivery",
            role="primary",
            route="/inbound",
            detail=f"{len(rows)} агрегированных строк",
        )
        source_refs = [source_ref]
    elif source == "catalog":
        rows = _analytics_sku_cost_rows(db, bundle, params, metrics, dimensions, limit)
        source_ref = _source_ref(
            source_type="sku_costs",
            source_label="Справочник себестоимости SKU",
            entity_type="sku_cost",
            role="primary",
            route="/sku",
            detail=f"{len(rows)} строк себестоимости",
        )
        source_refs = [source_ref]
    else:
        rows = _analytics_management_report_rows(db, params, metrics, dimensions, limit)
        source_ref = _source_ref(
            source_type="management_report",
            source_label="Управленческий отчёт",
            entity_type="management_report_metric",
            role="primary",
            route="/reports/management/summary",
            detail=f"{len(rows)} агрегированных строк",
        )
        source_refs = [source_ref]

    sort_by = str(params.get("sort_by") or (metrics[0] if metrics else "")).strip()
    sort_direction = str(params.get("sort_direction") or "desc").lower()
    if sort_by:
        rows = sorted(
            rows,
            key=lambda row: float(row.get(sort_by) or 0),
            reverse=sort_direction != "asc",
        )[:limit]

    totals = {
        metric: round(sum(float(row.get(metric) or 0) for row in rows), 4) for metric in metrics
    }
    status = "completed" if rows else "no_data"
    warnings = []
    if not rows:
        warnings.append(
            AssistantWarningData(
                code="analytics_slice_no_data",
                message="По выбранным метрикам, измерениям и фильтрам данных не найдено.",
                severity="warning",
            )
        )
    return (
        {
            "status": status,
            "source": source,
            "metrics": metrics,
            "dimensions": dimensions,
            "rows": rows,
            "totals": totals,
            "date_from": (
                _period_filter(params)[0].isoformat() if _period_filter(params)[0] else None
            ),
            "date_to": _period_filter(params)[1].isoformat() if _period_filter(params)[1] else None,
            "sort_by": sort_by or None,
            "sort_direction": sort_direction,
            "limit": limit,
            "query_description": (
                f"{source}: {', '.join(metrics)}"
                f"{' по ' + ', '.join(dimensions) if dimensions else ''}"
            ),
            "supported_metrics": sorted(ANALYTICS_METRIC_CATALOG),
            "supported_dimensions": sorted(ANALYTICS_DIMENSION_CATALOG),
            "sourceRefs": source_refs,
        },
        f"Аналитический срез {source}: {len(rows)} строк",
        source_refs,
        warnings,
    )


def _analytics_sales_rows(
    db: Session,
    bundle: AssistantContextBundle,
    params: dict[str, object],
    metrics: list[str],
    dimensions: list[str],
    limit: int,
) -> list[dict[str, object]]:
    date_from, date_to = _period_filter(params)
    statement = select(SalesFact)
    if date_from:
        statement = statement.where(SalesFact.period_month >= date_from)
    if date_to:
        statement = statement.where(SalesFact.period_month <= date_to)
    client_id = (
        str(_filter_value(params, "client_id") or bundle.context.selected_client_id or "") or None
    )
    sku_id = str(_filter_value(params, "sku_id") or bundle.context.selected_sku_id or "") or None
    category_id = (
        str(_filter_value(params, "category_id") or bundle.context.selected_category_id or "")
        or None
    )
    if client_id:
        statement = statement.where(SalesFact.client_id == client_id)
    if sku_id:
        statement = statement.where(SalesFact.sku_id == sku_id)
    facts = db.scalars(statement).all()
    selected_article = str(_filter_value(params, "article") or "").strip().lower()
    client_cache = {item.id: item for item in db.scalars(select(Client)).all()}
    sku_cache = {item.id: item for item in db.scalars(select(Sku)).all()}
    cost_cache = {item.article: item for item in db.scalars(select(SkuCost)).all()}
    category_cache = {item.id: item for item in db.scalars(select(Category)).all()}
    grouped: dict[tuple[object, ...], dict[str, float]] = {}
    margin_support: dict[tuple[object, ...], dict[str, float]] = {}
    for fact in facts:
        sku = sku_cache.get(fact.sku_id)
        if selected_article and (not sku or sku.article.lower() != selected_article):
            continue
        category = category_cache.get(fact.category_id or (sku.category_id if sku else ""))
        if category_id and (not category or category.id != category_id):
            continue
        client = client_cache.get(fact.client_id)
        quantity = float(fact.quantity or 0)
        revenue = float(fact.revenue_amount or 0)
        unit_cost = (
            float(cost_cache[sku.article].cost_rub) if sku and sku.article in cost_cache else 0.0
        )
        cost_amount = quantity * unit_cost
        gross_profit = revenue - cost_amount
        values = {
            "client": client.name if client else fact.client_id,
            "region": client.region if client else None,
            "sku": sku.name if sku else fact.sku_id,
            "article": sku.article if sku else fact.sku_id,
            "brand": sku.brand if sku else None,
            "category": category.name if category else None,
            "month": fact.period_month.strftime("%Y-%m"),
            "quarter": f"{fact.period_month.year}-{_quarter_for_month(fact.period_month.month)}",
            "year": fact.period_month.year,
        }
        item = grouped.setdefault(
            _group_key(values, dimensions), {metric: 0.0 for metric in metrics}
        )
        group_key = _group_key(values, dimensions)
        if "sales_qty" in item:
            item["sales_qty"] += quantity
        if "revenue" in item:
            item["revenue"] += revenue
        if "cost_amount" in item:
            item["cost_amount"] += cost_amount
        if "gross_profit" in item:
            item["gross_profit"] += gross_profit
        if "gross_margin_pct" in item:
            support = margin_support.setdefault(group_key, {"revenue": 0.0, "profit": 0.0})
            support["revenue"] += revenue
            support["profit"] += gross_profit
    if "gross_margin_pct" in metrics:
        for key, item in grouped.items():
            support = margin_support.get(key, {"revenue": 0.0, "profit": 0.0})
            item["gross_margin_pct"] = (
                (support["profit"] / support["revenue"]) * 100 if support["revenue"] else 0.0
            )
    return _sorted_metric_rows(dimensions, grouped, metrics, limit)


def _analytics_stock_rows(
    db: Session,
    bundle: AssistantContextBundle,
    params: dict[str, object],
    metrics: list[str],
    dimensions: list[str],
    limit: int,
) -> list[dict[str, object]]:
    snapshots = db.scalars(select(StockSnapshot)).all()
    latest_at_by_sku: dict[str, datetime] = {}
    for snapshot in snapshots:
        current = latest_at_by_sku.get(snapshot.sku_id)
        if current is None or snapshot.snapshot_at > current:
            latest_at_by_sku[snapshot.sku_id] = snapshot.snapshot_at
    sku_cache = {item.id: item for item in db.scalars(select(Sku)).all()}
    category_cache = {item.id: item for item in db.scalars(select(Category)).all()}
    selected_sku_id = (
        str(_filter_value(params, "sku_id") or bundle.context.selected_sku_id or "") or None
    )
    selected_category_id = (
        str(_filter_value(params, "category_id") or bundle.context.selected_category_id or "")
        or None
    )
    grouped: dict[tuple[object, ...], dict[str, float]] = {}
    for snapshot in snapshots:
        if latest_at_by_sku.get(snapshot.sku_id) != snapshot.snapshot_at:
            continue
        sku = sku_cache.get(snapshot.sku_id)
        if selected_sku_id and snapshot.sku_id != selected_sku_id:
            continue
        if selected_category_id and (not sku or sku.category_id != selected_category_id):
            continue
        category = category_cache.get(sku.category_id) if sku and sku.category_id else None
        values = {
            "sku": sku.name if sku else snapshot.sku_id,
            "article": sku.article if sku else snapshot.sku_id,
            "brand": sku.brand if sku else None,
            "category": category.name if category else None,
            "warehouse": snapshot.warehouse_code,
            "month": snapshot.snapshot_at.strftime("%Y-%m"),
            "quarter": f"{snapshot.snapshot_at.year}-{_quarter_for_month(snapshot.snapshot_at.month)}",
            "year": snapshot.snapshot_at.year,
        }
        item = grouped.setdefault(
            _group_key(values, dimensions), {metric: 0.0 for metric in metrics}
        )
        if "stock_qty" in item:
            item["stock_qty"] += float(snapshot.free_stock_qty or 0) + float(
                snapshot.reserved_like_qty or 0
            )
        if "free_stock" in item:
            item["free_stock"] += float(snapshot.free_stock_qty or 0)
    return _sorted_metric_rows(dimensions, grouped, metrics, limit)


def _analytics_reserve_rows(
    db: Session,
    bundle: AssistantContextBundle,
    params: dict[str, object],
    metrics: list[str],
    dimensions: list[str],
    limit: int,
) -> list[dict[str, object]]:
    _, reserve_rows = get_portfolio_rows(db)
    client_id = (
        str(_filter_value(params, "client_id") or bundle.context.selected_client_id or "") or None
    )
    sku_id = str(_filter_value(params, "sku_id") or bundle.context.selected_sku_id or "") or None
    sku_cache = {item.id: item for item in db.scalars(select(Sku)).all()}
    grouped: dict[tuple[object, ...], dict[str, float]] = {}
    for row in reserve_rows:
        if client_id and row.client_id != client_id:
            continue
        if sku_id and row.sku_id != sku_id:
            continue
        sku = sku_cache.get(row.sku_id)
        values = {
            "client": row.client_name,
            "sku": row.product_name,
            "article": row.article,
            "brand": sku.brand if sku else None,
            "category": row.category,
        }
        item = grouped.setdefault(
            _group_key(values, dimensions), {metric: 0.0 for metric in metrics}
        )
        if "reserve_qty" in item:
            item["reserve_qty"] += float(row.target_reserve_qty or 0)
        if "shortage_qty" in item:
            item["shortage_qty"] += float(row.shortage_qty or 0)
        if "coverage_months" in item:
            item["coverage_months"] = max(float(row.coverage_months or 0), item["coverage_months"])
    return _sorted_metric_rows(dimensions, grouped, metrics, limit)


def _analytics_inbound_rows(
    db: Session,
    bundle: AssistantContextBundle,
    params: dict[str, object],
    metrics: list[str],
    dimensions: list[str],
    limit: int,
) -> list[dict[str, object]]:
    date_from, date_to = _period_filter(params)
    deliveries = db.scalars(select(InboundDelivery)).all()
    sku_cache = {item.id: item for item in db.scalars(select(Sku)).all()}
    category_cache = {item.id: item for item in db.scalars(select(Category)).all()}
    selected_sku_id = (
        str(_filter_value(params, "sku_id") or bundle.context.selected_sku_id or "") or None
    )
    grouped: dict[tuple[object, ...], dict[str, float]] = {}
    for delivery in deliveries:
        if date_from and delivery.eta_date < date_from:
            continue
        if date_to and delivery.eta_date > date_to:
            continue
        if selected_sku_id and delivery.sku_id != selected_sku_id:
            continue
        sku = sku_cache.get(delivery.sku_id)
        category = category_cache.get(sku.category_id) if sku and sku.category_id else None
        values = {
            "sku": sku.name if sku else delivery.sku_id,
            "article": sku.article if sku else delivery.sku_id,
            "brand": sku.brand if sku else None,
            "category": category.name if category else None,
            "month": delivery.eta_date.strftime("%Y-%m"),
            "quarter": f"{delivery.eta_date.year}-{_quarter_for_month(delivery.eta_date.month)}",
            "year": delivery.eta_date.year,
        }
        item = grouped.setdefault(
            _group_key(values, dimensions), {metric: 0.0 for metric in metrics}
        )
        if "inbound_qty" in item:
            item["inbound_qty"] += float(delivery.quantity or 0)
    return _sorted_metric_rows(dimensions, grouped, metrics, limit)


def _analytics_sku_cost_rows(
    db: Session,
    bundle: AssistantContextBundle,
    params: dict[str, object],
    metrics: list[str],
    dimensions: list[str],
    limit: int,
) -> list[dict[str, object]]:
    selected_sku_id = (
        str(_filter_value(params, "sku_id") or bundle.context.selected_sku_id or "") or None
    )
    selected_category_id = (
        str(_filter_value(params, "category_id") or bundle.context.selected_category_id or "")
        or None
    )
    selected_article = str(_filter_value(params, "article") or "").strip().lower()
    sku_cache = {item.id: item for item in db.scalars(select(Sku)).all()}
    category_cache = {item.id: item for item in db.scalars(select(Category)).all()}
    grouped: dict[tuple[object, ...], dict[str, float]] = {}
    for cost in db.scalars(select(SkuCost)).all():
        sku = sku_cache.get(cost.sku_id or "")
        if selected_sku_id and cost.sku_id != selected_sku_id:
            continue
        if selected_article and cost.article.lower() != selected_article:
            continue
        if selected_category_id and (not sku or sku.category_id != selected_category_id):
            continue
        category = category_cache.get(sku.category_id) if sku and sku.category_id else None
        values = {
            "sku": sku.name if sku else cost.product_name,
            "article": cost.article,
            "brand": sku.brand if sku else None,
            "category": category.name if category else None,
        }
        item = grouped.setdefault(
            _group_key(values, dimensions), {metric: 0.0 for metric in metrics}
        )
        if "unit_cost" in item:
            item["unit_cost"] = float(cost.cost_rub or 0)
    return _sorted_metric_rows(dimensions, grouped, metrics, limit)


def _analytics_management_report_rows(
    db: Session,
    params: dict[str, object],
    metrics: list[str],
    dimensions: list[str],
    limit: int,
) -> list[dict[str, object]]:
    metric_names = {"profitability": "profitability_pct", "margin": "profitability_pct"}
    wanted_metric_names = [metric_names[item] for item in metrics if item in metric_names]
    if not wanted_metric_names:
        return []
    statement = select(ManagementReportMetric).where(
        ManagementReportMetric.metric_name.in_(wanted_metric_names)
    )
    period = params.get("period")
    year = None
    if isinstance(period, dict):
        date_from = str(period.get("date_from") or "")
        if len(date_from) >= 4 and date_from[:4].isdigit():
            year = int(date_from[:4])
    if year is not None:
        statement = statement.where(ManagementReportMetric.metric_year == year)
    rows = db.scalars(statement).all()
    grouped: dict[tuple[object, ...], dict[str, float]] = {}
    counts: dict[tuple[object, ...], int] = {}
    for metric in rows:
        values = {
            "product_group": metric.dimension_name,
            "year": metric.metric_year,
            "category": metric.dimension_name,
        }
        key = _group_key(values, dimensions)
        item = grouped.setdefault(key, {requested: 0.0 for requested in metrics})
        counts[key] = counts.get(key, 0) + 1
        for requested in metrics:
            item[requested] += float(metric.metric_value or 0)
    for key, item in grouped.items():
        count = counts.get(key, 1) or 1
        for metric in item:
            item[metric] = item[metric] / count
    return _sorted_metric_rows(dimensions, grouped, metrics, limit)


def _sorted_metric_rows(
    dimensions: list[str],
    grouped: dict[tuple[object, ...], dict[str, float]],
    metrics: list[str],
    limit: int,
) -> list[dict[str, object]]:
    primary_metric = metrics[0]
    rows = [
        _row_from_group(dimensions, key, metric_values) for key, metric_values in grouped.items()
    ]
    return sorted(rows, key=lambda row: float(row.get(primary_metric) or 0), reverse=True)[:limit]
