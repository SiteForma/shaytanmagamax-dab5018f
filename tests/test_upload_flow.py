from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_upload_apply_flow_updates_sales_series(client: TestClient) -> None:
    before = client.get("/api/sales/monthly", params={"sku_id": "sku_1", "client_id": "client_2"})
    assert before.status_code == 200
    before_count = len(before.json())

    fixture_path = Path("data/fixtures/uploads/sales_valid.csv")
    with fixture_path.open("rb") as fixture_file:
        upload_response = client.post(
            "/api/uploads",
            headers={"X-Dev-User": "user_admin"},
            data={"source_type": "sales"},
            files={"file": ("sales_valid.csv", fixture_file, "text/csv")},
        )
    assert upload_response.status_code == 200
    batch_id = upload_response.json()["job"]["id"]

    apply_response = client.post(
        f"/api/uploads/{batch_id}/apply",
        headers={"X-Dev-User": "user_admin"},
    )
    assert apply_response.status_code == 200
    assert apply_response.json()["applied_rows"] == 3

    after = client.get("/api/sales/monthly", params={"sku_id": "sku_1", "client_id": "client_2"})
    assert after.status_code == 200
    assert len(after.json()) >= before_count
    assert any(row["month"] == "2026-04" and row["qty"] == 420.0 for row in after.json())
