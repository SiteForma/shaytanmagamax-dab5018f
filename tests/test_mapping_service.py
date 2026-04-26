from __future__ import annotations

import pandas as pd

from apps.api.app.modules.mapping.service import build_mapping_fields, detect_source_type


def test_mapping_detects_sales_headers_in_russian() -> None:
    frame = pd.DataFrame(
        [
            {"Артикул": "K-2650-CR", "Сеть": "Leman Pro", "Кол-во": 420, "Дата": "2026-04-01"},
        ]
    )

    source_type = detect_source_type(list(frame.columns), explicit_source_type=None)
    mappings = build_mapping_fields(frame, source_type)
    canonical_map = {item.source: item.canonical for item in mappings}

    assert source_type == "sales"
    assert canonical_map["Артикул"] == "sku_code"
    assert canonical_map["Сеть"] == "client_name"
    assert canonical_map["Кол-во"] == "quantity"
    assert canonical_map["Дата"] == "period_date"


def test_mapping_detects_stock_department_header_as_warehouse() -> None:
    frame = pd.DataFrame(
        [
            {
                "Артикул": "K-2650-CR",
                "Остаток свободный": 12,
                "Дата": "2026-04-01",
                "Подразделение": "0311 ОТДЕЛ ПРОДАЖ КОМПЛЕКТУЮЩИЕ МОСКВА",
            },
        ]
    )

    mappings = build_mapping_fields(frame, "stock")
    canonical_map = {item.source: item.canonical for item in mappings}

    assert canonical_map["Подразделение"] == "warehouse_name"
