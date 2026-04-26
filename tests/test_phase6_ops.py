from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.app.core.config import Settings
from apps.api.app.db.base import Base
from apps.api.app.db.models import JobRun, Sku
from apps.api.app.db.seed import seed_reference_data


def test_admin_permissions_and_role_change_flow(client: TestClient) -> None:
    operator_users = client.get("/api/admin/users", headers={"X-Dev-User": "user_operator"})
    assert operator_users.status_code == 200
    assert len(operator_users.json()) >= 4

    operator_role_patch = client.patch(
        "/api/admin/users/user_viewer/role",
        headers={"X-Dev-User": "user_operator"},
        json={"role": "analyst"},
    )
    assert operator_role_patch.status_code == 403
    assert operator_role_patch.json()["code"] == "permission_denied"

    admin_role_patch = client.patch(
        "/api/admin/users/user_viewer/role",
        headers={"X-Dev-User": "user_admin"},
        json={"role": "analyst"},
    )
    assert admin_role_patch.status_code == 200
    assert admin_role_patch.json()["roles"] == ["analyst"]


def test_reserve_export_generation_download_and_audit(client: TestClient, tmp_path: Path) -> None:
    reserve_response = client.post(
        "/api/reserve/calculate",
        headers={"X-Dev-User": "user_admin"},
        json={
            "client_ids": ["client_2"],
            "sku_ids": ["sku_1", "sku_3"],
            "reserve_months": 3,
            "safety_factor": 1.1,
            "demand_strategy": "weighted_recent_average",
            "horizon_days": 60,
        },
    )
    assert reserve_response.status_code == 200
    run_id = reserve_response.json()["run"]["id"]

    export_response = client.post(
        f"/api/exports/reserve-runs/{run_id}",
        headers={"X-Dev-User": "user_admin"},
        params={"format": "csv"},
    )
    assert export_response.status_code == 200
    export_job = export_response.json()
    assert export_job["status"] == "completed"
    assert export_job["canDownload"] is True

    download_response = client.get(
        f"/api/exports/jobs/{export_job['id']}/download",
        headers={"X-Dev-User": "user_admin"},
    )
    assert download_response.status_code == 200
    assert "text/csv" in download_response.headers["content-type"]
    assert b"\xd0\x9a\xd0\xbb\xd0\xb8\xd0\xb5\xd0\xbd\xd1\x82" in download_response.content

    audit_response = client.get(
        "/api/admin/audit-events",
        headers={"X-Dev-User": "user_admin"},
        params={"action": "exports.generate"},
    )
    assert audit_response.status_code == 200
    audit_items = audit_response.json()["items"]
    assert any(item["target_id"] == export_job["id"] for item in audit_items)


def test_upload_actions_emit_audit_events(client: TestClient) -> None:
    fixture_path = Path("data/fixtures/uploads/sales_valid.csv")
    with fixture_path.open("rb") as fixture_file:
        upload_response = client.post(
            "/api/uploads/files",
            headers={"X-Dev-User": "user_admin"},
            data={"source_type": "sales"},
            files={"file": ("sales_valid.csv", fixture_file, "text/csv")},
        )
    assert upload_response.status_code == 200
    file_id = upload_response.json()["file"]["id"]

    validate_response = client.post(
        f"/api/uploads/files/{file_id}/validate",
        headers={"X-Dev-User": "user_admin"},
    )
    assert validate_response.status_code == 200

    audit_response = client.get(
        "/api/admin/audit-events",
        headers={"X-Dev-User": "user_admin"},
        params={"targetType": "upload_file"},
    )
    assert audit_response.status_code == 200
    actions = {item["action"] for item in audit_response.json()["items"] if item["target_id"] == file_id}
    assert "uploads.file_uploaded" in actions
    assert "uploads.validated" in actions


