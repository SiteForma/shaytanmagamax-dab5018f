from __future__ import annotations

from apps.api.app.modules.assistant.analytics_catalog import (
    DIMENSION_CATALOG,
    METRIC_CATALOG,
    capabilities_for_slice,
    normalize_dimension_name,
    normalize_metric_name,
    unsupported_dimensions,
    unsupported_dimensions_for_metrics,
    unsupported_metrics,
)


def test_metric_catalog_contains_supported_business_metrics() -> None:
    assert METRIC_CATALOG["sales_qty"].source == "sales"
    assert METRIC_CATALOG["revenue"].unit == "rub"
    assert METRIC_CATALOG["free_stock"].source == "stock"
    assert METRIC_CATALOG["shortage_qty"].source == "reserve"
    assert METRIC_CATALOG["inbound_qty"].required_capabilities == (("inbound", "read"),)
    assert METRIC_CATALOG["profitability"].source == "management_report"


def test_dimension_catalog_contains_supported_dimensions() -> None:
    assert DIMENSION_CATALOG["client"].label == "Клиент"
    assert DIMENSION_CATALOG["sku"].required_capabilities == (("catalog", "read"),)
    assert DIMENSION_CATALOG["product_group"].source == "management_report"
    assert DIMENSION_CATALOG["month"].resolver == "month"


def test_catalog_normalization_and_rejections() -> None:
    assert normalize_metric_name("выручка") == "revenue"
    assert normalize_metric_name("шт") == "sales_qty"
    assert normalize_dimension_name("товарная группа") == "product_group"
    assert unsupported_metrics(["revenue", "unknown_metric"]) == ["unknown_metric"]
    assert unsupported_dimensions(["client", "unknown_dimension"]) == ["unknown_dimension"]
    assert unsupported_dimensions_for_metrics(["stock_qty"], ["client"]) == ["client"]


def test_capabilities_are_derived_from_metrics_and_dimensions() -> None:
    capabilities = capabilities_for_slice(["revenue"], ["client"])

    assert ("sales", "read") in capabilities
    assert ("clients", "read") in capabilities
