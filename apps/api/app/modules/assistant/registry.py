from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from apps.api.app.core.errors import DomainError
from apps.api.app.modules.assistant.analytics_catalog import (
    METRIC_CATALOG,
    capabilities_for_slice,
    normalize_dimension_name,
    normalize_metric_name,
)
from apps.api.app.modules.assistant.domain import AssistantContextBundle, AssistantToolExecution
from apps.api.app.modules.assistant.state import AssistantMissingField
from apps.api.app.modules.assistant.tools import (
    tool_calculate_reserve,
    tool_get_analytics_slice,
    tool_get_client_summary,
    tool_get_dashboard_summary,
    tool_get_data_overview,
    tool_get_inbound_impact,
    tool_get_management_report,
    tool_get_period_comparison,
    tool_get_quality_issues,
    tool_get_reserve,
    tool_get_sales_summary,
    tool_get_sku_summary,
    tool_get_stock_risk,
    tool_get_upload_status,
    tool_reserve_explanation,
)

AssistantToolHandler = Callable[
    [Session, AssistantContextBundle, dict[str, Any], str | None],
    AssistantToolExecution,
]
AssistantCapabilityResolver = Callable[[dict[str, Any]], tuple[tuple[str, str], ...]]

SQL_LIKE_PATTERN = re.compile(
    r"(?is)\b(select|insert|update|delete|drop|alter|truncate|create|grant|revoke)\b|--|/\*|\*/|;",
)
ALLOWED_FILTER_FIELDS = frozenset(
    {
        "client_id",
        "client_name",
        "sku_id",
        "article",
        "sku_ids",
        "sku_codes",
        "category_id",
        "category_name",
        "warehouse",
        "region",
        "status",
        "risk",
        "date_from",
        "date_to",
        "year",
        "month",
    }
)


@dataclass(frozen=True, slots=True)
class AssistantToolSpec:
    name: str
    intent: str
    description: str
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...]
    required_capabilities: tuple[tuple[str, str], ...]
    handler: AssistantToolHandler
    capability_resolver: AssistantCapabilityResolver | None = None

    @property
    def allowed_fields(self) -> set[str]:
        return {*self.required_fields, *self.optional_fields}

    def capabilities_for(self, params: dict[str, Any]) -> tuple[tuple[str, str], ...]:
        if self.capability_resolver is None:
            return self.required_capabilities
        return self.capability_resolver(params)

    def validate(self, params: dict[str, Any]) -> list[AssistantMissingField]:
        unknown = sorted(
            set(params)
            - self.allowed_fields
            - {"_followup_intent", "_pending_intent", "_force_tool"}
        )
        if unknown:
            raise DomainError(
                code="assistant_unknown_tool_param",
                message="Planner вернул параметры, которых нет в контракте assistant tool.",
                details={"tool": self.name, "unknown_params": unknown},
                status_code=400,
            )
        filters = params.get("filters")
        if isinstance(filters, dict):
            unknown_filters = sorted(set(filters) - ALLOWED_FILTER_FIELDS)
            if unknown_filters:
                raise DomainError(
                    code="assistant_unknown_tool_filter",
                    message="Planner вернул фильтры, которых нет в контракте assistant tool.",
                    details={"tool": self.name, "unknown_filters": unknown_filters},
                    status_code=400,
                )
        sql_like_path = _find_sql_like_param(params)
        if sql_like_path:
            raise DomainError(
                code="assistant_sql_like_param_rejected",
                message="Planner вернул SQL-like параметр, это запрещено для assistant tools.",
                details={"tool": self.name, "param": sql_like_path},
                status_code=400,
            )
        missing: list[AssistantMissingField] = []
        for field_name in self.required_fields:
            value = params.get(field_name)
            if value is None or value == "" or value == []:
                missing.append(_missing_field(field_name, self.intent, params))
        if self.name == "get_analytics_slice":
            raw_metrics = params.get("metrics") or params.get("metric") or []
            if isinstance(raw_metrics, str):
                metrics = [normalize_metric_name(raw_metrics)]
            elif isinstance(raw_metrics, list):
                metrics = [normalize_metric_name(str(item)) for item in raw_metrics]
            else:
                metrics = []
            sources = {
                METRIC_CATALOG[metric].source for metric in metrics if metric in METRIC_CATALOG
            }
            needs_period = bool(sources.intersection({"sales", "inbound", "management_report"}))
            has_period = bool(params.get("period")) or bool(
                params.get("date_from") and params.get("date_to")
            )
            if needs_period and not has_period and all(item.name != "period" for item in missing):
                missing.append(_missing_field("period", self.intent, params))
        return missing


