from __future__ import annotations

from collections import OrderedDict

from sqlalchemy.orm import Session

from apps.api.app.common.utils import generate_id, utc_now
from apps.api.app.core.config import Settings
from apps.api.app.modules.assistant.context import build_context_bundle
from apps.api.app.modules.assistant.domain import (
    AssistantAnswerDraft,
    AssistantContextBundle,
    AssistantResolvedContext,
    AssistantToolExecution,
    AssistantWarningData,
)
from apps.api.app.modules.assistant.providers import finalize_with_provider
from apps.api.app.modules.assistant.routing import route_question
from apps.api.app.modules.assistant.schemas import (
    AssistantAnswerSection,
    AssistantFollowupSuggestion,
    AssistantPinnedContext,
    AssistantQueryRequest,
    AssistantResponse,
    AssistantSourceRef,
    AssistantToolCall,
    AssistantWarning,
)
from apps.api.app.modules.assistant.tools import (
    tool_calculate_reserve,
    tool_get_client_summary,
    tool_get_dashboard_summary,
    tool_get_inbound_impact,
    tool_get_quality_issues,
    tool_get_sku_summary,
    tool_get_stock_risk,
    tool_get_upload_status,
    tool_reserve_explanation,
)


def _qty(value: float | int | None) -> str:
    if value is None:
        return "н/д"
    return f"{float(value):.1f}".rstrip("0").rstrip(".")


def _localize_status_reason(value: str | None) -> str:
    if not value:
        return "Причина не указана"
    replacements = {
        "Coverage is far below target reserve": "Покрытие значительно ниже целевого резерва",
        "Coverage is below target reserve": "Покрытие ниже целевого резерва",
        "Insufficient history": "Недостаточно истории",
    }
    return replacements.get(value, value)


def _localize_status_code(value: str) -> str:
    return {
        "critical": "критичный",
        "warning": "предупреждение",
        "healthy": "в норме",
        "no_history": "без истории",
        "inactive": "неактивный",
        "overstocked": "избыточный",
    }.get(value, value)


def _localize_signal(value: str) -> str:
    return {
        "falling_demand": "Спрос снижается относительно последних месяцев",
        "rising_demand": "Спрос ускоряется относительно базовой истории",
        "volatile_history": "История спроса нестабильна",
        "weak_history": "Истории продаж недостаточно для уверенной оценки",
        "no_recent_sales": "Нет недавних продаж в выбранном окне",
        "insufficient_history": "Недостаточно истории на разрешённых уровнях fallback",
        "strict_recent_fell_back_to_6m": "Строгая recent average опиралась на 6-месячное окно",
        "proxy_history_used": "Использована прокси-история вместо прямой клиентской истории",
    }.get(value, value)


def _section(
    *,
    section_type: str,
    title: str,
    body: str | None = None,
    metrics: list[dict[str, object]] | None = None,
    rows: list[dict[str, object]] | None = None,
    items: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": generate_id("asec"),
        "type": section_type,
        "title": title,
        "body": body,
        "metrics": metrics or [],
        "rows": rows or [],
        "items": items or [],
    }


def _metric(key: str, label: str, value: str, tone: str = "neutral") -> dict[str, object]:
    return {"key": key, "label": label, "value": value, "tone": tone}


def _context_schema(context: AssistantResolvedContext) -> AssistantPinnedContext:
    return AssistantPinnedContext(
        selectedClientId=context.selected_client_id,
        selectedSkuId=context.selected_sku_id,
        selectedUploadIds=context.selected_upload_ids,
        selectedReserveRunId=context.selected_reserve_run_id,
        selectedCategoryId=context.selected_category_id,
    )


def _dedupe_source_refs(executions: list[AssistantToolExecution]) -> list[dict[str, object]]:
    seen: OrderedDict[tuple[str, str | None], dict[str, object]] = OrderedDict()
    for execution in executions:
        for ref in execution.source_refs:
            key = (str(ref.get("sourceType")), ref.get("entityId"))  # type: ignore[arg-type]
            seen.setdefault(key, ref)
    return list(seen.values())


