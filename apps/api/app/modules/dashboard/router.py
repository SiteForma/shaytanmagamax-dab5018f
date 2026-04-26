from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.app.db.session import get_db
from apps.api.app.modules.dashboard.schemas import (
    DashboardOverviewResponse,
    DashboardSummaryResponse,
    ExposedClientResponse,
    InboundShortagePoint,
    TopRiskSkuResponse,
)
from apps.api.app.modules.dashboard.service import (
    get_coverage_distribution,
    get_dashboard_overview,
    get_exposed_clients,
    get_freshness,
    get_inbound_vs_shortage,
    get_summary,
    get_top_risk_skus,
)
from apps.api.app.modules.reserve.schemas import CoverageBucketResponse, FreshnessPanelResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_summary_route(db: Session = Depends(get_db)) -> DashboardSummaryResponse:
    return get_summary(db)


@router.get("/top-risk-skus", response_model=list[TopRiskSkuResponse])
def get_top_risk_skus_route(db: Session = Depends(get_db)) -> list[TopRiskSkuResponse]:
    return get_top_risk_skus(db)


@router.get("/exposed-clients", response_model=list[ExposedClientResponse])
def get_exposed_clients_route(db: Session = Depends(get_db)) -> list[ExposedClientResponse]:
    return get_exposed_clients(db)


@router.get("/coverage-distribution", response_model=list[CoverageBucketResponse])
def get_coverage_distribution_route(db: Session = Depends(get_db)) -> list[CoverageBucketResponse]:
    return get_coverage_distribution(db)


@router.get("/inbound-vs-shortage", response_model=list[InboundShortagePoint])
def get_inbound_vs_shortage_route(db: Session = Depends(get_db)) -> list[InboundShortagePoint]:
    return get_inbound_vs_shortage(db)


@router.get("/freshness", response_model=FreshnessPanelResponse)
def get_freshness_route(db: Session = Depends(get_db)) -> FreshnessPanelResponse:
    return get_freshness(db)


@router.get("/overview", response_model=DashboardOverviewResponse)
def get_dashboard_overview_route(db: Session = Depends(get_db)) -> DashboardOverviewResponse:
    return get_dashboard_overview(db)
