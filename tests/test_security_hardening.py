from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.config import Settings
from apps.api.app.core.rate_limit import _MEMORY_LIMITS
from apps.api.app.db.models import RefreshToken


def test_assert_production_safety_blocks_explicit_unsafe_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import apps.api.app.main as main_module

    unsafe_settings = Settings(
        app_env="production",
        app_debug=True,
        jwt_secret="change-me-for-production",
        startup_schema_mode="auto_create",
        dev_admin_password="magamax-admin",
        s3_secret_key="minioadmin",
    )
    monkeypatch.setattr(main_module, "settings", unsafe_settings)

    with pytest.raises(RuntimeError) as exc_info:
        main_module.assert_production_safety()

    message = str(exc_info.value)
    assert "JWT_SECRET uses the unsafe production placeholder" in message
    assert "APP_DEBUG must be false in production" in message
    assert "STARTUP_SCHEMA_MODE=auto_create is forbidden in production" in message
    assert "DEV_ADMIN_PASSWORD uses an unsafe production value" in message
    assert "S3_SECRET_KEY uses an unsafe production value" in message


def test_x_dev_user_header_is_forbidden_outside_development(
    anonymous_client: TestClient,
    test_settings: Settings,
) -> None:
    test_settings.app_env = "production"

    response = anonymous_client.get("/api/auth/me", headers={"X-Dev-User": "user_admin"})

    assert response.status_code == 403
    assert response.json()["message"] == "Dev auth disabled in production"


def test_login_issues_refresh_token_and_refresh_endpoint_returns_access_token(
    anonymous_client: TestClient,
    db_session: Session,
) -> None:
    login_response = anonymous_client.post(
        "/api/auth/login",
        json={"email": "admin@magamax.local", "password": "magamax-admin"},
    )

    assert login_response.status_code == 200
    login_payload = login_response.json()
    assert login_payload["token_type"] == "bearer"
    assert login_payload["access_token"]
    assert login_payload["refresh_token"]

    token_hash = hashlib.sha256(login_payload["refresh_token"].encode("utf-8")).hexdigest()
    stored = db_session.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    assert stored is not None
    assert stored.revoked_at is None

    refresh_response = anonymous_client.post(
        "/api/auth/refresh",
        json={"refresh_token": login_payload["refresh_token"]},
    )

    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.json()
    assert refresh_payload["token_type"] == "bearer"
    assert refresh_payload["access_token"]
    assert "refresh_token" not in refresh_payload


def test_logout_revokes_refresh_token(anonymous_client: TestClient, db_session: Session) -> None:
    login_response = anonymous_client.post(
        "/api/auth/login",
        json={"email": "admin@magamax.local", "password": "magamax-admin"},
    )
    assert login_response.status_code == 200
    login_payload = login_response.json()

    logout_response = anonymous_client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {login_payload['access_token']}"},
        json={"refresh_token": login_payload["refresh_token"]},
    )

    assert logout_response.status_code == 200
    assert logout_response.json()["status"] == "ok"

    token_hash = hashlib.sha256(login_payload["refresh_token"].encode("utf-8")).hexdigest()
    stored = db_session.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    assert stored is not None
    assert stored.revoked_at is not None

    refresh_response = anonymous_client.post(
        "/api/auth/refresh",
        json={"refresh_token": login_payload["refresh_token"]},
    )
    assert refresh_response.status_code == 401


def test_auth_rate_limit_returns_retry_after_header(
    anonymous_client: TestClient,
    test_settings: Settings,
) -> None:
    _MEMORY_LIMITS.clear()
    test_settings.app_env = "production"
    test_settings.redis_url = ""

    last_response = None
    for _ in range(11):
        last_response = anonymous_client.post(
            "/api/auth/login",
            json={"email": "missing@magamax.local", "password": "wrong"},
        )

    assert last_response is not None
    assert last_response.status_code == 429
    assert last_response.headers["Retry-After"]


def test_backup_duckdb_copies_to_local_storage_and_prunes_old_backups(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.worker.worker_app import tasks

    duckdb_path = tmp_path / "analytics.duckdb"
    duckdb_path.write_bytes(b"duckdb-test-copy")
    local_storage_root = tmp_path / "object-storage"
    export_root = tmp_path / "exports"
    old_backup = local_storage_root / "backups" / "duckdb" / "2000-01-01_00-00.duckdb"
    old_backup.parent.mkdir(parents=True, exist_ok=True)
    old_backup.write_bytes(b"old")
    os.utime(old_backup, (datetime(2000, 1, 1, tzinfo=UTC).timestamp(),) * 2)

    settings = Settings(
        app_env="development",
        duckdb_path=str(duckdb_path),
        local_object_storage_root=str(local_storage_root),
        export_root=str(export_root),
        object_storage_mode="local",
        redis_url="",
    )
    monkeypatch.setattr(tasks, "get_settings", lambda: settings)

    result = tasks.backup_duckdb.fn()

    assert result["status"] == "ok"
    backup_path = local_storage_root / str(result["storage_key"])
    assert backup_path.exists()
    assert backup_path.read_bytes() == b"duckdb-test-copy"
    assert not old_backup.exists()
