from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.db.models import SalesFact
from apps.api.app.modules.sales.schemas import MonthlySalesResponse


def get_monthly_sales(
    db: Session,
    sku_id: str | None = None,
    client_id: str | None = None,
) -> list[MonthlySalesResponse]:
    stmt = select(SalesFact).order_by(SalesFact.period_month)
    if sku_id:
        stmt = stmt.where(SalesFact.sku_id == sku_id)
    if client_id:
        stmt = stmt.where(SalesFact.client_id == client_id)
    return [
        MonthlySalesResponse(month=row.period_month.strftime("%Y-%m"), qty=row.quantity)
        for row in db.scalars(stmt).all()
    ]
