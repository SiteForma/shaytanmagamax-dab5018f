from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.app.common.pagination import page_offset
from apps.api.app.core.request_context import get_request_id, get_trace_id
from apps.api.app.db.models import SystemEvent
from apps.api.app.modules.audit.schemas import AuditEventResponse

logger = logging.getLogger(__name__)


def record_audit_event(
    db: Session,
    *,
    actor_user_id: str | None,
    action: str,
    target_type: str,
    target_id: str,
    status: str = "success",
    context: dict[str, object] | None = None,
    trace_id: str | None = None,
) -> SystemEvent:
    payload = {
        "status": status,
        "request_id": get_request_id(),
        "trace_id": trace_id or get_trace_id(),
        **(context or {}),
    }
    event = SystemEvent(
        event_type=action,
        entity_type=target_type,
        entity_id=target_id,
        actor_user_id=actor_user_id,
        payload=payload,
    )
    db.add(event)
    db.flush()
    logger.info(
        "audit_event",
        extra={
            "audit_action": action,
            "target_type": target_type,
            "target_id": target_id,
            "actor_user_id": actor_user_id,
            "audit_status": status,
        },
    )
    return event


def serialize_audit_event(event: SystemEvent) -> AuditEventResponse:
    payload = dict(event.payload or {})
    return AuditEventResponse(
        id=event.id,
        action=event.event_type,
        target_type=event.entity_type,
        target_id=event.entity_id,
        actor_user_id=event.actor_user_id,
        status=str(payload.get("status", "success")),
        request_id=payload.get("request_id"),  # type: ignore[arg-type]
        trace_id=payload.get("trace_id"),  # type: ignore[arg-type]
        context={key: value for key, value in payload.items() if key not in {"status", "request_id", "trace_id"}},
        created_at=event.created_at.isoformat(),
    )


def list_audit_events(
    db: Session,
    *,
    action: str | None = None,
    target_type: str | None = None,
) -> list[AuditEventResponse]:
    stmt = select(SystemEvent)
    if action:
        stmt = stmt.where(SystemEvent.event_type == action)
    if target_type:
        stmt = stmt.where(SystemEvent.entity_type == target_type)
    events = db.scalars(stmt.order_by(SystemEvent.created_at.desc())).all()
    return [serialize_audit_event(event) for event in events]


def list_audit_events_page(
    db: Session,
    *,
    action: str | None = None,
    target_type: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[AuditEventResponse], int]:
    stmt = select(SystemEvent)
    if action:
        stmt = stmt.where(SystemEvent.event_type == action)
    if target_type:
        stmt = stmt.where(SystemEvent.entity_type == target_type)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    events = db.scalars(
        stmt.order_by(SystemEvent.created_at.desc())
        .offset(page_offset(page, page_size))
        .limit(page_size)
    ).all()
    return ([serialize_audit_event(event) for event in events], int(total))
