from __future__ import annotations

import sys
import types
from io import BytesIO
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from apps.api.app.modules.mapping.service import build_mapping_fields, detect_source_type
from apps.api.app.modules.uploads.parsers import read_upload_frame, read_upload_payload
from apps.api.app.modules.uploads.validation import validate_frame


def _upload_file(
    client: TestClient,
    fixture_path: Path,
    source_type: str,
    content_type: str = "text/csv",
) -> dict[str, object]:
    with fixture_path.open("rb") as fixture_file:
        response = client.post(
            "/api/uploads/files",
            headers={"X-Dev-User": "user_admin"},
            data={"source_type": source_type},
            files={"file": (fixture_path.name, fixture_file, content_type)},
        )
    assert response.status_code == 200
    return response.json()


def test_read_upload_frame_supports_messy_csv_and_xlsx(tmp_path: Path) -> None:
    csv_result = read_upload_frame(Path("data/fixtures/uploads/sales_messy.csv"))
    assert list(csv_result.frame.columns) == ["Артикул", "Контрагент", "Кол-во", "Период", "Выручка"]

    xlsx_path = tmp_path / "sales.xlsx"
    pd.DataFrame([{"Артикул": "K-2650-CR", "Сеть": "Leman Pro", "Кол-во": 420, "Дата": "2026-04-01"}]).to_excel(
        xlsx_path, index=False
    )
    xlsx_result = read_upload_frame(xlsx_path)
    assert xlsx_result.parser == "xlsx"
    assert list(xlsx_result.frame.columns) == ["Артикул", "Сеть", "Кол-во", "Дата"]


def test_read_upload_payload_supports_csv_bytes() -> None:
    payload = Path("data/fixtures/uploads/sales_messy.csv").read_bytes()
    result = read_upload_payload(payload, "sales_messy.csv")
    assert result.parser == "csv"
    assert list(result.frame.columns) == ["Артикул", "Контрагент", "Кол-во", "Период", "Выручка"]


def test_mapping_engine_handles_messy_sales_headers() -> None:
    frame = read_upload_frame(Path("data/fixtures/uploads/sales_messy.csv")).frame
    source_type = detect_source_type(list(frame.columns), explicit_source_type=None)
    mappings = build_mapping_fields(frame, source_type)
    canonical_map = {item.source: item.canonical for item in mappings}

    assert source_type == "sales"
    assert canonical_map["Артикул"] == "sku_code"
    assert canonical_map["Контрагент"] == "client_name"
    assert canonical_map["Кол-во"] == "quantity"
    assert canonical_map["Период"] == "period_date"
    assert any(item.required for item in mappings if item.canonical == "sku_code")


def test_validation_emits_negative_stock_warning() -> None:
    frame = read_upload_frame(Path("data/fixtures/uploads/stock_negative.csv")).frame
    mapping = {
        "snapshot date": "snapshot_date",
        "article": "sku_code",
        "free stock": "stock_free",
        "total stock": "stock_total",
        "warehouse": "warehouse_name",
    }
    result = validate_frame(frame, "stock", mapping)
    assert result.warning_count >= 1
    assert any(issue.code == "negative_stock" for issue in result.issues)


