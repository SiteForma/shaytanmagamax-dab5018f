from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

from apps.api.app.modules.reserve.schemas import CoverageBucketResponse, ReserveRowResponse

STATUS_RANK = {
    "critical": 5,
    "warning": 4,
    "no_history": 3,
    "inactive": 2,
    "healthy": 1,
    "overstocked": 0,
}


def summarize_reserve_rows(rows: list[ReserveRowResponse]) -> tuple[dict[str, float | int | None], dict[str, int]]:
    coverage_values = [row.coverage_months for row in rows if row.coverage_months is not None]
    status_counts = Counter(row.status for row in rows)
    totals: dict[str, float | int | None] = {
        "positions": len(rows),
        "positions_at_risk": sum(1 for row in rows if row.status in {"critical", "warning"}),
        "critical_positions": status_counts.get("critical", 0),
        "warning_positions": status_counts.get("warning", 0),
        "total_shortage_qty": round(sum(row.shortage_qty for row in rows), 1),
        "total_target_reserve_qty": round(sum(row.target_reserve_qty for row in rows), 1),
        "total_available_qty": round(sum(row.available_qty for row in rows), 1),
        "avg_coverage_months": round(sum(coverage_values) / len(coverage_values), 1)
        if coverage_values
        else None,
    }
    return totals, dict(status_counts)


def aggregate_top_risk_skus(rows: list[ReserveRowResponse]) -> list[dict[str, object]]:
    sku_rollup: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "sku_id": "",
            "sku_code": "",
            "product_name": "",
            "category_name": None,
            "affected_clients_count": 0,
            "shortage_qty_total": 0.0,
            "min_coverage_months": None,
            "worst_status": "healthy",
        }
    )
    for row in rows:
        bucket = sku_rollup[row.sku_id]
        bucket["sku_id"] = row.sku_id
        bucket["sku_code"] = row.article
        bucket["product_name"] = row.product_name
        bucket["category_name"] = row.category
        if row.shortage_qty > 0 or row.status in {"critical", "warning"}:
            bucket["affected_clients_count"] = int(bucket["affected_clients_count"]) + 1
        bucket["shortage_qty_total"] = round(float(bucket["shortage_qty_total"]) + row.shortage_qty, 1)
        current_min = bucket["min_coverage_months"]
        if row.coverage_months is not None:
            bucket["min_coverage_months"] = (
                row.coverage_months
                if current_min is None
                else min(float(current_min), row.coverage_months)
            )
        if STATUS_RANK[row.status] > STATUS_RANK[str(bucket["worst_status"])]:
            bucket["worst_status"] = row.status
    return sorted(
        sku_rollup.values(),
        key=lambda item: (float(item["shortage_qty_total"]), STATUS_RANK[str(item["worst_status"])]),
        reverse=True,
    )


def aggregate_exposed_clients(rows: list[ReserveRowResponse]) -> list[dict[str, object]]:
    client_rollup: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "client_id": "",
            "client_name": "",
            "critical_positions": 0,
            "warning_positions": 0,
            "positions_tracked": 0,
            "shortage_qty_total": 0.0,
            "coverage_values": [],
            "inbound_relief_qty": 0.0,
        }
    )
    for row in rows:
        bucket = client_rollup[row.client_id]
        bucket["client_id"] = row.client_id
        bucket["client_name"] = row.client_name
        bucket["positions_tracked"] = int(bucket["positions_tracked"]) + 1
        bucket["critical_positions"] = int(bucket["critical_positions"]) + (
            1 if row.status == "critical" else 0
        )
        bucket["warning_positions"] = int(bucket["warning_positions"]) + (
            1 if row.status == "warning" else 0
        )
        bucket["shortage_qty_total"] = round(float(bucket["shortage_qty_total"]) + row.shortage_qty, 1)
        if row.coverage_months is not None:
            bucket["coverage_values"].append(row.coverage_months)
        bucket["inbound_relief_qty"] = round(
            float(bucket["inbound_relief_qty"]) + row.inbound_within_horizon,
            1,
        )
    items: list[dict[str, object]] = []
    for item in client_rollup.values():
        coverage_values = item.pop("coverage_values")
        item["avg_coverage_months"] = (
            round(sum(coverage_values) / len(coverage_values), 1) if coverage_values else None
        )
        items.append(item)
    return sorted(items, key=lambda item: float(item["shortage_qty_total"]), reverse=True)