def _collect_warnings(bundle: AssistantContextBundle, executions: list[AssistantToolExecution]) -> list[AssistantWarningData]:
    warnings: list[AssistantWarningData] = [*bundle.warnings]
    for execution in executions:
        warnings.extend(execution.warnings)
    unique: OrderedDict[tuple[str, str], AssistantWarningData] = OrderedDict()
    for warning in warnings:
        unique.setdefault((warning.code, warning.message), warning)
    return list(unique.values())


def _generic_followups(intent: str, bundle: AssistantContextBundle) -> list[dict[str, object]]:
    if intent == "reserve_calculation":
        return [
            {
                "id": "critical_positions",
                "label": "Показать только critical",
                "prompt": "Покажи только критичные позиции по этому расчёту резерва",
                "action": "query",
            },
            {
                "id": "reserve_3m",
                "label": "Пересчитать на 3 месяца",
                "prompt": "Пересчитай резерв на 3 месяца по тому же контексту",
                "action": "query",
            },
        ]
    if intent == "reserve_explanation":
        return [
            {
                "id": "open_sku",
                "label": "Открыть SKU",
                "prompt": "Суммируй ситуацию по этому SKU",
                "action": "query",
                "route": f"/sku?sku={bundle.context.selected_sku_id}" if bundle.context.selected_sku_id else None,
            },
            {
                "id": "inbound_impact",
                "label": "Показать влияние поставок",
                "prompt": "Какие поставки снижают дефицит по этому SKU?",
                "action": "query",
            },
        ]
    if intent in {"sku_summary", "stock_risk_summary"}:
        return [
            {
                "id": "stock_risk",
                "label": "Показать риск покрытия",
                "prompt": "Покажи позиции с низким покрытием по этому контексту",
                "action": "query",
            },
            {
                "id": "quality_check",
                "label": "Проверить качество данных",
                "prompt": "Есть ли quality issues, влияющие на этот результат?",
                "action": "query",
            },
        ]
    if intent in {"client_summary", "diy_coverage_check"}:
        return [
            {
                "id": "below_reserve",
                "label": "Позиции ниже резерва",
                "prompt": "Покажи позиции ниже резерва по этому клиенту",
                "action": "query",
            },
            {
                "id": "top_skus",
                "label": "Топ SKU риска",
                "prompt": "Покажи SKU с наибольшим дефицитом по этому клиенту",
                "action": "query",
            },
        ]
    if intent in {"upload_status_summary", "quality_issue_summary"}:
        return [
            {
                "id": "uploads",
                "label": "Открыть загрузки",
                "prompt": "Покажи статус последних загрузок",
                "action": "open",
                "route": "/uploads",
            },
            {
                "id": "quality",
                "label": "Открыть quality",
                "prompt": "Покажи открытые quality issues",
                "action": "open",
                "route": "/quality",
            },
        ]
    return [
        {
            "id": "dashboard",
            "label": "Показать общую сводку",
            "prompt": "Покажи общую сводку по рискам и дефициту",
            "action": "query",
        }
    ]


def _reserve_rows_preview(rows: list[object], limit: int = 5) -> list[dict[str, object]]:
    preview: list[dict[str, object]] = []
    for row in rows[:limit]:
        preview.append(
            {
                "article": getattr(row, "article", ""),
                "clientName": getattr(row, "client_name", ""),
                "productName": getattr(row, "product_name", ""),
                "shortageQty": getattr(row, "shortage_qty", 0),
                "coverageMonths": getattr(row, "coverage_months", None),
                "status": getattr(row, "status", ""),
            }
        )
    return preview


def _compose_unsupported(bundle: AssistantContextBundle) -> AssistantAnswerDraft:
    return AssistantAnswerDraft(
        intent="unsupported_or_ambiguous",
        status="unsupported",
        confidence=0.35,
        title="Нужна более предметная постановка вопроса",
        summary="Ассистент не смог надёжно определить operational intent. Лучше указать клиента, SKU, горизонт расчёта или тип нужной сводки.",
        sections=[
            _section(
                section_type="narrative",
                title="Что уточнить",
                items=[
                    "клиент или DIY-сеть",
                    "SKU или категорию",
                    "горизонт резерва или тип сводки",
                ],
            )
        ],
        source_refs=[],
        tool_calls=[],
        followups=_generic_followups("unsupported_or_ambiguous", bundle),
        warnings=bundle.warnings,
        context_used=bundle.context,
    )


