from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.app.common.utils import generate_id, utc_now
from apps.api.app.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Role(TimestampMixin, Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("role")
    )
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("user")
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    roles: Mapped[list["UserRole"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[str] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    user: Mapped[User] = relationship(back_populates="roles")
    role: Mapped[Role] = relationship()


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    user: Mapped[User] = relationship()


class AccessPolicy(TimestampMixin, Base):
    __tablename__ = "access_policies"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("pol")
    )
    role_code: Mapped[str] = mapped_column(String(64), index=True)
    resource: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(64))
    effect: Mapped[str] = mapped_column(String(16), default="allow")


class Category(TimestampMixin, Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("cat")
    )
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    level: Mapped[int] = mapped_column(Integer, default=0)
    path: Mapped[str] = mapped_column(String(500))
    parent: Mapped["Category | None"] = relationship(remote_side=[id])


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("prd")
    )
    name: Mapped[str] = mapped_column(String(255))
    brand: Mapped[str] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Sku(TimestampMixin, Base):
    __tablename__ = "skus"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("sku")
    )
    article: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    brand: Mapped[str] = mapped_column(String(120))
    unit: Mapped[str] = mapped_column(String(16), default="pcs")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    category: Mapped[Category | None] = relationship()
    product: Mapped[Product | None] = relationship()


class SkuAlias(TimestampMixin, Base):
    __tablename__ = "sku_aliases"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("skualias")
    )
    sku_id: Mapped[str] = mapped_column(ForeignKey("skus.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column(String(255), index=True)
    sku: Mapped[Sku] = relationship()


class SkuCost(TimestampMixin, Base):
    __tablename__ = "sku_costs"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("skucost")
    )
    article: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    product_name: Mapped[str] = mapped_column(String(255))
    cost_rub: Mapped[float] = mapped_column(Numeric(18, 4))
    sku_id: Mapped[str | None] = mapped_column(
        ForeignKey("skus.id", ondelete="SET NULL"), nullable=True, index=True
    )
    upload_file_id: Mapped[str | None] = mapped_column(
        ForeignKey("upload_files.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_payload: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    sku: Mapped[Sku | None] = relationship()
    upload_file: Mapped["UploadFile | None"] = relationship()


class SkuCostHistory(TimestampMixin, Base):
    __tablename__ = "sku_cost_history"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("skucosthist")
    )
    article: Mapped[str] = mapped_column(String(120), index=True)
    product_name: Mapped[str] = mapped_column(String(255))
    cost_rub: Mapped[float] = mapped_column(Numeric(18, 4))
    sku_id: Mapped[str | None] = mapped_column(
        ForeignKey("skus.id", ondelete="SET NULL"), nullable=True, index=True
    )
    upload_file_id: Mapped[str | None] = mapped_column(
        ForeignKey("upload_files.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_payload: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    sku: Mapped[Sku | None] = relationship()
    upload_file: Mapped["UploadFile | None"] = relationship()


class Client(TimestampMixin, Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("client")
    )
    code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    region: Mapped[str] = mapped_column(String(120))
    client_group: Mapped[str] = mapped_column(String(120), default="DIY")
    network_type: Mapped[str] = mapped_column(String(120), default="DIY")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    policies: Mapped[list["DiyPolicy"]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )


class ClientAlias(TimestampMixin, Base):
    __tablename__ = "client_aliases"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("clalias")
    )
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column(String(255), index=True)
    client: Mapped[Client] = relationship()


class DiyPolicy(TimestampMixin, Base):
    __tablename__ = "diy_policies"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("policy")
    )
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    reserve_months: Mapped[int] = mapped_column(Integer, default=3)
    safety_factor: Mapped[float] = mapped_column(Float, default=1.1)
    priority_level: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    allowed_fallback_depth: Mapped[int] = mapped_column(Integer, default=4)
    fallback_chain: Mapped[list[str]] = mapped_column(JSON, default=list)
    category_overrides: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    sku_overrides: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    inclusion_rules: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    exclusion_rules: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    client: Mapped[Client] = relationship(back_populates="policies")


class MappingTemplate(TimestampMixin, Base):
    __tablename__ = "mapping_templates"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("maptpl")
    )
    name: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    required_fields: Mapped[list[str]] = mapped_column(JSON, default=list)
    transformation_hints: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    rules: Mapped[list["MappingRule"]] = relationship(
        back_populates="template", cascade="all, delete-orphan"
    )


class MappingRule(TimestampMixin, Base):
    __tablename__ = "mapping_rules"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("maprule")
    )
    template_id: Mapped[str] = mapped_column(
        ForeignKey("mapping_templates.id", ondelete="CASCADE"), index=True
    )
    source_header: Mapped[str] = mapped_column(String(255))
    canonical_field: Mapped[str] = mapped_column(String(255))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    template: Mapped[MappingTemplate] = relationship(back_populates="rules")


