from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from apps.api.app.common.utils import normalize_header
from apps.api.app.core.errors import DomainError
from apps.api.app.db.models import (
    Client,
    ClientAlias,
    MappingRule,
    MappingTemplate,
    Sku,
    SkuAlias,
    UploadBatch,
)
from apps.api.app.modules.mapping.schemas import (
    AliasCreateRequest,
    AliasResponse,
    MappingFieldResponse,
    MappingTemplateCreateRequest,
    MappingTemplateResponse,
    MappingTemplateUpdateRequest,
)


def _transliterate_cyrillic(value: str) -> str:
    table = str.maketrans(
        {
            "а": "a",
            "б": "b",
            "в": "v",
            "г": "g",
            "д": "d",
            "е": "e",
            "ё": "e",
            "ж": "zh",
            "з": "z",
            "и": "i",
            "й": "y",
            "к": "k",
            "л": "l",
            "м": "m",
            "н": "n",
            "о": "o",
            "п": "p",
            "р": "r",
            "с": "s",
            "т": "t",
            "у": "u",
            "ф": "f",
            "х": "h",
            "ц": "ts",
            "ч": "ch",
            "ш": "sh",
            "щ": "sch",
            "ъ": "",
            "ы": "y",
            "ь": "",
            "э": "e",
            "ю": "yu",
            "я": "ya",
        }
    )
    return value.lower().translate(table)


def normalize_mapping_token(value: str) -> str:
    ascii_value = _transliterate_cyrillic(value)
    return normalize_header(ascii_value)


def _token_variants(value: str) -> set[str]:
    direct = normalize_header(value)
    transliterated = normalize_mapping_token(value)
    return {token for token in {direct, transliterated} if token}


@dataclass(frozen=True, slots=True)
class SourceTypeSpec:
    canonical_fields: tuple[str, ...]
    required_fields: tuple[str, ...]
    synonyms: dict[str, tuple[str, ...]]
    supports_apply: bool = True


SOURCE_TYPE_SPECS: dict[str, SourceTypeSpec] = {
    "sales": SourceTypeSpec(
        canonical_fields=(
            "period_date",
            "year",
            "month",
            "client_name",
            "sku_code",
            "product_name",
            "quantity",
            "revenue",
            "category_name",
            "source_row_id",
        ),
        required_fields=("period_date", "client_name", "sku_code", "quantity"),
        synonyms={
            "period_date": ("period", "date", "month", "period date", "период", "дата"),
            "year": ("year", "год"),
            "month": ("month", "месяц"),
            "client_name": (
                "client",
                "customer",
                "network",
                "сеть",
                "клиент",
                "контрагент",
            ),
            "sku_code": (
                "sku",
                "article",
                "артикул",
                "код товара",
                "товарный код",
            ),
            "product_name": ("product", "product name", "наименование", "товар"),
            "quantity": ("qty", "quantity", "кол-во", "количество", "объем"),
            "revenue": ("revenue", "sales amount", "выручка", "сумма"),
            "category_name": ("category", "категория"),
            "source_row_id": ("row id", "source row", "строка"),
        },
    ),
    "stock": SourceTypeSpec(
        canonical_fields=(
            "snapshot_date",
            "sku_code",
            "product_name",
            "stock_total",
            "stock_free",
            "warehouse_name",
        ),
        required_fields=("snapshot_date", "sku_code", "stock_free"),
        synonyms={
            "snapshot_date": ("snapshot date", "date", "дата", "дата снимка"),
            "sku_code": ("sku", "article", "артикул", "код товара"),
            "product_name": ("product", "product name", "наименование"),
            "stock_total": ("stock total", "total stock", "остаток", "общий остаток"),
            "stock_free": (
                "stock free",
                "free stock",
                "free",
                "свободный остаток",
                "остаток свободный",
            ),
            "warehouse_name": ("warehouse", "warehouse code", "склад"),
        },
    ),
    "diy_clients": SourceTypeSpec(
        canonical_fields=(
            "client_name",
            "reserve_months",
            "safety_factor",
            "priority",
            "active",
            "region",
        ),
        required_fields=("client_name", "reserve_months", "safety_factor"),
        synonyms={
            "client_name": ("client", "customer", "сеть", "клиент"),
            "reserve_months": ("reserve months", "months", "горизонт", "резерв месяцев"),
            "safety_factor": ("safety factor", "safety", "коэффициент", "запас"),
            "priority": ("priority", "приоритет"),
            "active": ("active", "is active", "активен"),
            "region": ("region", "регион"),
        },
    ),
    "category_structure": SourceTypeSpec(
        canonical_fields=(
            "category_level_1",
            "category_level_2",
            "category_level_3",
            "sku_code",
            "product_name",
        ),
        required_fields=("sku_code",),
        synonyms={
            "category_level_1": ("category l1", "level 1", "категория 1", "уровень 1"),
            "category_level_2": ("category l2", "level 2", "категория 2", "уровень 2"),
            "category_level_3": ("category l3", "level 3", "категория 3", "уровень 3"),
            "sku_code": ("sku", "article", "артикул"),
            "product_name": ("product", "наименование", "товар"),
        },
    ),
    "inbound": SourceTypeSpec(
        canonical_fields=("sku_code", "product_name", "eta_date", "quantity", "status"),
        required_fields=("sku_code", "eta_date", "quantity", "status"),
        synonyms={
            "sku_code": ("sku", "article", "артикул"),
            "product_name": ("product", "наименование"),
            "eta_date": ("eta", "eta date", "arrival", "поставка", "дата поставки"),
            "quantity": ("qty", "quantity", "кол-во", "количество"),
            "status": ("status", "статус"),
        },
    ),
    "raw_report": SourceTypeSpec(
        canonical_fields=("source_row_id", "raw_value"),
        required_fields=(),
        synonyms={},
        supports_apply=False,
    ),
}