def _find_sql_like_param(value: Any, path: str = "params") -> str | None:
    if isinstance(value, str):
        return path if SQL_LIKE_PATTERN.search(value) else None
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            if "sql" in key_text.lower():
                return f"{path}.{key_text}"
            found = _find_sql_like_param(item, f"{path}.{key_text}")
            if found:
                return found
    if isinstance(value, list):
        for index, item in enumerate(value):
            found = _find_sql_like_param(item, f"{path}[{index}]")
            if found:
                return found
    return None


class AssistantToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, AssistantToolSpec] = {}

    def register(self, spec: AssistantToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Assistant tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def lookup(self, tool_name: str) -> AssistantToolSpec:
        spec = self._tools.get(tool_name)
        if spec is None:
            raise DomainError(
                code="assistant_unknown_tool",
                message="Planner запросил неизвестный assistant tool.",
                details={"tool": tool_name},
                status_code=400,
            )
        return spec

    def validate(self, tool_name: str, params: dict[str, Any]) -> list[AssistantMissingField]:
        return self.lookup(tool_name).validate(params)

    @property
    def tool_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    @property
    def specs(self) -> tuple[AssistantToolSpec, ...]:
        return tuple(self._tools[name] for name in sorted(self._tools))

    def tools_for_intent(self, intent: str) -> tuple[str, ...]:
        return tuple(spec.name for spec in self.specs if spec.intent == intent)

    def default_plan_for_intent(self, intent: str) -> list[str]:
        plan = DEFAULT_INTENT_TOOL_PLAN.get(intent)
        if plan is None:
            return []
        return list(plan)


DEFAULT_INTENT_TOOL_PLAN: dict[str, tuple[str, ...]] = {
    "reserve_calculation": ("get_reserve", "get_quality_issues", "get_upload_status"),
    "reserve_explanation": ("get_reserve_explanation", "get_sku_summary", "get_quality_issues"),
    "sku_summary": ("get_sku_summary", "get_quality_issues"),
    "client_summary": ("get_client_summary", "get_dashboard_summary"),
    "diy_coverage_check": ("get_client_summary", "get_dashboard_summary"),
    "inbound_impact": ("get_inbound_impact", "get_dashboard_summary"),
    "stock_risk_summary": ("get_stock_coverage", "get_dashboard_summary"),
    "upload_status_summary": ("get_upload_status", "get_dashboard_summary", "get_quality_issues"),
    "quality_issue_summary": ("get_quality_issues", "get_upload_status"),
    "management_report_summary": ("get_management_report",),
    "sales_summary": ("get_sales_summary",),
    "period_comparison": ("get_period_comparison",),
    "analytics_slice": ("get_analytics_slice",),
    "data_overview": ("get_data_overview",),
}


def _missing_field(field_name: str, intent: str, params: dict[str, Any]) -> AssistantMissingField:
    labels = {
        "client_id": "клиент",
        "sku_id": "SKU",
        "date_from": "начало периода",
        "date_to": "конец периода",
        "metric": "метрика",
        "current_period": "текущий период",
        "previous_period": "период сравнения",
        "period": "период",
        "question": "вопрос",
    }
    questions = {
        "client_id": "По какому клиенту смотреть?",
        "sku_id": f"По какому SKU смотреть для {params.get('client_name') or 'выбранного клиента'}?",
        "date_from": "За какой период посмотреть продажи?",
        "date_to": "До какой даты смотреть продажи?",
        "metric": "Что именно сравнить: продажи, остатки или резерв?",
        "current_period": "Какой период взять как текущий?",
        "previous_period": "С каким периодом сравнить?",
        "period": "За какой период собрать аналитический срез?",
        "question": "Что именно нужно найти в управленческом отчёте?",
    }
    if intent == "reserve_calculation" and field_name == "client_id":
        questions[field_name] = "По какому клиенту посчитать резерв?"
    return AssistantMissingField(
        name=field_name,
        label=labels.get(field_name, field_name),
        question=questions.get(field_name, f"Уточните {labels.get(field_name, field_name)}."),
    )


def _apply_params(bundle: AssistantContextBundle, params: dict[str, Any]) -> AssistantContextBundle:
    if params.get("client_id"):
        bundle.context.selected_client_id = str(params["client_id"])
    if params.get("sku_id"):
        bundle.context.selected_sku_id = str(params["sku_id"])
    if params.get("sku_ids"):
        bundle.route.extracted_sku_ids = [
            str(item) for item in params["sku_ids"] if str(item).strip()
        ]
    if params.get("category_id"):
        bundle.context.selected_category_id = str(params["category_id"])
    if params.get("reserve_run_id"):
        bundle.context.selected_reserve_run_id = str(params["reserve_run_id"])
    if params.get("reserve_months") is not None:
        bundle.route.reserve_months = int(params["reserve_months"])
    if params.get("safety_factor") is not None:
        bundle.route.safety_factor = float(params["safety_factor"])
    return bundle


def _reserve_handler(
    db: Session,
    bundle: AssistantContextBundle,
    params: dict[str, Any],
    created_by_id: str | None,
) -> AssistantToolExecution:
    return tool_calculate_reserve(db, _apply_params(bundle, params), created_by_id=created_by_id)


def _reserve_read_handler(
    db: Session,
    bundle: AssistantContextBundle,
    params: dict[str, Any],
    _created_by_id: str | None,
) -> AssistantToolExecution:
    return tool_get_reserve(db, _apply_params(bundle, params), params)


def _reserve_explanation_handler(
    db: Session,
    bundle: AssistantContextBundle,
    params: dict[str, Any],
    _created_by_id: str | None,
) -> AssistantToolExecution:
    return tool_reserve_explanation(db, _apply_params(bundle, params))


def _stock_handler(
    db: Session,
    bundle: AssistantContextBundle,
    params: dict[str, Any],
    _created_by_id: str | None,
) -> AssistantToolExecution:
    return tool_get_stock_risk(db, _apply_params(bundle, params))


def _sku_summary_handler(
    db: Session,
    bundle: AssistantContextBundle,
    params: dict[str, Any],
    _created_by_id: str | None,
) -> AssistantToolExecution:
    return tool_get_sku_summary(db, _apply_params(bundle, params))


def _client_summary_handler(
    db: Session,
    bundle: AssistantContextBundle,
    params: dict[str, Any],
    _created_by_id: str | None,
) -> AssistantToolExecution:
    return tool_get_client_summary(db, _apply_params(bundle, params))


def _inbound_handler(
    db: Session,
    bundle: AssistantContextBundle,
    params: dict[str, Any],
    _created_by_id: str | None,
) -> AssistantToolExecution:
    return tool_get_inbound_impact(db, _apply_params(bundle, params))


def _upload_handler(
    db: Session,
    bundle: AssistantContextBundle,
    params: dict[str, Any],
    _created_by_id: str | None,
) -> AssistantToolExecution:
    return tool_get_upload_status(db, _apply_params(bundle, params))


def _quality_handler(
    db: Session,
    bundle: AssistantContextBundle,
    params: dict[str, Any],
    _created_by_id: str | None,
) -> AssistantToolExecution:
    return tool_get_quality_issues(db, _apply_params(bundle, params))


def _dashboard_handler(
    db: Session,
    _bundle: AssistantContextBundle,
    _params: dict[str, Any],
    _created_by_id: str | None,
) -> AssistantToolExecution:
    return tool_get_dashboard_summary(db)


def _management_report_handler(
    db: Session,
    _bundle: AssistantContextBundle,
    params: dict[str, Any],
    _created_by_id: str | None,
) -> AssistantToolExecution:
    return tool_get_management_report(db, str(params.get("question") or ""))


def _sales_summary_handler(
    db: Session,
    bundle: AssistantContextBundle,
    params: dict[str, Any],
    _created_by_id: str | None,
) -> AssistantToolExecution:
    return tool_get_sales_summary(db, _apply_params(bundle, params), params)


def _period_comparison_handler(
    db: Session,
    bundle: AssistantContextBundle,
    params: dict[str, Any],
    _created_by_id: str | None,
) -> AssistantToolExecution:
    return tool_get_period_comparison(db, _apply_params(bundle, params), params)


def _analytics_slice_handler(
    db: Session,
    bundle: AssistantContextBundle,
    params: dict[str, Any],
    _created_by_id: str | None,
) -> AssistantToolExecution:
    return tool_get_analytics_slice(db, _apply_params(bundle, params), params)


def _data_overview_handler(
    db: Session,
    _bundle: AssistantContextBundle,
    _params: dict[str, Any],
    _created_by_id: str | None,
) -> AssistantToolExecution:
    return tool_get_data_overview(db)


def _analytics_required_capabilities(params: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    raw_metrics = params.get("metrics") or params.get("metric") or []
    if isinstance(raw_metrics, str):
        metrics = [normalize_metric_name(raw_metrics)]
    elif isinstance(raw_metrics, list):
        metrics = [normalize_metric_name(str(item)) for item in raw_metrics]
    else:
        metrics = []
    if not metrics:
        metrics = ["revenue"]
    raw_dimensions = params.get("dimensions") or params.get("dimension") or []
    if isinstance(raw_dimensions, str):
        dimensions = [normalize_dimension_name(raw_dimensions)]
    elif isinstance(raw_dimensions, list):
        dimensions = [normalize_dimension_name(str(item)) for item in raw_dimensions]
    else:
        dimensions = []
    return capabilities_for_slice(metrics, dimensions)


def get_default_tool_registry() -> AssistantToolRegistry:
    registry = AssistantToolRegistry()
    common_reserve_fields = (
        "client_id",
        "client_name",
        "sku_id",
        "sku_ids",
        "sku_codes",
        "category_id",
        "reserve_months",
        "safety_factor",
        "reserve_run_id",
        "status",
        "risk",
        "filters",
    )
    registry.register(
        AssistantToolSpec(
            name="calculate_reserve",
            intent="reserve_calculation",
            description="Расчёт резерва через reserve engine.",
            required_fields=("client_id",),
            optional_fields=common_reserve_fields,
            required_capabilities=(("reserve", "read"), ("reserve", "run")),
            handler=_reserve_handler,
        )
    )
    registry.register(
        AssistantToolSpec(
            name="get_reserve",
            intent="reserve_calculation",
            description="Read-only чтение последнего сохранённого reserve run без скрытого пересчёта.",
            required_fields=(),
            optional_fields=(*common_reserve_fields, "status", "risk", "filters"),
            required_capabilities=(("reserve", "read"),),
            handler=_reserve_read_handler,
        )
    )
    registry.register(
        AssistantToolSpec(
            name="get_reserve_explanation",
            intent="reserve_explanation",
            description="Объяснение сохранённой или вычисленной reserve row.",
            required_fields=(),
            optional_fields=common_reserve_fields,
            required_capabilities=(("reserve", "read"),),
            handler=_reserve_explanation_handler,
        )
    )
    registry.register(
        AssistantToolSpec(
            name="explain_reserve",
            intent="reserve_explanation",
            description="Alias for reserve explanation.",
            required_fields=(),
            optional_fields=common_reserve_fields,
            required_capabilities=(("reserve", "read"),),
            handler=_reserve_explanation_handler,
        )
    )
    registry.register(
        AssistantToolSpec(
            name="get_stock_coverage",
            intent="stock_risk_summary",
            description="Список SKU с низким покрытием склада.",
            required_fields=(),
            optional_fields=(
                "category_id",
                "sku_id",
                "client_id",
                "status",
                "risk",
                "filters",
                "reserve_months",
            ),
            required_capabilities=(("stock", "read"),),
            handler=_stock_handler,
        )
    )
    registry.register(
        AssistantToolSpec(
            name="get_sku_summary",
            intent="sku_summary",
            description="Сводка по SKU из catalog, stock, sales и reserve read models.",
            required_fields=(),
            optional_fields=("sku_id", "sku_ids", "client_id"),
            required_capabilities=(("catalog", "read"),),
            handler=_sku_summary_handler,
        )
    )
    registry.register(
        AssistantToolSpec(
            name="get_client_summary",
            intent="client_summary",
            description="Сводка по DIY-клиенту.",
            required_fields=("client_id",),
            optional_fields=("client_id", "client_name"),
            required_capabilities=(("clients", "read"), ("reserve", "read")),
            handler=_client_summary_handler,
        )
    )
    registry.register(
        AssistantToolSpec(
            name="get_inbound_impact",
            intent="inbound_impact",
            description="Входящие поставки и их влияние на резерв.",
            required_fields=(),
            optional_fields=("client_id", "sku_id", "sku_ids"),
            required_capabilities=(("inbound", "read"),),
            handler=_inbound_handler,
        )
    )
    registry.register(
        AssistantToolSpec(
            name="get_upload_status",
            intent="upload_status_summary",
            description="Статус загрузок и ingestion freshness.",
            required_fields=(),
            optional_fields=("upload_ids", "client_id", "sku_id"),
            required_capabilities=(("uploads", "read"),),
            handler=_upload_handler,
        )
    )
    registry.register(
        AssistantToolSpec(
            name="get_quality_issues",
            intent="quality_issue_summary",
            description="Проблемы качества данных.",
            required_fields=(),
            optional_fields=("client_id", "sku_id", "upload_ids"),
            required_capabilities=(("quality", "read"),),
            handler=_quality_handler,
        )
    )
    registry.register(
        AssistantToolSpec(
            name="get_dashboard_summary",
            intent="dashboard_summary",
            description="Сводка dashboard и freshness.",
            required_fields=(),
            optional_fields=(),
            required_capabilities=(("dashboard", "read"),),
            handler=_dashboard_handler,
        )
    )
    registry.register(
        AssistantToolSpec(
            name="get_management_report",
            intent="management_report_summary",
            description="Контекст управленческого отчёта.",
            required_fields=("question",),
            optional_fields=("question", "year", "rank", "metric"),
            required_capabilities=(("reports", "read"),),
            handler=_management_report_handler,
        )
    )
    registry.register(
        AssistantToolSpec(
            name="get_sales_summary",
            intent="sales_summary",
            description="Сводка продаж по периоду, клиенту и SKU.",
            required_fields=("date_from", "date_to"),
            optional_fields=(
                "date_from",
                "date_to",
                "client_id",
                "client_name",
                "sku_id",
                "sku_ids",
                "metric",
            ),
            required_capabilities=(("sales", "read"),),
            handler=_sales_summary_handler,
        )
    )
    registry.register(
        AssistantToolSpec(
            name="get_period_comparison",
            intent="period_comparison",
            description="Сравнение метрики между двумя периодами.",
            required_fields=("metric", "current_period", "previous_period"),
            optional_fields=(
                "metric",
                "current_period",
                "previous_period",
                "client_id",
                "client_name",
                "sku_id",
                "sku_ids",
            ),
            required_capabilities=(("sales", "read"),),
            handler=_period_comparison_handler,
        )
    )
    registry.register(
        AssistantToolSpec(
            name="get_analytics_slice",
            intent="analytics_slice",
            description="Read-only универсальный аналитический срез через allowlisted metrics/dimensions.",
            required_fields=("metrics",),
            optional_fields=(
                "metric",
                "metrics",
                "dimension",
                "dimensions",
                "filters",
                "period",
                "date_from",
                "date_to",
                "sort",
                "sort_by",
                "sort_direction",
                "limit",
                "client_id",
                "client_name",
                "sku_id",
                "sku_ids",
                "category_id",
            ),
            required_capabilities=(("sales", "read"),),
            handler=_analytics_slice_handler,
            capability_resolver=_analytics_required_capabilities,
        )
    )
    registry.register(
        AssistantToolSpec(
            name="get_data_overview",
            intent="data_overview",
            description="Read-only инвентаризация полезных аналитических данных в БД без скрытых расчётов.",
            required_fields=(),
            optional_fields=(),
            required_capabilities=(
                ("dashboard", "read"),
                ("catalog", "read"),
                ("clients", "read"),
                ("uploads", "read"),
                ("sales", "read"),
                ("stock", "read"),
                ("reserve", "read"),
                ("inbound", "read"),
                ("quality", "read"),
                ("reports", "read"),
            ),
            handler=_data_overview_handler,
        )
    )
    return registry
