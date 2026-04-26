from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.app.db.session import get_db
from apps.api.app.modules.reports.schemas import (
    ManagementReportImportResponse,
    ManagementReportMetricResponse,
    ManagementReportRowResponse,
    ManagementReportSummaryResponse,
    OrganizationUnitResponse,
)
from apps.api.app.modules.reports.service import (
    get_management_report_summary,
    list_management_report_imports,
    list_management_report_metrics,
    list_management_report_rows,
    list_organization_units,
)

router = APIRouter(prefix="/reports/management", tags=["reports"])


@router.get("/imports", response_model=list[ManagementReportImportResponse])
def list_imports_route(db: Session = Depends(get_db)) -> list[ManagementReportImportResponse]:
    return list_management_report_imports(db)


@router.get("/summary", response_model=ManagementReportSummaryResponse)
def get_summary_route(db: Session = Depends(get_db)) -> ManagementReportSummaryResponse:
    return get_management_report_summary(db)


@router.get("/metrics", response_model=list[ManagementReportMetricResponse])
def list_metrics_route(
    import_id: str | None = None,
    sheet_name: str | None = Query(default=None, alias="sheetName"),
    dimension_type: str | None = Query(default=None, alias="dimensionType"),
    metric_name: str | None = Query(default=None, alias="metricName"),
    metric_year: int | None = Query(default=None, alias="metricYear"),
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[ManagementReportMetricResponse]:
    return list_management_report_metrics(
        db,
        import_id=import_id,
        sheet_name=sheet_name,
        dimension_type=dimension_type,
        metric_name=metric_name,
        metric_year=metric_year,
        search=search,
        limit=limit,
    )


@router.get("/rows", response_model=list[ManagementReportRowResponse])
def list_rows_route(
    import_id: str | None = None,
    sheet_name: str | None = Query(default=None, alias="sheetName"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[ManagementReportRowResponse]:
    return list_management_report_rows(
        db,
        import_id=import_id,
        sheet_name=sheet_name,
        limit=limit,
    )


@router.get("/organization-units", response_model=list[OrganizationUnitResponse])
def list_organization_units_route(
    import_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[OrganizationUnitResponse]:
    return list_organization_units(db, import_id=import_id)