def _compose_answer(bundle: AssistantContextBundle, executions: list[AssistantToolExecution]) -> AssistantAnswerDraft:
    if bundle.route.intent == "unsupported_or_ambiguous":
        return _compose_unsupported(bundle)

    tool_map = {execution.tool_name: execution for execution in executions}
    warnings = _collect_warnings(bundle, executions)
    source_refs = _dedupe_source_refs(executions)

    if bundle.route.intent == "reserve_calculation":
        calculation = tool_map["calculate_reserve"].payload
        if calculation is None:
            return AssistantAnswerDraft(
                intent="reserve_calculation",
                status="needs_clarification",
                confidence=0.42,
                title="Расчёт резерва не выполнен",
                summary="Для расчёта резерва не хватает определённого клиента или SKU-контекста.",
                sections=[
                    _section(
                        section_type="warning_block",
                        title="Что нужно для расчёта",
                        items=[warning.message for warning in warnings] or ["Уточните клиента и SKU."],
                    )
                ],
                source_refs=source_refs,
                tool_calls=executions,
                followups=_generic_followups("reserve_calculation", bundle),
                warnings=warnings,
                context_used=bundle.context,
            )
        totals = calculation.run.summary_payload
        sections = [
            _section(
                section_type="narrative",
                title="Вывод",
                body=(
                    f"По текущему расчёту ниже целевого резерва {int(totals.get('positions_at_risk', 0))} позиций, "
                    f"общий дефицит составляет {_qty(totals.get('total_shortage_qty'))} шт."
                ),
            ),
            _section(
                section_type="metric_summary",
                title="Ключевые метрики",
                metrics=[
                    _metric("positions", "Позиции", str(int(totals.get("positions", 0)))),
                    _metric(
                        "at_risk",
                        "Под риском",
                        str(int(totals.get("positions_at_risk", 0))),
                        "warning" if int(totals.get("positions_at_risk", 0)) else "positive",
                    ),
                    _metric(
                        "shortage",
                        "Дефицит",
                        f"{_qty(totals.get('total_shortage_qty'))} шт.",
                        "critical" if float(totals.get("total_shortage_qty", 0) or 0) > 0 else "positive",
                    ),
                    _metric(
                        "coverage",
                        "Среднее покрытие",
                        f"{_qty(totals.get('avg_coverage_months'))} мес.",
                    ),
                ],
            ),
            _section(
                section_type="reserve_table_preview",
                title="Ключевые позиции",
                rows=_reserve_rows_preview(calculation.rows),
            ),
        ]
        if warnings:
            sections.append(
                _section(
                    section_type="warning_block",
                    title="Ограничения",
                    items=[warning.message for warning in warnings],
                )
            )
        return AssistantAnswerDraft(
            intent="reserve_calculation",
            status="completed" if not warnings else "partial",
            confidence=0.91 if not warnings else 0.78,
            title="Расчёт резерва выполнен",
            summary=sections[0]["body"] or "",
            sections=sections,
            source_refs=source_refs,
            tool_calls=executions,
            followups=_generic_followups("reserve_calculation", bundle),
            warnings=warnings,
            context_used=bundle.context,
        )

    if bundle.route.intent == "reserve_explanation":
        payload = tool_map["get_reserve_explanation"].payload
        if payload is None:
            return AssistantAnswerDraft(
                intent="reserve_explanation",
                status="needs_clarification",
                confidence=0.4,
                title="Объяснение не собрано",
                summary="Не удалось однозначно определить reserve row для объяснения.",
                sections=[
                    _section(
                        section_type="warning_block",
                        title="Что мешает объяснению",
                        items=[warning.message for warning in warnings] or ["Уточните SKU или клиента."],
                    )
                ],
                source_refs=source_refs,
                tool_calls=executions,
                followups=_generic_followups("reserve_explanation", bundle),
                warnings=warnings,
                context_used=bundle.context,
            )
        row = payload["row"]
        warning_items = list(row.explanation_payload.get("warnings", [])) + [warning.message for warning in warnings]
        sections = [
            _section(
                section_type="narrative",
                title="Почему позиция в риске",
                body=(
                    f"{row.article} для {row.client_name} имеет статус {_localize_status_code(row.status)}: {_localize_status_reason(row.status_reason)}. "
                    f"Спрос {_qty(row.demand_per_month)} шт./мес., цель {_qty(row.target_reserve_qty)} шт., "
                    f"доступно {_qty(row.available_qty)} шт."
                ),
            ),
            _section(
                section_type="metric_summary",
                title="Основание расчёта",
                metrics=[
                    _metric("fallback", "Уровень fallback", row.fallback_level),
                    _metric("basis", "Основа спроса", row.demand_basis_type),
                    _metric("coverage", "Покрытие", f"{_qty(row.coverage_months)} мес."),
                    _metric("shortage", "Дефицит", f"{_qty(row.shortage_qty)} шт.", "critical"),
                ],
            ),
        ]
        if warning_items:
            sections.append(
                _section(
                    section_type="warning_block",
                    title="Что важно учесть",
                    items=[_localize_signal(str(item)) for item in warning_items],
                )
            )
        return AssistantAnswerDraft(
            intent="reserve_explanation",
            status="completed" if not warnings else "partial",
            confidence=0.9 if row.fallback_level == "client_sku" else 0.76,
            title=f"Объяснение по {row.article}",
            summary=sections[0]["body"] or "",
            sections=sections,
            source_refs=source_refs,
            tool_calls=executions,
            followups=_generic_followups("reserve_explanation", bundle),
            warnings=warnings,
            context_used=bundle.context,
        )

    if bundle.route.intent == "sku_summary":
        detail = tool_map["get_sku_summary"].payload
        if detail is None:
            return _compose_unsupported(bundle)
        reserve_summary = detail.reserve_summary
        sections = [
            _section(
                section_type="narrative",
                title="Текущая ситуация",
                body=(
                    f"По SKU {detail.sku.article} ({detail.sku.name}) "
                    f"дефицит {_qty(reserve_summary.shortage_qty_total if reserve_summary else 0)} шт., "
                    f"затронуто клиентов {reserve_summary.affected_clients_count if reserve_summary else 0}."
                ),
            ),
            _section(
                section_type="metric_summary",
                title="SKU в цифрах",
                metrics=[
                    _metric("free_stock", "Свободный остаток", f"{_qty(detail.stock.free_stock if detail.stock else 0)} шт."),
                    _metric("inbound", "Входящие поставки", str(len(detail.inbound))),
                    _metric("coverage", "Среднее покрытие", f"{_qty(reserve_summary.avg_coverage_months if reserve_summary else None)} мес."),
                    _metric("clients", "Клиентов под риском", str(reserve_summary.affected_clients_count if reserve_summary else 0)),
                ],
            ),
            _section(
                section_type="reserve_table_preview",
                title="Клиентский сплит",
                rows=[
                    {
                        "clientName": item.client_name,
                        "share": item.share,
                        "shortageQty": item.shortage_qty,
                        "coverageMonths": item.coverage_months,
                        "status": item.status,
                    }
                    for item in detail.client_split[:5]
                ],
            ),
        ]
        return AssistantAnswerDraft(
            intent="sku_summary",
            status="completed" if not warnings else "partial",
            confidence=0.88 if reserve_summary else 0.72,
            title=f"SKU {detail.sku.article}",
            summary=sections[0]["body"] or "",
            sections=sections,
            source_refs=source_refs,
            tool_calls=executions,
            followups=_generic_followups("sku_summary", bundle),
            warnings=warnings,
            context_used=bundle.context,
        )

    if bundle.route.intent in {"client_summary", "diy_coverage_check"}:
        payload = tool_map["get_client_summary"].payload
        if payload is None:
            dashboard = tool_map.get("get_dashboard_summary")
            summary = "Не удалось выбрать конкретного клиента. Показываю ближайшую общую картину по DIY-портфелю."
            sections = [
                _section(section_type="narrative", title="Что не определилось", body=summary),
            ]
            if dashboard and dashboard.payload is not None:
                overview = dashboard.payload
                sections.append(
                    _section(
                        section_type="metric_summary",
                        title="Общая сводка",
                        metrics=[
                            _metric("positions_at_risk", "Под риском", str(overview.summary.positions_at_risk), "warning"),
                            _metric("shortage", "Дефицит", f"{_qty(overview.summary.total_shortage_qty)} шт.", "critical"),
                        ],
                    )
                )
            return AssistantAnswerDraft(
                intent=bundle.route.intent,  # type: ignore[arg-type]
                status="needs_clarification",
                confidence=0.48,
                title="Нужен клиент или pinned context",
                summary=summary,
                sections=sections,
                source_refs=source_refs,
                tool_calls=executions,
                followups=_generic_followups(bundle.route.intent, bundle),
                warnings=warnings,
                context_used=bundle.context,
            )
        detail = payload["detail"]
        top_skus = payload["top_skus"]
        sections = [
            _section(
                section_type="narrative",
                title="Ситуация по клиенту",
                body=(
                    f"У {detail.name} сейчас {detail.critical_positions} critical и {detail.warning_positions} warning позиций. "
                    f"Суммарный дефицит {_qty(detail.shortage_qty)} шт., среднее покрытие {_qty(detail.coverage_months)} мес."
                ),
            ),
            _section(
                section_type="metric_summary",
                title="Ключевые показатели",
                metrics=[
                    _metric("critical", "Critical", str(detail.critical_positions), "critical"),
                    _metric("warning", "Warning", str(detail.warning_positions), "warning"),
                    _metric("shortage", "Дефицит", f"{_qty(detail.shortage_qty)} шт.", "critical"),
                    _metric("coverage", "Покрытие", f"{_qty(detail.coverage_months)} мес."),
                ],
            ),
            _section(
                section_type="reserve_table_preview",
                title="SKU с наибольшим риском",
                rows=[
                    {
                        "article": item.sku_code,
                        "productName": item.product_name,
                        "shortageQty": item.shortage_qty,
                        "coverageMonths": item.coverage_months,
                        "status": item.status,
                    }
                    for item in top_skus[:5]
                ],
            ),
        ]
        return AssistantAnswerDraft(
            intent=bundle.route.intent,  # type: ignore[arg-type]
            status="completed" if not warnings else "partial",
            confidence=0.86,
            title=f"DIY-клиент {detail.name}",
            summary=sections[0]["body"] or "",
            sections=sections,
            source_refs=source_refs,
            tool_calls=executions,
            followups=_generic_followups(bundle.route.intent, bundle),
            warnings=warnings,
            context_used=bundle.context,
        )

    if bundle.route.intent == "inbound_impact":
        rows = tool_map["get_inbound_impact"].payload or []
        total_impact = sum(getattr(item, "reserve_impact", 0) for item in rows)
        sections = [
            _section(
                section_type="narrative",
                title="Поставки с наибольшим эффектом",
                body=(
                    f"Сейчас наиболее релевантны {len(rows)} входящих поставок. "
                    f"Потенциальный relief по текущей выборке — {_qty(total_impact)} шт."
                ),
            ),
            _section(
                section_type="metric_summary",
                title="Inbound impact",
                metrics=[
                    _metric("deliveries", "Поставок", str(len(rows))),
                    _metric("impact", "Reserve impact", f"{_qty(total_impact)} шт.", "positive"),
                ],
            ),
            _section(
                section_type="reserve_table_preview",
                title="Ключевые поставки",
                rows=[
                    {
                        "article": item.article,
                        "productName": item.sku_name,
                        "eta": item.eta,
                        "status": item.status,
                        "reserveImpact": item.reserve_impact,
                    }
                    for item in rows[:6]
                ],
            ),
        ]
        return AssistantAnswerDraft(
            intent="inbound_impact",
            status="completed" if rows else "partial",
            confidence=0.82 if rows else 0.6,
            title="Влияние входящих поставок",
            summary=sections[0]["body"] or "",
            sections=sections,
            source_refs=source_refs,
            tool_calls=executions,
            followups=_generic_followups("inbound_impact", bundle),
            warnings=warnings,
            context_used=bundle.context,
        )

    if bundle.route.intent == "stock_risk_summary":
        rows = tool_map["get_stock_coverage"].payload or []
        total_shortage = sum(getattr(item, "shortage_qty_total", 0) for item in rows)
        sections = [
            _section(
                section_type="narrative",
                title="Риск склада",
                body=(
                    f"По текущей выборке рискованных позиций {len(rows)}, суммарный дефицит {_qty(total_shortage)} шт."
                ),
            ),
            _section(
                section_type="metric_summary",
                title="Ключевые метрики",
                metrics=[
                    _metric("positions", "Позиции", str(len(rows)), "warning" if rows else "positive"),
                    _metric("shortage", "Дефицит", f"{_qty(total_shortage)} шт.", "critical" if total_shortage else "positive"),
                ],
            ),
            _section(
                section_type="reserve_table_preview",
                title="Низкое покрытие",
                rows=[
                    {
                        "article": item.article,
                        "productName": item.product_name,
                        "coverageMonths": item.coverage_months,
                        "shortageQty": item.shortage_qty_total,
                        "status": item.worst_status,
                    }
                    for item in rows[:6]
                ],
            ),
        ]
        return AssistantAnswerDraft(
            intent="stock_risk_summary",
            status="completed" if rows else "partial",
            confidence=0.84,
            title="Сводка по stock risk",
            summary=sections[0]["body"] or "",
            sections=sections,
            source_refs=source_refs,
            tool_calls=executions,
            followups=_generic_followups("stock_risk_summary", bundle),
            warnings=warnings,
            context_used=bundle.context,
        )

    if bundle.route.intent == "upload_status_summary":
        details = tool_map["get_upload_status"].payload or []
        dashboard = tool_map.get("get_dashboard_summary")
        freshness_hours = dashboard.payload.freshness.freshness_hours if dashboard and dashboard.payload else None
        sections = [
            _section(
                section_type="narrative",
                title="Статус данных",
                body=(
                    f"Проверено {len(details)} загрузок. "
                    f"Последний известный freshness lag — {_qty(freshness_hours)} ч."
                ),
            ),
            _section(
                section_type="metric_summary",
                title="Ingestion и freshness",
                metrics=[
                    _metric("uploads", "Загрузок", str(len(details))),
                    _metric("freshness", "Freshness", f"{_qty(freshness_hours)} ч."),
                ],
            ),
            _section(
                section_type="reserve_table_preview",
                title="Последние загрузки",
                rows=[
                    {
                        "fileName": detail.file.file_name,
                        "status": detail.file.status,
                        "rows": detail.file.total_rows,
                        "issues": detail.file.issue_counts.total,
                    }
                    for detail in details[:5]
                ],
            ),
        ]
        return AssistantAnswerDraft(
            intent="upload_status_summary",
            status="completed" if details else "partial",
            confidence=0.8,
            title="Freshness и статус загрузок",
            summary=sections[0]["body"] or "",
            sections=sections,
            source_refs=source_refs,
            tool_calls=executions,
            followups=_generic_followups("upload_status_summary", bundle),
            warnings=warnings,
            context_used=bundle.context,
        )

    if bundle.route.intent == "quality_issue_summary":
        issues = tool_map["get_quality_issues"].payload or []
        sections = [
            _section(
                section_type="narrative",
                title="Quality issues",
                body=f"Сейчас найдено {len(issues)} релевантных quality issues, которые могут влиять на интерпретацию результата.",
            ),
            _section(
                section_type="reserve_table_preview",
                title="Открытые проблемы",
                rows=[
                    {
                        "type": issue.type,
                        "severity": issue.severity,
                        "entity": issue.entity,
                        "source": issue.source,
                    }
                    for issue in issues[:6]
                ],
            ),
        ]
        return AssistantAnswerDraft(
            intent="quality_issue_summary",
            status="completed" if issues else "partial",
            confidence=0.78,
            title="Сводка по качеству данных",
            summary=sections[0]["body"] or "",
            sections=sections,
            source_refs=source_refs,
            tool_calls=executions,
            followups=_generic_followups("quality_issue_summary", bundle),
            warnings=warnings,
            context_used=bundle.context,
        )

    return _compose_unsupported(bundle)


