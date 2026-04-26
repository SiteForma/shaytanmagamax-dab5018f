from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from apps.api.app.api.dependencies import (
    require_authenticated_rate_limit,
    require_capability,
    require_user,
)
from apps.api.app.modules.admin.router import router as admin_router
from apps.api.app.modules.assistant.router import router as assistant_router
from apps.api.app.modules.auth.router import router as auth_router
from apps.api.app.modules.catalog.router import router as catalog_router
from apps.api.app.modules.clients.router import router as clients_router
from apps.api.app.modules.dashboard.router import router as dashboard_router
from apps.api.app.modules.exports.router import router as exports_router
from apps.api.app.modules.health.router import router as health_router
from apps.api.app.modules.inbound.router import router as inbound_router
from apps.api.app.modules.mapping.router import router as mapping_router
from apps.api.app.modules.quality.router import router as quality_router
from apps.api.app.modules.reports.router import router as reports_router
from apps.api.app.modules.reserve.router import router as reserve_router
from apps.api.app.modules.sales.router import router as sales_router
from apps.api.app.modules.stock.router import router as stock_router
from apps.api.app.modules.uploads.router import router as uploads_router

api_router = APIRouter(prefix="/api")


def _protected_dependencies(resource: str, action: str = "read") -> list[Any]:
    return [
        Depends(require_user),
        Depends(require_authenticated_rate_limit),
        Depends(require_capability(resource, action)),
    ]


def _include_protected_router(router: APIRouter, *, resource: str, action: str = "read") -> None:
    api_router.include_router(router, dependencies=_protected_dependencies(resource, action))


def _include_authenticated_router(router: APIRouter) -> None:
    api_router.include_router(
        router,
        dependencies=[Depends(require_user), Depends(require_authenticated_rate_limit)],
    )


# Intentionally open for infra probes and sign-in bootstrap.
api_router.include_router(health_router)
api_router.include_router(auth_router)
_include_protected_router(dashboard_router, resource="dashboard")
_include_protected_router(catalog_router, resource="catalog")
_include_protected_router(clients_router, resource="clients")
_include_protected_router(stock_router, resource="stock")
_include_protected_router(inbound_router, resource="inbound")
_include_protected_router(sales_router, resource="sales")
_include_protected_router(reserve_router, resource="reserve")
_include_protected_router(mapping_router, resource="mapping")
_include_protected_router(uploads_router, resource="uploads")
_include_protected_router(quality_router, resource="quality")
_include_protected_router(reports_router, resource="dashboard")
_include_protected_router(assistant_router, resource="assistant", action="query")

# Mixed-capability surfaces keep route-level capability checks, but still require authentication globally.
_include_authenticated_router(exports_router)
_include_authenticated_router(admin_router)
