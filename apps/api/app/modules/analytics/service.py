from __future__ import annotations

from pathlib import Path
from threading import Lock

import duckdb
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.config import Settings
from apps.api.app.db.models import InboundDelivery, ReserveRow, SalesFact, StockSnapshot

_ANALYTICS_MATERIALIZE_LOCK = Lock()


def materialize_analytics(db: Session, settings: Settings) -> None:
    with _ANALYTICS_MATERIALIZE_LOCK:
        parquet_root = Path(settings.parquet_root)
        parquet_root.mkdir(parents=True, exist_ok=True)
        duckdb_path = Path(settings.duckdb_path)
        duckdb_path.parent.mkdir(parents=True, exist_ok=True)

        sales_rows = [
            {
                "id": row.id,
                "client_id": row.client_id,
                "sku_id": row.sku_id,
                "category_id": row.category_id,
                "period_month": row.period_month.isoformat(),
                "quantity": row.quantity,
            }
            for row in db.scalars(select(SalesFact)).all()
        ]
        stock_rows = [
            {
                "id": row.id,
                "sku_id": row.sku_id,
                "warehouse_code": row.warehouse_code,
                "snapshot_at": row.snapshot_at.isoformat(),
                "free_stock_qty": row.free_stock_qty,
                "reserved_like_qty": row.reserved_like_qty,
            }
            for row in db.scalars(select(StockSnapshot)).all()
        ]
        inbound_rows = [
            {
                "id": row.id,
                "sku_id": row.sku_id,
                "quantity": row.quantity,
                "eta_date": row.eta_date.isoformat(),
                "status": row.status,
                "reserve_impact_qty": row.reserve_impact_qty,
            }
            for row in db.scalars(select(InboundDelivery)).all()
        ]
        reserve_rows = [
            {
                "id": row.id,
                "run_id": row.run_id,
                "client_id": row.client_id,
                "sku_id": row.sku_id,
                "shortage_qty": row.shortage_qty,
                "coverage_months": row.coverage_months,
                "status": row.status,
            }
            for row in db.scalars(select(ReserveRow)).all()
        ]

        datasets = {
            "sales_facts": pd.DataFrame(sales_rows),
            "stock_snapshots": pd.DataFrame(stock_rows),
            "inbound_deliveries": pd.DataFrame(inbound_rows),
            "reserve_rows": pd.DataFrame(reserve_rows),
        }

        for name, frame in datasets.items():
            parquet_path = parquet_root / f"{name}.parquet"
            if frame.empty:
                if parquet_path.exists():
                    parquet_path.unlink()
                continue
            frame.to_parquet(parquet_path, index=False)

        with duckdb.connect(str(duckdb_path)) as conn:
            for name, frame in datasets.items():
                if frame.empty:
                    conn.execute(f"drop table if exists {name}")
                    continue
                conn.register("tmp_frame", frame)
                conn.execute(f"create or replace table {name} as select * from tmp_frame")
                conn.unregister("tmp_frame")