def _tool_plan(intent: str) -> list[str]:
    plans = {
        "reserve_calculation": ["calculate_reserve", "get_quality_issues", "get_upload_status"],
        "reserve_explanation": ["get_reserve_explanation", "get_sku_summary", "get_quality_issues"],
        "sku_summary": ["get_sku_summary", "get_quality_issues"],
        "client_summary": ["get_client_summary", "get_dashboard_summary"],
        "diy_coverage_check": ["get_client_summary", "get_dashboard_summary"],
        "inbound_impact": ["get_inbound_impact", "get_dashboard_summary"],
        "stock_risk_summary": ["get_stock_coverage", "get_dashboard_summary"],
        "upload_status_summary": ["get_upload_status", "get_dashboard_summary", "get_quality_issues"],
        "quality_issue_summary": ["get_quality_issues", "get_upload_status"],
    }
    return plans.get(intent, [])


def execute_assistant_query(
    db: Session,
    settings: Settings,
    *,
    payload: AssistantQueryRequest,
    created_by_id: str | None,
) -> AssistantResponse:
    trace_id = generate_id("trace")
    question = payload.prompt_text()
    route = route_question(db, question)
    bundle = build_context_bundle(db, route=route, pinned_context=payload.context)

    executions: list[AssistantToolExecution] = []
    for tool_name in _tool_plan(route.intent):
        if tool_name == "calculate_reserve":
            executions.append(tool_calculate_reserve(db, bundle, created_by_id=created_by_id))
        elif tool_name == "get_reserve_explanation":
            executions.append(tool_reserve_explanation(db, bundle))
        elif tool_name == "get_sku_summary":
            executions.append(tool_get_sku_summary(db, bundle))
        elif tool_name == "get_client_summary":
            executions.append(tool_get_client_summary(db, bundle))
        elif tool_name == "get_inbound_impact":
            executions.append(tool_get_inbound_impact(db, bundle))
        elif tool_name == "get_stock_coverage":
            executions.append(tool_get_stock_risk(db, bundle))
        elif tool_name == "get_upload_status":
            executions.append(tool_get_upload_status(db, bundle))
        elif tool_name == "get_quality_issues":
            executions.append(tool_get_quality_issues(db, bundle))
        elif tool_name == "get_dashboard_summary":
            executions.append(tool_get_dashboard_summary(db))

    draft = _compose_answer(bundle, executions)
    draft, provider_name, _provider_warnings = finalize_with_provider(settings, draft)

    return AssistantResponse(
        answerId=generate_id("ans"),
        sessionId=payload.session_id,
        intent=draft.intent,
        status=draft.status,  # type: ignore[arg-type]
        confidence=round(draft.confidence, 2),
        title=draft.title,
        summary=draft.summary,
        sections=[AssistantAnswerSection(**section) for section in draft.sections],
        sourceRefs=[AssistantSourceRef(**item) for item in draft.source_refs],
        toolCalls=[
            AssistantToolCall(
                toolName=execution.tool_name,
                status=execution.status,  # type: ignore[arg-type]
                arguments=execution.arguments,
                summary=execution.summary,
                latencyMs=execution.latency_ms,
            )
            for execution in draft.tool_calls
        ],
        followups=[AssistantFollowupSuggestion(**item) for item in draft.followups],
        warnings=[
            AssistantWarning(
                code=warning.code,
                message=warning.message,
                severity=warning.severity,  # type: ignore[arg-type]
            )
            for warning in draft.warnings
        ],
        generatedAt=utc_now().isoformat(),
        traceId=trace_id,
        provider=provider_name,
        contextUsed=_context_schema(draft.context_used),
    )
