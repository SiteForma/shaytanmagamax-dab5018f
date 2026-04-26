from __future__ import annotations

import pytest

from apps.api.app.core.errors import DomainError
from apps.api.app.modules.assistant.registry import get_default_tool_registry


def test_registry_registers_standard_phase6_tools() -> None:
    registry = get_default_tool_registry()

    assert registry.lookup("get_reserve").intent == "reserve_calculation"
    assert registry.lookup("explain_reserve").intent == "reserve_explanation"
    assert registry.lookup("get_stock_coverage").required_capabilities == (("stock", "read"),)
    assert registry.lookup("get_management_report").required_capabilities == (("reports", "read"),)
    assert registry.lookup("get_sales_summary").required_capabilities == (("sales", "read"),)
    assert registry.lookup("get_period_comparison").intent == "period_comparison"
    assert registry.lookup("get_data_overview").intent == "data_overview"


def test_registry_rejects_unknown_tool_and_unknown_params() -> None:
    registry = get_default_tool_registry()

    with pytest.raises(DomainError) as unknown_tool:
        registry.lookup("run_sql")
    assert unknown_tool.value.code == "assistant_unknown_tool"

    with pytest.raises(DomainError) as unknown_param:
        registry.validate("get_sales_summary", {"date_from": "2025-01-01", "date_to": "2025-12-01", "sql": "select 1"})
    assert unknown_param.value.code == "assistant_unknown_tool_param"


def test_registry_rejects_sql_like_values_even_in_allowed_params() -> None:
    registry = get_default_tool_registry()

    with pytest.raises(DomainError) as sql_like:
        registry.validate("get_management_report", {"question": "select * from sales_facts"})

    assert sql_like.value.code == "assistant_sql_like_param_rejected"
    assert sql_like.value.details == {"tool": "get_management_report", "param": "params.question"}


def test_registry_returns_required_missing_fields() -> None:
    registry = get_default_tool_registry()

    assert registry.validate("get_reserve", {}) == []

    missing = registry.validate("calculate_reserve", {})

    assert [field.name for field in missing] == ["client_id"]
    assert "клиент" in missing[0].label
