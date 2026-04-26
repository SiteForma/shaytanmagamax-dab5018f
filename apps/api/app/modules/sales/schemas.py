from __future__ import annotations

from apps.api.app.common.schemas import ORMModel


class MonthlySalesResponse(ORMModel):
    month: str
    qty: float
