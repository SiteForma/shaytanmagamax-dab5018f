from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.app.api.dependencies import get_settings_dependency, require_capability
from apps.api.app.core.config import Settings
from apps.api.app.db.models import User
from apps.api.app.db.session import get_db
from apps.api.app.modules.audit.service import record_audit_event
from apps.api.app.modules.mapping.schemas import (
    AliasCreateRequest,
    AliasResponse,
    ApplyTemplateRequest,
    MappingFieldResponse,
    MappingTemplateCreateRequest,
    MappingTemplateResponse,
    MappingTemplateUpdateRequest,
)
from apps.api.app.modules.mapping.service import (
    create_client_alias,
    create_mapping_template,
    create_sku_alias,
    get_default_mapping_fields,
    list_client_aliases,
    list_mapping_templates,
    list_sku_aliases,
    update_mapping_template,
)
from apps.api.app.modules.uploads.schemas import UploadFileDetailResponse
from apps.api.app.modules.uploads.service import apply_mapping_template_to_upload

router = APIRouter(prefix="/mapping", tags=["mapping"])


@router.get("/suggestions", response_model=list[MappingFieldResponse])
def get_mapping_suggestions_route(
    batch_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[MappingFieldResponse]:
    return get_default_mapping_fields(db, batch_id=batch_id)


@router.get("/templates", response_model=list[MappingTemplateResponse])
def list_mapping_templates_route(
    source_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[MappingTemplateResponse]:
    return list_mapping_templates(db, source_type=source_type)


@router.post("/templates", response_model=MappingTemplateResponse)
def create_mapping_template_route(
    payload: MappingTemplateCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_capability("mapping", "write")),
) -> MappingTemplateResponse:
    template = create_mapping_template(db, payload, created_by_id=current_user.id)
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="mapping.template_created",
        target_type="mapping_template",
        target_id=template.id,
        context={"source_type": template.source_type, "name": template.name},
    )
    db.commit()
    return template


@router.patch("/templates/{template_id}", response_model=MappingTemplateResponse)
def update_mapping_template_route(
    template_id: str,
    payload: MappingTemplateUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_capability("mapping", "write")),
) -> MappingTemplateResponse:
    template = update_mapping_template(db, template_id, payload)
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="mapping.template_updated",
        target_type="mapping_template",
        target_id=template_id,
        context=payload.model_dump(mode="json", exclude_none=True),
    )
    db.commit()
    return template


@router.post("/templates/{template_id}/apply", response_model=UploadFileDetailResponse)
def apply_mapping_template_route(
    template_id: str,
    payload: ApplyTemplateRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    current_user: User = Depends(require_capability("mapping", "write")),
) -> UploadFileDetailResponse:
    detail = apply_mapping_template_to_upload(db, settings, payload.file_id, template_id)
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="mapping.template_applied",
        target_type="upload_file",
        target_id=payload.file_id,
        context={"template_id": template_id, "status": detail.file.status},
    )
    db.commit()
    return detail


@router.get("/aliases/skus", response_model=list[AliasResponse])
def list_sku_aliases_route(db: Session = Depends(get_db)) -> list[AliasResponse]:
    return list_sku_aliases(db)


@router.post("/aliases/skus", response_model=AliasResponse)
def create_sku_alias_route(
    payload: AliasCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_capability("mapping", "write")),
) -> AliasResponse:
    alias = create_sku_alias(db, payload)
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="mapping.sku_alias_created",
        target_type="sku_alias",
        target_id=alias.id,
        context={"alias": alias.alias, "entity_code": alias.entity_code, "entity_name": alias.entity_name},
    )
    db.commit()
    return alias


@router.get("/aliases/clients", response_model=list[AliasResponse])
def list_client_aliases_route(db: Session = Depends(get_db)) -> list[AliasResponse]:
    return list_client_aliases(db)


@router.post("/aliases/clients", response_model=AliasResponse)
def create_client_alias_route(
    payload: AliasCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_capability("mapping", "write")),
) -> AliasResponse:
    alias = create_client_alias(db, payload)
    record_audit_event(
        db,
        actor_user_id=current_user.id,
        action="mapping.client_alias_created",
        target_type="client_alias",
        target_id=alias.id,
        context={"alias": alias.alias, "entity_code": alias.entity_code, "entity_name": alias.entity_name},
    )
    db.commit()
    return alias
