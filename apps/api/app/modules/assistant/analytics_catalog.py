from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

AnalyticsSource = Literal["sales", "stock", "reserve", "inbound", "management_report", "catalog"]


@dataclass(frozen=True, slots=True)
class MetricSpec:
    key: str
    label: str
    source: AnalyticsSource
    expression_type: str
    unit: str
    supported_dimensions: tuple[str, ...]
    required_capabilities: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class DimensionSpec:
    key: str
    label: str
    source: AnalyticsSource | Literal["shared"]
    resolver: str
    required_capabilities: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class AnalyticsSliceRequest:
    metrics: list[str]
    dimensions: list[str] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
    date_from: str | None = None
    date_to: str | None = None
    sort_by: str | None = None
    sort_direction: Literal["asc", "desc"] = "desc"
    limit: int = 20


@dataclass(frozen=True, slots=True)
class AnalyticsSliceResult:
    metrics: list[str]
    dimensions: list[str]
    rows: list[dict[str, Any]]
    totals: dict[str, float]
    warnings: list[dict[str, str]]
    source_refs: list[dict[str, Any]]
    query_description: str


METRIC_ALIASES: dict[str, str] = {
    "quantity": "sales_qty",
    "qty": "sales_qty",
    "количество": "sales_qty",
    "штуки": "sales_qty",
    "шт": "sales_qty",
    "продажи_шт": "sales_qty",
    "продажи": "sales_qty",
    "выручка": "revenue",
    "оборот": "revenue",
    "себестоимость": "unit_cost",
    "себесстоимость": "unit_cost",
    "себестоимость за единицу": "unit_cost",
    "цена себестоимости": "unit_cost",
    "cost_of_goods_sold": "unit_cost",
    "unit_cost": "unit_cost",
    "затраты": "cost_amount",
    "себестоимость продаж": "cost_amount",
    "прибыль": "gross_profit",
    "валовая прибыль": "gross_profit",
    "заработали": "gross_profit",
    "profit": "gross_profit",
    "gross_profit": "gross_profit",
    "маржинальность": "gross_margin_pct",
    "валовая маржа": "gross_margin_pct",
    "margin_pct": "gross_margin_pct",
    "gross_margin_pct": "gross_margin_pct",
    "остаток": "stock_qty",
    "остатки": "stock_qty",
    "склад": "stock_qty",
    "свободный_остаток": "free_stock",
    "резерв": "reserve_qty",
    "дефицит": "shortage_qty",
    "покрытие": "coverage_months",
    "поставки": "inbound_qty",
    "входящие": "inbound_qty",
    "рентабельность": "profitability",
    "прибыльность": "profitability",
    "маржа": "margin",
}

DIMENSION_ALIASES: dict[str, str] = {
    "клиент": "client",
    "клиенты": "client",
    "сеть": "client",
    "товар": "sku",
    "товары": "sku",
    "sku": "sku",
    "артикул": "article",
    "артикулы": "article",
    "бренд": "brand",
    "бренды": "brand",
    "категория": "category",
    "категории": "category",
    "тг": "product_group",
    "товарная группа": "product_group",
    "товарные группы": "product_group",
    "склад": "warehouse",
    "склады": "warehouse",
    "месяц": "month",
    "месяцы": "month",
    "квартал": "quarter",
    "кварталы": "quarter",
    "год": "year",
    "годы": "year",
    "регион": "region",
    "регионы": "region",
}

SALES_DIMENSIONS = (
    "client",
    "sku",
    "article",
    "brand",
    "category",
    "month",
    "quarter",
    "year",
    "region",
)
CATALOG_DIMENSIONS = ("sku", "article", "brand", "category")
STOCK_DIMENSIONS = ("sku", "article", "brand", "category", "warehouse", "month", "quarter", "year")
RESERVE_DIMENSIONS = ("client", "sku", "article", "brand", "category")
INBOUND_DIMENSIONS = ("sku", "article", "brand", "category", "month", "quarter", "year")
REPORT_DIMENSIONS = ("product_group", "category", "year")

