from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.app.db.models import Sku, SkuCost, SkuCostHistory, UploadFile


def test_sku_cost_upload_import_persists_article_name_and_cost(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
) -> None:
    sku = db_session.scalar(select(Sku).where(Sku.article == "K-2650-CR"))
    assert sku is not None
    workbook_path = tmp_path / "Себесстоимость.xlsx"
    pd.DataFrame(
        [
            {
                "Артикул": "K-2650-CR",
                "Наименование": "Ручка-кнопка из файла",
                "Себестоимость, руб": 125.5,
            },
            {
                "Артикул": "NEW-001",
                "Наименование": "Kerron Новый артикул без SKU",
                "Себестоимость, руб": "77,10",
            },
        ]
    ).to_excel(workbook_path, index=False)

    with workbook_path.open("rb") as file:
        upload_response = client.post(
            "/api/uploads/files",
            data={"source_type": "raw_report"},
            files={
                "file": (
                    workbook_path.name,
                    file,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert upload_response.status_code == 200
    file_id = upload_response.json()["file"]["id"]

    import_response = client.post(f"/api/catalog/sku-costs/import-upload/{file_id}")
    assert import_response.status_code == 200
    payload = import_response.json()
    assert payload["imported_rows"] == 2
    assert payload["linked_sku_rows"] == 2
    assert payload["history_rows"] == 2

    cost = db_session.scalar(select(SkuCost).where(SkuCost.article == "K-2650-CR"))
    assert cost is not None
    assert cost.product_name == "Ручка-кнопка из файла"
    assert float(cost.cost_rub) == 125.5
    assert cost.sku_id == sku.id
    assert cost.upload_file_id == file_id

    orphan_cost = db_session.scalar(select(SkuCost).where(SkuCost.article == "NEW-001"))
    assert orphan_cost is not None
    assert orphan_cost.product_name == "Kerron Новый артикул без SKU"
    assert float(orphan_cost.cost_rub) == 77.1
    assert orphan_cost.sku_id is not None
    created_sku = db_session.get(Sku, orphan_cost.sku_id)
    assert created_sku is not None
    assert created_sku.article == "NEW-001"
    assert created_sku.name == "Kerron Новый артикул без SKU"
    assert created_sku.brand == "Kerron"
    history_rows = db_session.scalars(
        select(SkuCostHistory).where(SkuCostHistory.upload_file_id == file_id)
    ).all()
    assert len(history_rows) == 2

    upload_file = db_session.get(UploadFile, file_id)
    assert upload_file is not None
    assert upload_file.batch.status == "applied"
    assert upload_file.batch.applied_rows == 2

    costs_response = client.get("/api/catalog/sku-costs", params={"query": "NEW-001"})
    assert costs_response.status_code == 200
    cost_rows = costs_response.json()
    assert len(cost_rows) == 1
    assert cost_rows[0]["article"] == "NEW-001"
    assert cost_rows[0]["product_name"] == "Kerron Новый артикул без SKU"
    assert cost_rows[0]["cost_rub"] == 77.1


def test_sku_cost_upload_auto_detects_and_imports(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
) -> None:
    workbook_path = tmp_path / "Себесстоимость.xlsx"
    pd.DataFrame(
        [
            {
                "Артикул": "AUTO-001",
                "Наименование": "Автоопределённый артикул",
                "Себестоимость, руб": 54.25,
            },
        ]
    ).to_excel(workbook_path, index=False)

    with workbook_path.open("rb") as file:
        upload_response = client.post(
            "/api/uploads/files",
            files={
                "file": (
                    workbook_path.name,
                    file,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )

    assert upload_response.status_code == 200
    payload = upload_response.json()
    file_id = payload["file"]["id"]
    assert payload["file"]["source_type"] == "sku_costs"
    assert payload["file"]["detected_source_type"] == "sku_costs"
    assert payload["file"]["status"] == "applied"
    assert payload["file"]["source_detection"]["requires_confirmation"] is False
    assert payload["file"]["applied_rows"] == 1

    cost = db_session.scalar(select(SkuCost).where(SkuCost.article == "AUTO-001"))
    assert cost is not None
    assert cost.product_name == "Автоопределённый артикул"
    assert float(cost.cost_rub) == 54.25
    assert cost.upload_file_id == file_id

    history_count = db_session.scalar(
        select(func.count())
        .select_from(SkuCostHistory)
        .where(SkuCostHistory.upload_file_id == file_id)
    )
    assert history_count == 1


def test_sku_catalog_exposes_cost_fields(client: TestClient, db_session: Session) -> None:
    sku = db_session.scalar(select(Sku).where(Sku.article == "K-2650-CR"))
    assert sku is not None
    db_session.add(
        SkuCost(
            article=sku.article,
            product_name="Ручка-кнопка из файла",
            cost_rub=125.5,
            sku_id=sku.id,
        )
    )
    db_session.commit()

    list_response = client.get("/api/catalog/skus", params={"query": "K-2650-CR"})
    assert list_response.status_code == 200
    item = next(row for row in list_response.json() if row["article"] == "K-2650-CR")
    assert item["cost_rub"] == 125.5
    assert item["cost_product_name"] == "Ручка-кнопка из файла"

    detail_response = client.get(f"/api/catalog/skus/{sku.id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["cost"]["article"] == "K-2650-CR"
    assert detail["cost"]["product_name"] == "Ручка-кнопка из файла"
    assert detail["cost"]["cost_rub"] == 125.5


def test_sku_catalog_hides_uncosted_category_like_rows(
    client: TestClient,
    db_session: Session,
) -> None:
    db_session.add(
        Sku(
            article="01. Вазы",
            name="01. Вазы",
            brand="MAGAMAX",
            unit="pcs",
            active=True,
        )
    )
    db_session.commit()

    response = client.get("/api/catalog/skus")
    assert response.status_code == 200
    articles = {row["article"] for row in response.json()}
    assert "01. Вазы" not in articles
