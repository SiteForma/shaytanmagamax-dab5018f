from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ErrorEnvelope(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: dict[str, object] | None = None


class PaginationMeta(BaseModel):
    page: int = 1
    page_size: int = Field(default=25, alias="pageSize")
    total: int


class PaginatedResponse(ORMModel, Generic[T]):
    items: list[T]
    meta: PaginationMeta


class AuditStamp(ORMModel):
    created_at: datetime
    updated_at: datetime | None = None