METRIC_CATALOG: dict[str, MetricSpec] = {
    "sales_qty": MetricSpec(
        key="sales_qty",
        label="Продажи, шт.",
        source="sales",
        expression_type="sum_sales_quantity",
        unit="qty",
        supported_dimensions=SALES_DIMENSIONS,
        required_capabilities=(("sales", "read"),),
    ),
    "revenue": MetricSpec(
        key="revenue",
        label="Выручка",
        source="sales",
        expression_type="sum_sales_revenue",
        unit="rub",
        supported_dimensions=SALES_DIMENSIONS,
        required_capabilities=(("sales", "read"),),
    ),
    "cost_amount": MetricSpec(
        key="cost_amount",
        label="Себестоимость продаж",
        source="sales",
        expression_type="sum_sales_cost_amount",
        unit="rub",
        supported_dimensions=SALES_DIMENSIONS,
        required_capabilities=(("sales", "read"), ("catalog", "read")),
    ),
    "unit_cost": MetricSpec(
        key="unit_cost",
        label="Себестоимость за ед.",
        source="catalog",
        expression_type="latest_sku_unit_cost",
        unit="rub",
        supported_dimensions=CATALOG_DIMENSIONS,
        required_capabilities=(("catalog", "read"),),
    ),
    "gross_profit": MetricSpec(
        key="gross_profit",
        label="Валовая прибыль",
        source="sales",
        expression_type="sum_gross_profit",
        unit="rub",
        supported_dimensions=SALES_DIMENSIONS,
        required_capabilities=(("sales", "read"), ("catalog", "read")),
    ),
    "gross_margin_pct": MetricSpec(
        key="gross_margin_pct",
        label="Валовая маржа",
        source="sales",
        expression_type="gross_profit_over_revenue_pct",
        unit="pct",
        supported_dimensions=SALES_DIMENSIONS,
        required_capabilities=(("sales", "read"), ("catalog", "read")),
    ),
    "stock_qty": MetricSpec(
        key="stock_qty",
        label="Остаток",
        source="stock",
        expression_type="sum_stock_total",
        unit="qty",
        supported_dimensions=STOCK_DIMENSIONS,
        required_capabilities=(("stock", "read"),),
    ),
    "free_stock": MetricSpec(
        key="free_stock",
        label="Свободный остаток",
        source="stock",
        expression_type="sum_free_stock",
        unit="qty",
        supported_dimensions=STOCK_DIMENSIONS,
        required_capabilities=(("stock", "read"),),
    ),
    "reserve_qty": MetricSpec(
        key="reserve_qty",
        label="Целевой резерв",
        source="reserve",
        expression_type="sum_target_reserve",
        unit="qty",
        supported_dimensions=RESERVE_DIMENSIONS,
        required_capabilities=(("reserve", "read"),),
    ),
    "shortage_qty": MetricSpec(
        key="shortage_qty",
        label="Дефицит",
        source="reserve",
        expression_type="sum_shortage",
        unit="qty",
        supported_dimensions=RESERVE_DIMENSIONS,
        required_capabilities=(("reserve", "read"),),
    ),
    "coverage_months": MetricSpec(
        key="coverage_months",
        label="Покрытие, мес.",
        source="reserve",
        expression_type="max_coverage_months",
        unit="months",
        supported_dimensions=RESERVE_DIMENSIONS,
        required_capabilities=(("reserve", "read"),),
    ),
    "inbound_qty": MetricSpec(
        key="inbound_qty",
        label="Входящие поставки",
        source="inbound",
        expression_type="sum_inbound_quantity",
        unit="qty",
        supported_dimensions=INBOUND_DIMENSIONS,
        required_capabilities=(("inbound", "read"),),
    ),
    "margin": MetricSpec(
        key="margin",
        label="Маржа",
        source="management_report",
        expression_type="avg_profitability_pct",
        unit="pct",
        supported_dimensions=REPORT_DIMENSIONS,
        required_capabilities=(("reports", "read"),),
    ),
    "profitability": MetricSpec(
        key="profitability",
        label="Рентабельность",
        source="management_report",
        expression_type="avg_profitability_pct",
        unit="pct",
        supported_dimensions=REPORT_DIMENSIONS,
        required_capabilities=(("reports", "read"),),
    ),
}

DIMENSION_CATALOG: dict[str, DimensionSpec] = {
    "client": DimensionSpec("client", "Клиент", "shared", "client_name", (("clients", "read"),)),
    "sku": DimensionSpec("sku", "SKU", "shared", "sku_name", (("catalog", "read"),)),
    "article": DimensionSpec("article", "Артикул", "shared", "sku_article", (("catalog", "read"),)),
    "brand": DimensionSpec("brand", "Бренд", "shared", "sku_brand", (("catalog", "read"),)),
    "category": DimensionSpec(
        "category", "Категория", "shared", "category_name", (("catalog", "read"),)
    ),
    "product_group": DimensionSpec(
        "product_group",
        "Товарная группа",
        "management_report",
        "dimension_name",
        (("reports", "read"),),
    ),
    "warehouse": DimensionSpec(
        "warehouse", "Склад", "stock", "warehouse_code", (("stock", "read"),)
    ),
    "month": DimensionSpec("month", "Месяц", "shared", "month"),
    "quarter": DimensionSpec("quarter", "Квартал", "shared", "quarter"),
    "year": DimensionSpec("year", "Год", "shared", "year"),
    "region": DimensionSpec("region", "Регион", "sales", "client_region", (("clients", "read"),)),
}


def normalize_metric_name(value: str) -> str:
    normalized = value.strip().lower().replace("ё", "е")
    return METRIC_ALIASES.get(normalized, normalized)


def normalize_dimension_name(value: str) -> str:
    normalized = value.strip().lower().replace("ё", "е")
    return DIMENSION_ALIASES.get(normalized, normalized)


def metric_source(metrics: list[str]) -> AnalyticsSource | None:
    sources = {METRIC_CATALOG[item].source for item in metrics if item in METRIC_CATALOG}
    return next(iter(sources)) if len(sources) == 1 else None


def capabilities_for_slice(
    metrics: list[str], dimensions: list[str]
) -> tuple[tuple[str, str], ...]:
    capabilities: list[tuple[str, str]] = []
    for metric in metrics:
        spec = METRIC_CATALOG.get(metric)
        if spec:
            capabilities.extend(spec.required_capabilities)
    for dimension in dimensions:
        spec = DIMENSION_CATALOG.get(dimension)
        if spec:
            capabilities.extend(spec.required_capabilities)
    deduped: list[tuple[str, str]] = []
    for capability in capabilities:
        if capability not in deduped:
            deduped.append(capability)
    return tuple(deduped or (("sales", "read"),))


def unsupported_metrics(metrics: list[str]) -> list[str]:
    return [item for item in metrics if item not in METRIC_CATALOG]


def unsupported_dimensions(dimensions: list[str]) -> list[str]:
    return [item for item in dimensions if item not in DIMENSION_CATALOG]


def unsupported_dimensions_for_metrics(metrics: list[str], dimensions: list[str]) -> list[str]:
    source = metric_source(metrics)
    if source is None:
        return []
    supported = set.intersection(
        *(
            set(METRIC_CATALOG[metric].supported_dimensions)
            for metric in metrics
            if metric in METRIC_CATALOG
        )
    )
    return [dimension for dimension in dimensions if dimension not in supported]