class DataSource(TimestampMixin, Base):
    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("src")
    )
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(64))
    parsing_version: Mapped[str] = mapped_column(String(32), default="v1")
    normalization_version: Mapped[str] = mapped_column(String(32), default="v1")


class UploadBatch(TimestampMixin, Base):
    __tablename__ = "upload_batches"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("batch")
    )
    source_type: Mapped[str] = mapped_column(String(64), index=True)
    detected_source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="uploaded", index=True)
    uploaded_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    mapping_template_id: Mapped[str | None] = mapped_column(
        ForeignKey("mapping_templates.id"), nullable=True
    )
    parsing_version: Mapped[str] = mapped_column(String(32), default="v1")
    normalization_version: Mapped[str] = mapped_column(String(32), default="v1")
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0)
    applied_rows: Mapped[int] = mapped_column(Integer, default=0)
    failed_rows: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    issue_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_of_batch_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    mapping_payload: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    preview_payload: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    validation_payload: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    status_payload: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    files: Mapped[list["UploadFile"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class UploadFile(TimestampMixin, Base):
    __tablename__ = "upload_files"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("file")
    )
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("upload_batches.id", ondelete="CASCADE"), index=True
    )
    file_name: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(64))
    content_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(128))
    storage_key: Mapped[str] = mapped_column(String(500))
    batch: Mapped[UploadBatch] = relationship(back_populates="files")


class UploadedRowIssue(TimestampMixin, Base):
    __tablename__ = "uploaded_row_issues"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("rowiss")
    )
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("upload_batches.id", ondelete="CASCADE"), index=True
    )
    file_id: Mapped[str] = mapped_column(
        ForeignKey("upload_files.id", ondelete="CASCADE"), index=True
    )
    row_number: Mapped[int] = mapped_column(Integer)
    field_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    code: Mapped[str] = mapped_column(String(128), index=True)
    severity: Mapped[str] = mapped_column(String(32), default="medium")
    message: Mapped[str] = mapped_column(Text)
    raw_payload: Mapped[dict[str, object] | None] = mapped_column(
        MutableDict.as_mutable(JSON), nullable=True
    )


class SalesFact(TimestampMixin, Base):
    __tablename__ = "sales_facts"
    __table_args__ = (
        UniqueConstraint("client_id", "sku_id", "period_month", name="uq_sales_period"),
    )

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("sale")
    )
    source_batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("upload_batches.id"), nullable=True
    )
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), index=True)
    sku_id: Mapped[str] = mapped_column(ForeignKey("skus.id"), index=True)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    period_month: Mapped[date] = mapped_column(Date, index=True)
    quantity: Mapped[float] = mapped_column(Float)
    revenue_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)


class StockSnapshot(TimestampMixin, Base):
    __tablename__ = "stock_snapshots"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("stock")
    )
    source_batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("upload_batches.id"), nullable=True
    )
    sku_id: Mapped[str] = mapped_column(ForeignKey("skus.id"), index=True)
    warehouse_code: Mapped[str] = mapped_column(String(120))
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    free_stock_qty: Mapped[float] = mapped_column(Float)
    reserved_like_qty: Mapped[float] = mapped_column(Float, default=0)


class InboundDelivery(TimestampMixin, Base):
    __tablename__ = "inbound_deliveries"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("inbound")
    )
    source_batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("upload_batches.id"), nullable=True
    )
    external_ref: Mapped[str] = mapped_column(String(255), unique=True)
    sku_id: Mapped[str] = mapped_column(ForeignKey("skus.id"), index=True)
    container_ref: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    quantity: Mapped[float] = mapped_column(Float)
    free_stock_after_allocation_qty: Mapped[float] = mapped_column(Float, default=0)
    client_order_qty: Mapped[float] = mapped_column(Float, default=0)
    eta_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(64), index=True)
    sheet_status: Mapped[str | None] = mapped_column(String(120), nullable=True)
    affected_client_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    reserve_impact_qty: Mapped[float] = mapped_column(Float, default=0)
    client_allocations: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    raw_payload: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )


