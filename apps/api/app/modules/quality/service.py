from __future__ import annotations

from sqlalchemy import asc, case, desc, func, or_, select
from sqlalchemy.orm import Session

from apps.api.app.common.pagination import page_offset
from apps.api.app.db.models import QualityIssue
from apps.api.app.modules.quality.schemas import QualityIssueResponse


def _serialize_quality_issue(issue: QualityIssue) -> QualityIssueResponse:
    return QualityIssueResponse(
        id=issue.id,
        type=issue.issue_type,
        severity=issue.severity,
        entity=issue.entity_ref,
        description=issue.description,
        detected_at=issue.detected_at.isoformat(),
        source=issue.source_label,
    )


def _quality_issues_stmt(
    severity: str | None = None,
    issue_type: str | None = None,
    search: str | None = None,
    sort_by: str = "detected_at",
    sort_dir: str = "desc",
):
    stmt = select(QualityIssue)
    if severity:
        stmt = stmt.where(QualityIssue.severity == severity)
    if issue_type:
        stmt = stmt.where(QualityIssue.issue_type == issue_type)
    if search:
        needle = search.lower()
        pattern = f"%{needle}%"
        stmt = stmt.where(
            or_(
                func.lower(QualityIssue.entity_ref).like(pattern),
                func.lower(QualityIssue.description).like(pattern),
                func.lower(QualityIssue.source_label).like(pattern),
            )
        )
    severity_rank = {
        "critical": 4,
        "error": 3,
        "high": 3,
        "warning": 2,
        "medium": 2,
        "info": 1,
        "low": 1,
    }
    severity_order = case(
        *[(QualityIssue.severity == name, rank) for name, rank in severity_rank.items()],
        else_=0,
    )
    sorters: dict[str, object] = {
        "detected_at": QualityIssue.detected_at,
        "severity": severity_order,
        "type": QualityIssue.issue_type,
        "entity": QualityIssue.entity_ref,
        "source": QualityIssue.source_label,
    }
    column = sorters.get(sort_by, QualityIssue.detected_at)
    order_fn = desc if sort_dir == "desc" else asc
    return stmt.order_by(order_fn(column))


def list_quality_issues(
    db: Session,
    severity: str | None = None,
    issue_type: str | None = None,
    search: str | None = None,
    sort_by: str = "detected_at",
    sort_dir: str = "desc",
) -> list[QualityIssueResponse]:
    stmt = _quality_issues_stmt(
        severity=severity,
        issue_type=issue_type,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return [_serialize_quality_issue(issue) for issue in db.scalars(stmt).all()]


def list_quality_issues_page(
    db: Session,
    *,
    severity: str | None = None,
    issue_type: str | None = None,
    search: str | None = None,
    sort_by: str = "detected_at",
    sort_dir: str = "desc",
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[QualityIssueResponse], int]:
    stmt = _quality_issues_stmt(
        severity=severity,
        issue_type=issue_type,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.scalars(stmt.offset(page_offset(page, page_size)).limit(page_size)).all()
    return ([_serialize_quality_issue(issue) for issue in rows], int(total))
