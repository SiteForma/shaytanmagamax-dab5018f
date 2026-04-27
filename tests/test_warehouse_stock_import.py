from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.db.models import Sku, StockSnapshot


def test_warehouse_stock_upload_splits_free_and_diy_reserved_buckets(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
) -> None:
    workbook_path = tmp_path / "Стоки склад + обособка.xlsx"
    pd.DataFrame(
        [
            {
                "Артикул": "Склад",
                "Номенклатура": None,
                "Unnamed: 6": "Доступно",
            },
            {
                "Артикул": "STOCK-001",
                "Номенклатура": "Тестовый товар со склада",
                "Unnamed: 6": 15,
            },
            {
                "Артикул": "1.1.1. ОПТ ЩЕЛКОВО (МАГАМАКС)",
                "Номенклатура": None,
                "Unnamed: 6": 15,
            },
            {
                "Артикул": "склад Щелково",
                "Номенклатура": None,
                "Unnamed: 6": 10,
            },
            {
                "Артикул": "Обсобка СЕТИ",
                "Номенклатура": None,
                "Unnamed: 6": 5,
            },
        ]
    ).to_excel(workbook_path, index=False)

    with workbook_path.open("rb") as file:
        response = client.post(
            "/api/uploads/files",
            files={
                "file": (
                    workbook_path.name,
                    file,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )

    assert response.status_code == 200
    payload = response.json()
    file_payload = payload["file"]
    assert file_payload["source_type"] == "stock"
    assert file_payload["status"] == "applied"
    assert file_payload["applied_rows"] == 2
    assert file_payload["failed_rows"] == 0
    assert file_payload["issue_counts"]["total"] == 0
    assert file_payload["source_detection"]["requires_confirmation"] is False
    assert file_payload["readiness"]["can_apply"] is False
    assert file_payload["readiness"]["can_validate"] is False

    sku = db_session.scalar(select(Sku).where(Sku.article == "STOCK-001"))
    assert sku is not None
    snapshots = db_session.scalars(
        select(StockSnapshot)
        .where(StockSnapshot.sku_id == sku.id)
        .order_by(StockSnapshot.warehouse_code)
    ).all()
    assert [
        (item.warehouse_code, item.free_stock_qty, item.reserved_like_qty) for item in snapshots
    ] == [
        ("DIY_NETWORKS_OBOSOBKA", 0.0, 5.0),
        ("SHELKOVO_FREE", 10.0, 0.0),
    ]

    detail_response = client.get(f"/api/catalog/skus/{sku.id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["stock"]["free_stock"] == 10.0
    assert detail["stock"]["reserved_like"] == 5.0
    assert detail["stock"]["warehouse"] == "Сводный"