def list_supported_source_types() -> list[str]:
    return list(SOURCE_TYPE_SPECS)


def get_source_type_spec(source_type: str) -> SourceTypeSpec:
    spec = SOURCE_TYPE_SPECS.get(source_type)
    if spec is None:
        raise DomainError(code="unsupported_source_type", message=f"Неподдерживаемый тип источника: {source_type}")
    return spec


def list_canonical_fields(source_type: str) -> list[str]:
    return list(get_source_type_spec(source_type).canonical_fields)


def list_required_fields(source_type: str) -> list[str]:
    return list(get_source_type_spec(source_type).required_fields)


def source_supports_apply(source_type: str) -> bool:
    return get_source_type_spec(source_type).supports_apply


def detect_source_type(columns: list[str], explicit_source_type: str | None) -> str:
    if explicit_source_type:
        return explicit_source_type
    best_source_type = "raw_report"
    best_score = -1.0
    for source_type, _spec in SOURCE_TYPE_SPECS.items():
        score = 0.0
        for column in columns:
            _, confidence, _ = suggest_canonical_field(str(column), source_type)
            score += confidence
        if score > best_score:
            best_score = score
            best_source_type = source_type
    return best_source_type


def _canonical_tokens(source_type: str, canonical_field: str) -> set[str]:
    spec = get_source_type_spec(source_type)
    tokens = _token_variants(canonical_field)
    for synonym in spec.synonyms.get(canonical_field, ()):
        tokens.update(_token_variants(synonym))
    return tokens


def _template_token_map(template_mapping: dict[str, str]) -> dict[str, str]:
    token_map: dict[str, str] = {}
    for source_header, canonical_field in template_mapping.items():
        for token in _token_variants(source_header):
            token_map[token] = canonical_field
    return token_map


def _score_token_match(header_tokens: set[str], candidate_tokens: set[str]) -> float:
    best = 0.0
    for header_token in header_tokens:
        for candidate_token in candidate_tokens:
            if header_token == candidate_token:
                return 0.96
            if header_token in candidate_token or candidate_token in header_token:
                best = max(best, 0.82)
            similarity = SequenceMatcher(None, header_token, candidate_token).ratio()
            best = max(best, round(similarity * 0.78, 2))
    return best


def suggest_canonical_field(
    source_header: str, source_type: str, template_mapping: dict[str, str] | None = None
) -> tuple[str, float, list[str]]:
    header_tokens = _token_variants(source_header)
    template_tokens = _template_token_map(template_mapping or {})
    ranked: list[tuple[str, float]] = []
    for canonical_field in list_canonical_fields(source_type):
        score = 0.0
        canonical_exact_tokens = _token_variants(canonical_field)
        if header_tokens & canonical_exact_tokens:
            score = 1.0
        if any(template_tokens.get(token) == canonical_field for token in header_tokens):
            score = max(score, 0.99)
        score = max(score, _score_token_match(header_tokens, _canonical_tokens(source_type, canonical_field)))
        ranked.append((canonical_field, round(score, 2)))
    ranked.sort(key=lambda item: item[1], reverse=True)
    top_candidates = [candidate for candidate, score in ranked[:3] if score >= 0.35]
    best_canonical, best_score = ranked[0]
    if best_score < 0.62:
        return "", 0.0, top_candidates
    return best_canonical, best_score, top_candidates


