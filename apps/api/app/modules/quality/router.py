from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.app.common.pagination import paginated_response
from apps.api.app.common.schemas import PaginatedResponse
from apps.api.app.db.session import get_db
from apps.api.app.modules.quality.schemas import QualityIssueListResponse, QualityIssueResponse
from apps.api.app.modules.quality.service import list_quality_issues_page

router = APIRouter(prefix="/quality", tags=["quality"])


@router.get("/issues", response_model=PaginatedResponse[QualityIssueResponse])
def list_quality_issues_route(
    severity: str | None = Query(default=None),
    type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    sort_by: str = Query(default="detected_at"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
) -> QualityIssueListResponse:
    items, total = list_quality_issues_page(
        db,
        severity=severity,
        issue_type=type,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )
    return QualityIssueListResponse.model_validate(
        paginated_response(items, total=total, page=page, page_size=page_size)
    )
