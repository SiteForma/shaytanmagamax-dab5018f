from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "Shaytan Machine"
    app_debug: bool = True
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_release: str | None = None

    database_url: str = "sqlite:///./data/dev/shaytan_machine.db"
    redis_url: str = "redis://localhost:6379/0"
    duckdb_path: str = "./data/analytics/shaytan_machine.duckdb"
    parquet_root: str = "./data/analytics/parquet"

    object_storage_mode: Literal["local", "s3"] = "local"
    local_object_storage_root: str = "./data/object-storage"
    export_root: str = "./data/exports"
    export_async_enabled: bool = True
    export_async_row_threshold: int = 500
    s3_endpoint_url: str | None = None
    s3_bucket: str = "shaytan-machine"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None

    jwt_secret: str = "change-me-for-production"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 480

    assistant_provider: Literal["deterministic", "openai_compatible"] = "deterministic"
    assistant_llm_enabled: bool = False
    assistant_openai_base_url: str | None = None
    assistant_openai_api_key: str | None = None
    assistant_openai_model: str = "gpt-5.4-mini"
    assistant_input_usd_per_1m_tokens: float = 0.15
    assistant_output_usd_per_1m_tokens: float = 0.60
    assistant_rub_per_usd: float = 300.0
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.0
    otel_enabled: bool = False
    otel_service_name: str = "shaytan-machine-api"
    otel_exporter_otlp_endpoint: str | None = None

    startup_schema_mode: Literal["auto_create", "migrations_only"] = "auto_create"
    startup_seed_sample_data: bool = False
    startup_materialize_analytics: bool = False

    dev_admin_email: str = "admin@magamax.local"
    dev_admin_password: str = "magamax-admin"

    cors_origins: str = Field(default="http://127.0.0.1:8090,http://localhost:8090")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def should_auto_create_schema(self) -> bool:
        return self.app_env != "production" and self.startup_schema_mode == "auto_create"

    @property
    def should_seed_sample_data(self) -> bool:
        return self.app_env != "production" and self.startup_seed_sample_data

    @property
    def should_materialize_analytics_on_startup(self) -> bool:
        return self.app_env != "production" and self.startup_materialize_analytics

    def production_startup_errors(self) -> list[str]:
        if self.app_env != "production":
            return []
        errors: list[str] = []
        if self.app_debug:
            errors.append("APP_DEBUG must be false in production")
        if self.database_url.startswith("sqlite"):
            errors.append("DATABASE_URL must point to PostgreSQL in production")
        if self.jwt_secret == "change-me-for-production" or len(self.jwt_secret) < 32:
            errors.append("JWT_SECRET must be a non-default secret with at least 32 characters")
        if self.dev_admin_email == "admin@magamax.local" or self.dev_admin_password == "magamax-admin":
            errors.append("DEV_ADMIN_EMAIL/DEV_ADMIN_PASSWORD must not use local defaults in production")
        if self.startup_schema_mode != "migrations_only":
            errors.append("STARTUP_SCHEMA_MODE must be migrations_only in production")
        if self.startup_seed_sample_data:
            errors.append("STARTUP_SEED_SAMPLE_DATA must be false in production")
        if self.startup_materialize_analytics:
            errors.append("STARTUP_MATERIALIZE_ANALYTICS must be false in production")
        if not self.redis_url:
            errors.append("REDIS_URL is required for production workers and async jobs")
        if not self.export_async_enabled:
            errors.append("EXPORT_ASYNC_ENABLED must be true in production")
        if self.object_storage_mode != "s3":
            errors.append("OBJECT_STORAGE_MODE must be s3 in production")
        if self.object_storage_mode == "s3" and (
            not self.s3_endpoint_url
            or not self.s3_bucket
            or not self.s3_access_key
            or not self.s3_secret_key
        ):
            errors.append("S3_ENDPOINT_URL, S3_BUCKET, S3_ACCESS_KEY and S3_SECRET_KEY are required")
        if not self.sentry_dsn:
            errors.append("SENTRY_DSN is required in production")
        if not self.otel_enabled:
            errors.append("OTEL_ENABLED must be true in production")
        if not self.otel_exporter_otlp_endpoint:
            errors.append("OTEL_EXPORTER_OTLP_ENDPOINT is required in production")
        if not self.app_release:
            errors.append("APP_RELEASE is required in production")
        return errors

    def validate_for_startup(self) -> None:
        errors = self.production_startup_errors()
        if errors:
            raise RuntimeError("Unsafe production configuration: " + "; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    return Settings()