def aggregate_coverage_distribution(rows: list[ReserveRowResponse]) -> list[CoverageBucketResponse]:
    buckets = Counter(
        "no_history"
        if row.status == "no_history"
        else "overstocked"
        if row.status == "overstocked"
        else "under_1m"
        if row.coverage_months is not None and row.coverage_months < 1
        else "between_1m_and_target"
        if row.status in {"critical", "warning"}
        else "healthy"
        for row in rows
    )
    ordered = ["no_history", "under_1m", "between_1m_and_target", "healthy", "overstocked"]
    return [CoverageBucketResponse(bucket=bucket, count=buckets.get(bucket, 0)) for bucket in ordered]


def aggregate_inbound_vs_shortage(
    rows: list[ReserveRowResponse], inbound_timeline: list[dict[str, object]], as_of_date: date
) -> list[dict[str, object]]:
    shortage_total = round(sum(row.shortage_qty for row in rows), 1)
    months: dict[str, float] = defaultdict(float)
    for item in inbound_timeline:
        months[str(item["month"])] += float(item["inbound_qty"])
    ordered_months = sorted(months)[:6]
    if not ordered_months:
        ordered_months = [as_of_date.strftime("%Y-%m")]
    return [
        {
            "month": month,
            "inbound_qty": round(months.get(month, 0.0), 1),
            "shortage_qty": shortage_total,
        }
        for month in ordered_months
    ]


def aggregate_client_top_skus(rows: list[ReserveRowResponse], client_id: str) -> list[dict[str, object]]:
    selected_rows = [row for row in rows if row.client_id == client_id]
    return [
        {
            "sku_id": row.sku_id,
            "sku_code": row.article,
            "product_name": row.product_name,
            "category_name": row.category,
            "status": row.status,
            "shortage_qty": row.shortage_qty,
            "coverage_months": row.coverage_months,
            "target_reserve_qty": row.target_reserve_qty,
            "available_qty": row.available_qty,
        }
        for row in sorted(selected_rows, key=lambda item: (item.shortage_qty, STATUS_RANK[item.status]), reverse=True)[:10]
    ]


def aggregate_client_category_exposure(rows: list[ReserveRowResponse], client_id: str) -> list[dict[str, object]]:
    selected_rows = [row for row in rows if row.client_id == client_id]
    exposure: dict[str, dict[str, object]] = defaultdict(
        lambda: {"category_name": "Unassigned", "positions": 0, "shortage_qty_total": 0.0}
    )
    for row in selected_rows:
        key = row.category or "Unassigned"
        bucket = exposure[key]
        bucket["category_name"] = key
        bucket["positions"] = int(bucket["positions"]) + 1
        bucket["shortage_qty_total"] = round(float(bucket["shortage_qty_total"]) + row.shortage_qty, 1)
    return sorted(exposure.values(), key=lambda item: float(item["shortage_qty_total"]), reverse=True)


def aggregate_sku_reserve_summary(rows: list[ReserveRowResponse], sku_id: str) -> dict[str, object] | None:
    selected_rows = [row for row in rows if row.sku_id == sku_id]
    if not selected_rows:
        return None
    coverage_values = [row.coverage_months for row in selected_rows if row.coverage_months is not None]
    worst_status = max(selected_rows, key=lambda row: STATUS_RANK[row.status]).status
    return {
        "sku_id": sku_id,
        "sku_code": selected_rows[0].article,
        "product_name": selected_rows[0].product_name,
        "category_name": selected_rows[0].category,
        "affected_clients_count": len(selected_rows),
        "shortage_qty_total": round(sum(row.shortage_qty for row in selected_rows), 1),
        "avg_coverage_months": round(sum(coverage_values) / len(coverage_values), 1)
        if coverage_values
        else None,
        "worst_status": worst_status,
    }


def aggregate_stock_coverage(rows: list[ReserveRowResponse]) -> list[dict[str, object]]:
    sku_rollup = aggregate_top_risk_skus(rows)
    coverage_rows: list[dict[str, object]] = []
    for item in sku_rollup:
        coverage_rows.append(
            {
                "sku_id": item["sku_id"],
                "article": item["sku_code"],
                "product_name": item["product_name"],
                "category_name": item["category_name"],
                "affected_clients_count": item["affected_clients_count"],
                "shortage_qty_total": item["shortage_qty_total"],
                "min_coverage_months": item["min_coverage_months"],
                "worst_status": item["worst_status"],
            }
        )
    return coverage_rows


def aggregate_potential_stockout(rows: list[ReserveRowResponse]) -> list[ReserveRowResponse]:
    return sorted(
        [row for row in rows if row.status in {"critical", "warning"}],
        key=lambda row: (STATUS_RANK[row.status], row.shortage_qty),
        reverse=True,
    )