def build_mapping_fields(
    frame: pd.DataFrame,
    source_type: str,
    template_mapping: dict[str, str] | None = None,
) -> list[MappingFieldResponse]:
    required_fields = set(list_required_fields(source_type))
    suggestions: list[MappingFieldResponse] = []
    for column in frame.columns:
        canonical, confidence, candidates = suggest_canonical_field(
            str(column), source_type, template_mapping=template_mapping
        )
        status: MappingFieldResponse.__annotations__["status"]
        if not canonical:
            status = "missing"
        elif confidence >= 0.9:
            status = "ok"
        else:
            status = "review"
        sample_value = None if frame.empty else frame.iloc[0][column]
        suggestions.append(
            MappingFieldResponse(
                source=str(column),
                canonical=canonical,
                confidence=confidence,
                status=status,
                sample=None if sample_value is None else str(sample_value),
                candidates=candidates,
                required=canonical in required_fields if canonical else False,
            )
        )
    return suggestions


def get_default_mapping_fields(
    db: Session, batch_id: str | None = None
) -> list[MappingFieldResponse]:
    if batch_id:
        batch = db.get(UploadBatch, batch_id)
        if batch and batch.mapping_payload.get("suggestions"):
            return [
                MappingFieldResponse(**payload) for payload in batch.mapping_payload["suggestions"]
            ]

    latest_batch = db.scalars(select(UploadBatch).order_by(UploadBatch.created_at.desc())).first()
    if latest_batch and latest_batch.mapping_payload.get("suggestions"):
        return [
            MappingFieldResponse(**payload)
            for payload in latest_batch.mapping_payload["suggestions"]
        ]

    template = (
        db.scalars(
            select(MappingTemplate)
            .options(selectinload(MappingTemplate.rules))
            .where(MappingTemplate.is_default.is_(True))
            .order_by(MappingTemplate.updated_at.desc())
        )
        .unique()
        .first()
    )
    if template is None:
        return []
    return [
        MappingFieldResponse(
            source=rule.source_header,
            canonical=rule.canonical_field,
            confidence=rule.confidence,
            status="ok",
            required=rule.canonical_field in template.required_fields,
        )
        for rule in template.rules
    ]


def _template_to_response(template: MappingTemplate) -> MappingTemplateResponse:
    return MappingTemplateResponse(
        id=template.id,
        name=template.name,
        source_type=template.source_type,
        version=template.version,
        is_default=template.is_default,
        is_active=template.is_active,
        created_by_id=template.created_by_id,
        required_fields=list(template.required_fields),
        transformation_hints=dict(template.transformation_hints),
        mappings={rule.source_header: rule.canonical_field for rule in template.rules},
        created_at=template.created_at.isoformat(),
        updated_at=template.updated_at.isoformat(),
    )


def list_mapping_templates(
    db: Session, source_type: str | None = None
) -> list[MappingTemplateResponse]:
    query = select(MappingTemplate).options(selectinload(MappingTemplate.rules))
    if source_type:
        query = query.where(MappingTemplate.source_type == source_type)
    templates = db.scalars(query.order_by(MappingTemplate.updated_at.desc())).unique().all()
    return [_template_to_response(template) for template in templates]


def get_mapping_template(db: Session, template_id: str) -> MappingTemplate:
    template = (
        db.scalars(
            select(MappingTemplate)
            .options(selectinload(MappingTemplate.rules))
            .where(MappingTemplate.id == template_id)
        )
        .unique()
        .first()
    )
    if template is None:
        raise DomainError(code="mapping_template_not_found", message="Шаблон сопоставления не найден")
    return template


def create_mapping_template(
    db: Session,
    payload: MappingTemplateCreateRequest,
    created_by_id: str | None = None,
) -> MappingTemplateResponse:
    template = MappingTemplate(
        name=payload.name,
        source_type=payload.source_type,
        version=1,
        is_default=payload.is_default,
        is_active=payload.is_active,
        created_by_id=created_by_id,
        required_fields=payload.required_fields or list_required_fields(payload.source_type),
        transformation_hints=payload.transformation_hints,
    )
    db.add(template)
    db.flush()
    for source_header, canonical_field in payload.mappings.items():
        db.add(
            MappingRule(
                template_id=template.id,
                source_header=source_header,
                canonical_field=canonical_field,
                confidence=0.99,
            )
        )
    db.commit()
    return _template_to_response(get_mapping_template(db, template.id))


