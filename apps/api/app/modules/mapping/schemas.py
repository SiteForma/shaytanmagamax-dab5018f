from __future__ import annotations

from typing import Literal

from pydantic import Field

from apps.api.app.common.schemas import ORMModel


class MappingFieldResponse(ORMModel):
    source: str
    canonical: str
    confidence: float
    status: Literal["ok", "review", "missing"]
    sample: str | None = None
    candidates: list[str] = Field(default_factory=list)
    required: bool = False


class MappingStateResponse(ORMModel):
    source_type: str
    canonical_fields: list[str]
    required_fields: list[str]
    supports_apply: bool
    template_id: str | None = None
    suggestions: list[MappingFieldResponse]
    active_mapping: dict[str, str]


class MappingUpdateRequest(ORMModel):
    mappings: dict[str, str]
    template_id: str | None = None


class MappingTemplateResponse(ORMModel):
    id: str
    name: str
    source_type: str
    version: int
    is_default: bool
    is_active: bool
    created_by_id: str | None = None
    required_fields: list[str]
    transformation_hints: dict[str, object]
    mappings: dict[str, str]
    created_at: str
    updated_at: str


class MappingTemplateCreateRequest(ORMModel):
    name: str
    source_type: str
    mappings: dict[str, str]
    required_fields: list[str] = Field(default_factory=list)
    transformation_hints: dict[str, object] = Field(default_factory=dict)
    is_default: bool = False
    is_active: bool = True


class MappingTemplateUpdateRequest(ORMModel):
    name: str | None = None
    mappings: dict[str, str] | None = None
    required_fields: list[str] | None = None
    transformation_hints: dict[str, object] | None = None
    is_default: bool | None = None
    is_active: bool | None = None


class ApplyTemplateRequest(ORMModel):
    file_id: str


class AliasResponse(ORMModel):
    id: str
    alias: str
    entity_id: str
    entity_code: str
    entity_name: str
    created_at: str


class AliasCreateRequest(ORMModel):
    alias: str
    entity_id: str | None = None
    entity_code: str | None = None
