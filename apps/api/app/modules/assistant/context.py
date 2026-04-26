from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from apps.api.app.modules.assistant.domain import (
    AssistantContextBundle,
    AssistantResolvedContext,
    AssistantRoute,
    AssistantWarningData,
)
from apps.api.app.modules.assistant.schemas import AssistantPinnedContext
from apps.api.app.modules.dashboard.service import get_freshness


def build_context_bundle(
    db: Session,
    *,
    route: AssistantRoute,
    pinned_context: AssistantPinnedContext | None,
) -> AssistantContextBundle:
    normalized = (pinned_context or AssistantPinnedContext()).normalized()
    warnings = list(route.warnings)

    selected_client_id = route.extracted_client_id or normalized.selected_client_id
    selected_sku_id = (
        route.extracted_sku_ids[0] if route.extracted_sku_ids else None
    ) or normalized.selected_sku_id
    selected_category_id = route.extracted_category_id or normalized.selected_category_id
    selected_upload_ids = route.extracted_upload_ids or list(normalized.selected_upload_ids)
    selected_reserve_run_id = normalized.selected_reserve_run_id

    if (
        route.extracted_client_id
        and normalized.selected_client_id
        and route.extracted_client_id != normalized.selected_client_id
    ):
        warnings.append(
            AssistantWarningData(
                code="conflicting_pinned_client",
                message="Вопрос указывает на другого клиента, pinned context по клиенту переопределён вопросом.",
            )
        )
    if (
        route.extracted_sku_ids
        and normalized.selected_sku_id
        and route.extracted_sku_ids[0] != normalized.selected_sku_id
    ):
        warnings.append(
            AssistantWarningData(
                code="conflicting_pinned_sku",
                message="Вопрос указывает на другой SKU, pinned context по SKU переопределён вопросом.",
            )
        )

    freshness = get_freshness(db)
    freshness_raw = freshness.last_reserve_run_at or freshness.last_upload_at
    freshness_at = datetime.fromisoformat(freshness_raw) if freshness_raw else None
    return AssistantContextBundle(
        context=AssistantResolvedContext(
            selected_client_id=selected_client_id,
            selected_sku_id=selected_sku_id,
            selected_upload_ids=selected_upload_ids,
            selected_reserve_run_id=selected_reserve_run_id,
            selected_category_id=selected_category_id,
        ),
        route=route,
        warnings=warnings,
        data_freshness_at=freshness_at,
    )