class ReserveRun(TimestampMixin, Base):
    __tablename__ = "reserve_runs"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("run")
    )
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="completed")
    scope_type: Mapped[str] = mapped_column(String(64), default="portfolio")
    grouping_mode: Mapped[str] = mapped_column(String(64), default="client_sku")
    reserve_months: Mapped[int] = mapped_column(Integer)
    safety_factor: Mapped[float] = mapped_column(Float)
    demand_basis: Mapped[str] = mapped_column(String(64))
    demand_strategy: Mapped[str] = mapped_column(String(64), default="weighted_recent_average")
    include_inbound: Mapped[bool] = mapped_column(Boolean, default=True)
    inbound_statuses: Mapped[list[str]] = mapped_column(JSON, default=list)
    as_of_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    horizon_days: Mapped[int] = mapped_column(Integer, default=60)
    filters_payload: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    summary_payload: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    row_count: Mapped[int] = mapped_column(Integer, default=0)


class ReserveRow(TimestampMixin, Base):
    __tablename__ = "reserve_rows"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("rrow")
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("reserve_runs.id", ondelete="CASCADE"), index=True
    )
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), index=True)
    sku_id: Mapped[str] = mapped_column(ForeignKey("skus.id"), index=True)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    policy_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    client_priority_level: Mapped[int] = mapped_column(Integer, default=0)
    sales_qty_1m: Mapped[float] = mapped_column(Float, default=0)
    sales_qty_3m: Mapped[float] = mapped_column(Float, default=0)
    sales_qty_6m: Mapped[float] = mapped_column(Float, default=0)
    history_months_available: Mapped[int] = mapped_column(Integer, default=0)
    demand_basis: Mapped[str] = mapped_column(String(64))
    demand_basis_type: Mapped[str] = mapped_column(String(64), default="insufficient_history")
    fallback_level: Mapped[str] = mapped_column(String(64))
    basis_window_used: Mapped[str] = mapped_column(String(64), default="none")
    last_sale_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    trend_signal: Mapped[str] = mapped_column(String(32), default="flat")
    demand_stability: Mapped[float] = mapped_column(Float, default=0)
    avg_sales_3m: Mapped[float] = mapped_column(Float, default=0)
    avg_sales_6m: Mapped[float] = mapped_column(Float, default=0)
    demand_per_month: Mapped[float] = mapped_column(Float, default=0)
    reserve_months: Mapped[int] = mapped_column(Integer)
    target_reserve_qty: Mapped[float] = mapped_column(Float, default=0)
    free_stock_qty: Mapped[float] = mapped_column(Float, default=0)
    inbound_in_horizon_qty: Mapped[float] = mapped_column(Float, default=0)
    available_qty: Mapped[float] = mapped_column(Float, default=0)
    shortage_qty: Mapped[float] = mapped_column(Float, default=0)
    coverage_months: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(32), index=True)
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation_payload: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )


class QualityIssue(TimestampMixin, Base):
    __tablename__ = "quality_issues"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("qiss")
    )
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    file_id: Mapped[str | None] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    issue_type: Mapped[str] = mapped_column(String(128), index=True)
    severity: Mapped[str] = mapped_column(String(32), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_ref: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    source_label: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="open")


class JobRun(TimestampMixin, Base):
    __tablename__ = "job_runs"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("job")
    )
    job_name: Mapped[str] = mapped_column(String(128), index=True)
    queue_name: Mapped[str] = mapped_column(String(128), default="default")
    status: Mapped[str] = mapped_column(String(32), default="queued")
    payload: Mapped[dict[str, object]] = mapped_column(MutableDict.as_mutable(JSON), default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class ManagementReportImport(TimestampMixin, Base):
    __tablename__ = "management_report_imports"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("mrimp")
    )
    file_name: Mapped[str] = mapped_column(String(255))
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    checksum: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    report_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    sheet_count: Mapped[int] = mapped_column(Integer, default=0)
    raw_row_count: Mapped[int] = mapped_column(Integer, default=0)
    metric_count: Mapped[int] = mapped_column(Integer, default=0)
    imported_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    metadata_payload: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    rows: Mapped[list["ManagementReportRow"]] = relationship(
        back_populates="report_import", cascade="all, delete-orphan"
    )
    metrics: Mapped[list["ManagementReportMetric"]] = relationship(
        back_populates="report_import", cascade="all, delete-orphan"
    )