def update_mapping_template(
    db: Session, template_id: str, payload: MappingTemplateUpdateRequest
) -> MappingTemplateResponse:
    template = get_mapping_template(db, template_id)
    if payload.name is not None:
        template.name = payload.name
    if payload.required_fields is not None:
        template.required_fields = payload.required_fields
    if payload.transformation_hints is not None:
        template.transformation_hints = payload.transformation_hints
    if payload.is_default is not None:
        template.is_default = payload.is_default
    if payload.is_active is not None:
        template.is_active = payload.is_active
    if payload.mappings is not None:
        template.version += 1
        template.rules.clear()
        db.flush()
        for source_header, canonical_field in payload.mappings.items():
            template.rules.append(
                MappingRule(
                    source_header=source_header,
                    canonical_field=canonical_field,
                    confidence=0.99,
                )
            )
    db.commit()
    return _template_to_response(get_mapping_template(db, template.id))


def list_sku_aliases(db: Session) -> list[AliasResponse]:
    aliases = db.scalars(select(SkuAlias).order_by(SkuAlias.created_at.desc())).all()
    result: list[AliasResponse] = []
    for alias in aliases:
        sku = db.get(Sku, alias.sku_id)
        if sku is None:
            continue
        result.append(
            AliasResponse(
                id=alias.id,
                alias=alias.alias,
                entity_id=sku.id,
                entity_code=sku.article,
                entity_name=sku.name,
                created_at=alias.created_at.isoformat(),
            )
        )
    return result


def list_client_aliases(db: Session) -> list[AliasResponse]:
    aliases = db.scalars(select(ClientAlias).order_by(ClientAlias.created_at.desc())).all()
    result: list[AliasResponse] = []
    for alias in aliases:
        client = db.get(Client, alias.client_id)
        if client is None:
            continue
        result.append(
            AliasResponse(
                id=alias.id,
                alias=alias.alias,
                entity_id=client.id,
                entity_code=client.code,
                entity_name=client.name,
                created_at=alias.created_at.isoformat(),
            )
        )
    return result


def _resolve_sku_reference(db: Session, payload: AliasCreateRequest) -> Sku:
    if payload.entity_id:
        sku = db.get(Sku, payload.entity_id)
    elif payload.entity_code:
        sku = db.scalars(select(Sku).where(Sku.article == payload.entity_code)).first()
    else:
        sku = None
    if sku is None:
        raise DomainError(code="sku_not_found", message="SKU для алиаса не найден")
    return sku


def _resolve_client_reference(db: Session, payload: AliasCreateRequest) -> Client:
    if payload.entity_id:
        client = db.get(Client, payload.entity_id)
    elif payload.entity_code:
        client = db.scalars(select(Client).where(Client.code == payload.entity_code)).first()
    else:
        client = None
    if client is None:
        raise DomainError(code="client_not_found", message="Клиент для алиаса не найден")
    return client


def create_sku_alias(db: Session, payload: AliasCreateRequest) -> AliasResponse:
    sku = _resolve_sku_reference(db, payload)
    alias = SkuAlias(sku_id=sku.id, alias=payload.alias.strip())
    db.add(alias)
    db.commit()
    db.refresh(alias)
    return AliasResponse(
        id=alias.id,
        alias=alias.alias,
        entity_id=sku.id,
        entity_code=sku.article,
        entity_name=sku.name,
        created_at=alias.created_at.isoformat(),
    )


def create_client_alias(db: Session, payload: AliasCreateRequest) -> AliasResponse:
    client = _resolve_client_reference(db, payload)
    alias = ClientAlias(client_id=client.id, alias=payload.alias.strip())
    db.add(alias)
    db.commit()
    db.refresh(alias)
    return AliasResponse(
        id=alias.id,
        alias=alias.alias,
        entity_id=client.id,
        entity_code=client.code,
        entity_name=client.name,
        created_at=alias.created_at.isoformat(),
    )


def resolve_sku_by_code_or_alias(db: Session, value: str) -> Sku | None:
    direct = db.scalars(select(Sku).where(Sku.article == value)).first()
    if direct is not None:
        return direct
    aliases = db.scalars(select(SkuAlias)).all()
    for alias in aliases:
        if normalize_mapping_token(alias.alias) == normalize_mapping_token(value):
            return db.get(Sku, alias.sku_id)
    return None


def resolve_client_by_name_or_alias(db: Session, value: str) -> Client | None:
    direct = db.scalars(select(Client).where(Client.name == value)).first()
    if direct is not None:
        return direct
    aliases = db.scalars(select(ClientAlias)).all()
    for alias in aliases:
        if normalize_mapping_token(alias.alias) == normalize_mapping_token(value):
            return db.get(Client, alias.client_id)
    return None