def test_upload_preview_flow_returns_real_preview(client: TestClient) -> None:
    payload = _upload_file(client, Path("data/fixtures/uploads/sales_valid.csv"), "sales")
    file_id = payload["file"]["id"]

    preview_response = client.get(f"/api/uploads/files/{file_id}/preview")
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["headers"] == ["article", "client", "quantity", "period"]
    assert preview["sample_row_count"] == 3

    detail_response = client.get(f"/api/uploads/files/{file_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["file"]["status"] == "ready_to_apply"
    assert detail["validation"]["valid_rows"] == 3
    assert detail["file"]["readiness"]["can_apply"] is True


def test_duplicate_upload_warning_path(client: TestClient) -> None:
    first = _upload_file(client, Path("data/fixtures/uploads/sales_valid.csv"), "sales")
    second = _upload_file(client, Path("data/fixtures/uploads/sales_valid.csv"), "sales")

    assert second["file"]["duplicate_of_batch_id"] == first["file"]["batch_id"]
    assert second["validation"]["issue_counts"]["warning"] >= 1
    issues_response = client.get(f"/api/uploads/files/{second['file']['id']}/issues")
    assert issues_response.status_code == 200
    assert any(issue["code"] == "duplicate_upload" for issue in issues_response.json()["items"])


def test_partial_success_path_and_issues_listing(client: TestClient) -> None:
    payload = _upload_file(client, Path("data/fixtures/uploads/diy_clients_invalid.csv"), "diy_clients")
    file_id = payload["file"]["id"]
    assert payload["file"]["status"] == "issues_found"

    issues_response = client.get(f"/api/uploads/files/{file_id}/issues")
    assert issues_response.status_code == 200
    issues = issues_response.json()["items"]
    assert any(issue["code"] == "invalid_reserve_months" for issue in issues)
    assert any(issue["code"] == "duplicate_active_policy" for issue in issues)


def test_mapping_template_and_alias_endpoints(client: TestClient) -> None:
    template_response = client.post(
        "/api/mapping/templates",
        headers={"X-Dev-User": "user_admin"},
        json={
            "name": "Sales Russian",
            "source_type": "sales",
            "mappings": {
                "Артикул": "sku_code",
                "Контрагент": "client_name",
                "Кол-во": "quantity",
                "Период": "period_date",
            },
            "required_fields": ["sku_code", "client_name", "quantity", "period_date"],
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["id"]

    upload_payload = _upload_file(client, Path("data/fixtures/uploads/sales_messy.csv"), "sales")
    file_id = upload_payload["file"]["id"]

    apply_template_response = client.post(
        f"/api/mapping/templates/{template_id}/apply",
        headers={"X-Dev-User": "user_admin"},
        json={"file_id": file_id},
    )
    assert apply_template_response.status_code == 200
    assert apply_template_response.json()["mapping"]["template_id"] == template_id

    sku_alias_response = client.post(
        "/api/mapping/aliases/skus",
        headers={"X-Dev-User": "user_admin"},
        json={"alias": "alias-k2650", "entity_code": "K-2650-CR"},
    )
    client_alias_response = client.post(
        "/api/mapping/aliases/clients",
        headers={"X-Dev-User": "user_admin"},
        json={"alias": "Леман Про", "entity_code": "leman-pro"},
    )
    assert sku_alias_response.status_code == 200
    assert client_alias_response.status_code == 200


def test_alias_resolution_path_allows_apply(client: TestClient) -> None:
    client.post(
        "/api/mapping/aliases/skus",
        headers={"X-Dev-User": "user_admin"},
        json={"alias": "alias-k2650", "entity_code": "K-2650-CR"},
    )
    client.post(
        "/api/mapping/aliases/clients",
        headers={"X-Dev-User": "user_admin"},
        json={"alias": "Леман Про", "entity_code": "leman-pro"},
    )

    payload = BytesIO(
        b"article,client,quantity,period\nalias-k2650,\xd0\x9b\xd0\xb5\xd0\xbc\xd0\xb0\xd0\xbd \xd0\x9f\xd1\x80\xd0\xbe,180,2026-04-01\n"
    )
    response = client.post(
        "/api/uploads/files",
        headers={"X-Dev-User": "user_admin"},
        data={"source_type": "sales"},
        files={"file": ("sales_alias.csv", payload, "text/csv")},
    )
    assert response.status_code == 200
    file_id = response.json()["file"]["id"]

    apply_response = client.post(
        f"/api/uploads/files/{file_id}/apply",
        headers={"X-Dev-User": "user_admin"},
    )
    assert apply_response.status_code == 200
    assert apply_response.json()["applied_rows"] == 1


def test_s3_backed_upload_flow_reads_preview_and_validates_via_object_storage(
    client: TestClient,
    test_settings,
    monkeypatch,
) -> None:
    class FakeS3Client:
        def __init__(self) -> None:
            self._buckets: set[str] = set()
            self._objects: dict[tuple[str, str], bytes] = {}

        def head_bucket(self, *, Bucket: str) -> None:
            if Bucket not in self._buckets:
                raise RuntimeError("bucket not found")

        def create_bucket(self, *, Bucket: str) -> None:
            self._buckets.add(Bucket)

        def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str) -> None:
            self._buckets.add(Bucket)
            self._objects[(Bucket, Key)] = Body

        def get_object(self, *, Bucket: str, Key: str) -> dict[str, BytesIO]:
            return {"Body": BytesIO(self._objects[(Bucket, Key)])}

    fake_s3 = FakeS3Client()
    monkeypatch.setitem(sys.modules, "boto3", types.SimpleNamespace(client=lambda *args, **kwargs: fake_s3))
    test_settings.object_storage_mode = "s3"
    test_settings.s3_bucket = "shaytan-machine-tests"
    test_settings.s3_access_key = "minioadmin"
    test_settings.s3_secret_key = "minioadmin"
    test_settings.s3_endpoint_url = "http://127.0.0.1:9000"

    payload = _upload_file(client, Path("data/fixtures/uploads/sales_valid.csv"), "sales")
    file_id = payload["file"]["id"]

    preview_response = client.get(f"/api/uploads/files/{file_id}/preview")
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["headers"] == ["article", "client", "quantity", "period"]

    validate_response = client.post(
        f"/api/uploads/files/{file_id}/validate",
        headers={"X-Dev-User": "user_admin"},
    )
    assert validate_response.status_code == 200
    assert validate_response.json()["file"]["status"] == "ready_to_apply"


def test_raw_report_uses_review_only_lifecycle(client: TestClient) -> None:
    payload = _upload_file(client, Path("data/fixtures/uploads/sales_valid.csv"), "raw_report")
    file_id = payload["file"]["id"]

    assert payload["file"]["status"] == "ready_to_review"
    assert payload["file"]["readiness"]["can_apply"] is False
    assert payload["file"]["readiness"]["can_validate"] is False

    validate_response = client.post(
        f"/api/uploads/files/{file_id}/validate",
        headers={"X-Dev-User": "user_admin"},
    )
    assert validate_response.status_code == 200
    assert validate_response.json()["file"]["status"] == "ready_to_review"

    apply_response = client.post(
        f"/api/uploads/files/{file_id}/apply",
        headers={"X-Dev-User": "user_admin"},
    )
    assert apply_response.status_code == 400
    assert apply_response.json()["code"] == "apply_not_supported"


def test_upload_list_and_issue_endpoints_return_real_pagination_meta(client: TestClient) -> None:
    first = _upload_file(client, Path("data/fixtures/uploads/sales_valid.csv"), "sales")
    second = _upload_file(client, Path("data/fixtures/uploads/diy_clients_invalid.csv"), "diy_clients")

    files_page = client.get("/api/uploads/files", params={"page": 1, "page_size": 1})
    assert files_page.status_code == 200
    files_payload = files_page.json()
    assert files_payload["meta"]["total"] >= 2
    assert len(files_payload["items"]) == 1

    issues_page = client.get(
        f"/api/uploads/files/{second['file']['id']}/issues",
        params={"page": 1, "page_size": 1},
    )
    assert issues_page.status_code == 200
    issues_payload = issues_page.json()
    assert issues_payload["meta"]["total"] >= 1
    assert len(issues_payload["items"]) == 1

    batches_page = client.get("/api/uploads/batches", params={"page": 1, "page_size": 1})
    assert batches_page.status_code == 200
    batches_payload = batches_page.json()
    assert batches_payload["meta"]["total"] >= 2
    assert len(batches_payload["items"]) == 1