class ManagementReportRow(TimestampMixin, Base):
    __tablename__ = "management_report_rows"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("mrrow")
    )
    import_id: Mapped[str] = mapped_column(
        ForeignKey("management_report_imports.id", ondelete="CASCADE"), index=True
    )
    sheet_name: Mapped[str] = mapped_column(String(255), index=True)
    row_index: Mapped[int] = mapped_column(Integer)
    is_header: Mapped[bool] = mapped_column(Boolean, default=False)
    parsed_metric_count: Mapped[int] = mapped_column(Integer, default=0)
    raw_values: Mapped[list[object]] = mapped_column(MutableList.as_mutable(JSON), default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_import: Mapped[ManagementReportImport] = relationship(back_populates="rows")


class OrganizationUnit(TimestampMixin, Base):
    __tablename__ = "organization_units"
    __table_args__ = (UniqueConstraint("unit_type", "code", name="uq_organization_unit_type_code"),)

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("org")
    )
    unit_type: Mapped[str] = mapped_column(String(64), default="department", index=True)
    code: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    source_import_id: Mapped[str | None] = mapped_column(
        ForeignKey("management_report_imports.id"), nullable=True, index=True
    )
    metadata_payload: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )


class ManagementReportMetric(TimestampMixin, Base):
    __tablename__ = "management_report_metrics"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("mrm")
    )
    import_id: Mapped[str] = mapped_column(
        ForeignKey("management_report_imports.id", ondelete="CASCADE"), index=True
    )
    source_row_id: Mapped[str | None] = mapped_column(
        ForeignKey("management_report_rows.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sheet_name: Mapped[str] = mapped_column(String(255), index=True)
    row_index: Mapped[int] = mapped_column(Integer)
    dimension_type: Mapped[str] = mapped_column(String(80), index=True)
    dimension_code: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    dimension_name: Mapped[str] = mapped_column(String(255), index=True)
    metric_name: Mapped[str] = mapped_column(String(120), index=True)
    metric_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    metric_value: Mapped[float] = mapped_column(Numeric(18, 4))
    metric_unit: Mapped[str] = mapped_column(String(32), default="rub")
    raw_payload: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    report_import: Mapped[ManagementReportImport] = relationship(back_populates="metrics")


class ExportJob(TimestampMixin, Base):
    __tablename__ = "export_jobs"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("exp")
    )
    requested_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    export_type: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    format: Mapped[str] = mapped_column(String(16), default="csv")
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    filters_payload: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    summary_payload: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    download_count: Mapped[int] = mapped_column(Integer, default=0)


class AssistantSession(TimestampMixin, Base):
    __tablename__ = "assistant_sessions"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("asess")
    )
    created_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), default="Новая сессия")
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    pinned_context: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    last_intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    preferred_mode: Mapped[str] = mapped_column(String(32), default="deterministic")
    provider: Mapped[str] = mapped_column(String(64), default="deterministic")
    latest_trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    messages: Mapped[list["AssistantMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class AssistantMessage(TimestampMixin, Base):
    __tablename__ = "assistant_messages"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("amsg")
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("assistant_sessions.id", ondelete="CASCADE"), index=True
    )
    created_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    role: Mapped[str] = mapped_column(String(16), index=True)
    message_text: Mapped[str] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="completed")
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    context_payload: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    response_payload: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSON), default=dict
    )
    source_refs: Mapped[list[dict[str, object]]] = mapped_column(
        MutableList.as_mutable(JSON), default=list
    )
    tool_calls: Mapped[list[dict[str, object]]] = mapped_column(
        MutableList.as_mutable(JSON), default=list
    )
    warnings: Mapped[list[dict[str, object]]] = mapped_column(
        MutableList.as_mutable(JSON), default=list
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    session: Mapped[AssistantSession] = relationship(back_populates="messages")


class SystemEvent(TimestampMixin, Base):
    __tablename__ = "system_events"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: generate_id("evt")
    )
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(40))
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
