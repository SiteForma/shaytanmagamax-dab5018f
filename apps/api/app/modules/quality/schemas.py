from __future__ import annotations

from apps.api.app.common.schemas import ORMModel, PaginatedResponse


class QualityIssueResponse(ORMModel):
    id: str
    type: str
    severity: str
    entity: str
    description: str
    detected_at: str
    source: str


class QualityIssueListResponse(PaginatedResponse[QualityIssueResponse]):
    pass
