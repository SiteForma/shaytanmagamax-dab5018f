from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from apps.api.app.api.dependencies import get_db, get_settings_dependency
from apps.api.app.core.config import Settings
from apps.api.app.db.base import Base
from apps.api.app.db.seed import seed_reference_data
from apps.api.app.main import create_app


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="development",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        redis_url="",
        local_object_storage_root=str(tmp_path / "object-storage"),
        parquet_root=str(tmp_path / "parquet"),
        duckdb_path=str(tmp_path / "analytics.duckdb"),
        dev_admin_email="admin@magamax.local",
        dev_admin_password="magamax-admin",
    )


@pytest.fixture
def db_session(test_settings: Settings) -> Generator[Session, None, None]:
    engine = create_engine(test_settings.database_url, future=True)
    TestingSessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, class_=Session
    )
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as session:
        seed_reference_data(session, test_settings)
    with TestingSessionLocal() as session:
        yield session
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session: Session, test_settings: Settings) -> Generator[TestClient, None, None]:
    app = create_app()
    app.router.on_startup.clear()
    app.router.on_shutdown.clear()

    def override_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings_dependency] = lambda: test_settings

    with TestClient(app) as test_client:
        test_client.headers.update({"X-Dev-User": "user_admin"})
        yield test_client


@pytest.fixture
def anonymous_client(db_session: Session, test_settings: Settings) -> Generator[TestClient, None, None]:
    app = create_app()
    app.router.on_startup.clear()
    app.router.on_shutdown.clear()

    def override_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings_dependency] = lambda: test_settings

    with TestClient(app) as test_client:
        yield test_client
