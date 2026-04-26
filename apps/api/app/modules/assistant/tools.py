from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from time import perf_counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.app.db.models import Client, SalesFact, Sku
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
from apps.api.app.modules.reserve.domain import ReserveCalculationInput
from apps.api.app.modules.reserve.schemas import ReserveRowResponse
from apps.api.app.modules.reserve.service import (
    calculate_and_persist,
    get_portfolio_rows,
    get_run_detail,
    get_run_rows,
)
from apps.api.app.modules.reports.service import get_management_report_assistant_context
from apps.api.app.modules.stock.service import get_stock_coverage
from apps.api.app.modules.uploads.service import get_upload_file_detail, list_upload_files


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
    except Exception as exc:  # pragma: no cover - defensive for operational fallback
        return AssistantToolExecution(
            tool_name=name,
            status="failed",
            arguments=arguments,
            summary=str(exc),
            latency_ms=max(int((perf_counter() - started) * 1000), 1),
            warnings=[
                AssistantWarningData(
                    code=f"{name}_failed",
                    message=f"Инструмент {name} завершился ошибкой: {exc}",
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
        return datetime.fromisoformat(text).date().replace(day=1)
    except ValueError:
        return None


def _period_bounds(value: object) -> tuple[date | None, date | None]:
    start = _parse_date(value)
    if start is None:
        return None, None
    if start.month == 12:
        end = date(start.year + 1, 1, 1)
    else:
        end = date(start.year, start.month + 1, 1)
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
    category_ids = [bundle.context.selected_category_id] if bundle.context.selected_category_id else None
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
    return result, f"Сформирован reserve run {result.run.id} по {result.run.row_count} строкам", refs, []


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
    return sorted(filtered, key=lambda row: (row.shortage_qty, row.target_reserve_qty), reverse=True)[0]


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
        if not rows and bundle.context.selected_client_id and bundle.context.selected_sku_id:
            calculated = calculate_and_persist(
                db,
                ReserveCalculationInput(
                    client_ids=[bundle.context.selected_client_id],
                    sku_ids=[bundle.context.selected_sku_id],
                    demand_strategy="weighted_recent_average",
                    include_inbound=True,
                    inbound_statuses_to_count=["confirmed"],
                    persist_run=True,
                    horizon_days=60,
                ),
                created_by_id=None,
                reuse_existing=True,
            )
            rows = calculated.rows
            run = get_run_detail(db, calculated.run.id)
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
            [AssistantWarningData(code="missing_sku", message="Для SKU-сводки нужен SKU или pinned context.")],
        )
    detail = get_sku_detail(db, sku_id)
    if detail is None:
        return (
            None,
            "SKU не найден",
            [],
            [AssistantWarningData(code="sku_not_found", message="Запрошенный SKU не найден.", severity="error")],
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
            [AssistantWarningData(code="missing_client", message="Для client summary нужен клиент.")],
        )
    detail = get_client(db, client_id)
    if detail is None:
        return (
            None,
            "Клиент не найден",
            [],
            [AssistantWarningData(code="client_not_found", message="Запрошенный клиент не найден.", severity="error")],
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
    return {
        "detail": detail,
        "rows": rows,
        "top_skus": top_skus,
    }, f"Получена сводка по клиенту {detail.name}", refs, []


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
            item
            for item in timeline
            if bundle.context.selected_client_id in item.affected_clients
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
            [AssistantWarningData(code="missing_period", message="Укажите период продаж.", severity="warning")],
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
