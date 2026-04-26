from __future__ import annotations

from apps.api.app.common.schemas import ORMModel, PaginatedResponse


class AuditEventResponse(ORMModel):
    id: str
    action: str
    target_type: str
    target_id: str
    actor_user_id: str | None = None
    status: str
    request_id: str | None = None
    trace_id: str | None = None
    context: dict[str, object]
    created_at: str


class AuditEventListResponse(PaginatedResponse[AuditEventResponse]):
    pass