def test_async_client_exposure_export_can_queue_and_retry(
    client: TestClient,
    db_session,
    test_settings,
    monkeypatch,
) -> None:
    test_settings.export_async_enabled = True
    test_settings.export_async_row_threshold = 1
    monkeypatch.setattr(
        "apps.api.app.modules.exports.service._enqueue_export_job",
        lambda settings, export_job_id, job_run_id: True,
    )

    export_response = client.post(
        "/api/exports/clients/exposure",
        headers={"X-Dev-User": "user_admin"},
        json={"format": "xlsx"},
    )
    assert export_response.status_code == 200
    export_job = export_response.json()
    assert export_job["status"] == "queued"
    assert export_job["canDownload"] is False

    job_run = db_session.scalars(select(JobRun).where(JobRun.job_name == "generate_export")).first()
    assert job_run is not None
    assert job_run.payload["export_job_id"] == export_job["id"]
    job_run.status = "failed"
    job_run.error_message = "worker timeout"
    db_session.add(job_run)
    db_session.commit()

    retry_response = client.post(
        f"/api/admin/jobs/{job_run.id}/retry",
        headers={"X-Dev-User": "user_admin"},
    )
    assert retry_response.status_code == 200
    assert retry_response.json()["jobName"] == "generate_export"


def test_diy_exposure_report_pack_export_generation(client: TestClient) -> None:
    response = client.post(
        "/api/exports/report-packs/diy-exposure",
        headers={"X-Dev-User": "user_admin"},
        json={"format": "xlsx"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["format"] == "xlsx"
    assert payload["status"] in {"completed", "queued"}


def test_production_settings_disable_implicit_startup_mutations() -> None:
    settings = Settings(
        app_env="production",
        startup_schema_mode="auto_create",
        startup_seed_sample_data=True,
        startup_materialize_analytics=True,
    )
    assert settings.should_auto_create_schema is False
    assert settings.should_seed_sample_data is False
    assert settings.should_materialize_analytics_on_startup is False
    assert "STARTUP_SCHEMA_MODE must be migrations_only in production" in settings.production_startup_errors()


def test_production_settings_block_unsafe_defaults() -> None:
    settings = Settings(app_env="production")
    errors = settings.production_startup_errors()
    assert "APP_DEBUG must be false in production" in errors
    assert "DATABASE_URL must point to PostgreSQL in production" in errors
    assert "JWT_SECRET must be a non-default secret with at least 32 characters" in errors
    assert "OBJECT_STORAGE_MODE must be s3 in production" in errors
    assert "SENTRY_DSN is required in production" in errors
    assert "OTEL_ENABLED must be true in production" in errors


def test_production_settings_accept_staging_like_posture() -> None:
    settings = Settings(
        app_env="production",
        app_debug=False,
        app_release="test-release",
        database_url="postgresql+psycopg://magamax:magamax@localhost:5432/shaytan_machine",
        redis_url="redis://localhost:6379/0",
        object_storage_mode="s3",
        s3_endpoint_url="http://localhost:9000",
        s3_bucket="shaytan-machine",
        s3_access_key="minioadmin",
        s3_secret_key="minioadmin",
        jwt_secret="x" * 40,
        sentry_dsn="https://public@example.com/1",
        otel_enabled=True,
        otel_exporter_otlp_endpoint="http://localhost:4318/v1/traces",
        startup_schema_mode="migrations_only",
        startup_seed_sample_data=False,
        startup_materialize_analytics=False,
        export_async_enabled=True,
        dev_admin_email="ops@example.com",
        dev_admin_password="not-a-local-password",
    )
    assert settings.production_startup_errors() == []


def test_seed_reference_data_respects_foreign_keys_with_strict_sqlite(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'seed_fk.db'}", future=True)

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.create_all(bind=engine)
    settings = Settings(
        app_env="development",
        database_url=f"sqlite:///{tmp_path / 'seed_fk.db'}",
        local_object_storage_root=str(tmp_path / "object-storage"),
        parquet_root=str(tmp_path / "parquet"),
        duckdb_path=str(tmp_path / "analytics.duckdb"),
        dev_admin_email="admin@magamax.local",
        dev_admin_password="magamax-admin",
    )

    with SessionLocal() as session:
        seed_reference_data(session, settings)
        assert session.scalar(select(Sku.id).limit(1)) is not None

    Base.metadata.drop_all(bind=engine)


def test_admin_health_details_and_ready_endpoint_include_ops_posture(client: TestClient) -> None:
    health_response = client.get("/api/admin/system/health-details", headers={"X-Dev-User": "user_admin"})
    assert health_response.status_code == 200
    health = health_response.json()
    assert "workerQueues" in health
    assert "environmentWarnings" in health
    assert "startupSchemaMode" in health
    assert "exportAsyncEnabled" in health

    ready_response = client.get("/api/health/ready")
    assert ready_response.status_code == 200
    ready = ready_response.json()
    assert "redis_configured" in ready
    assert "startup_schema_mode" in ready
