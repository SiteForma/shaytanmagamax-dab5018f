from __future__ import annotations

from apps.api.app.common.schemas import ORMModel


class SkuCostImportResponse(ORMModel):
    upload_file_id: str
    file_name: str
    total_rows: int
    imported_rows: int
    skipped_rows: int
    linked_sku_rows: int
    history_rows: int
