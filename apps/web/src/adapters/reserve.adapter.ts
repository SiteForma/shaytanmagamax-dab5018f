import type { ReserveCalculationResult, ReserveRow, ReserveRunSummary } from "@/types";

export function reserveRowApiToViewModel(item: any): ReserveRow {
  return {
    clientId: item.client_id,
    clientName: item.client_name,
    skuId: item.sku_id,
    article: item.article,
    productName: item.product_name,
    category: item.category,
    salesQty1m: item.sales_qty_1m,
    salesQty3m: item.sales_qty_3m,
    salesQty6m: item.sales_qty_6m,
    avgMonthly3m: item.avg_monthly_3m,
    avgMonthly6m: item.avg_monthly_6m,
    historyMonthsAvailable: item.history_months_available,
    lastSaleDate: item.last_sale_date,
    demandStability: item.demand_stability,
    trendSignal: item.trend_signal,
    demandPerMonth: item.demand_per_month,
    reserveMonths: item.reserve_months,
    safetyFactor: item.safety_factor,
    targetReserveQty: item.target_reserve_qty,
    freeStock: item.free_stock,
    inboundWithinHorizon: item.inbound_within_horizon,
    totalFreeStockQty: item.total_free_stock_qty,
    totalInboundWithinHorizonQty: item.total_inbound_in_horizon_qty,
    allocatedFreeStockQty: item.allocated_free_stock_qty,
    allocatedInboundQty: item.allocated_inbound_qty,
    availableQty: item.available_qty,
    shortageQty: item.shortage_qty,
    coverageMonths: item.coverage_months,
    status: item.status,
    statusReason: item.status_reason,
    demandBasis: item.demand_basis,
    demandBasisType: item.demand_basis_type,
    fallbackLevel: item.fallback_level,
    basisWindowUsed: item.basis_window_used,
    explanationPayload: item.explanation_payload,
  };
}

export function reserveRunApiToViewModel(item: any): ReserveRunSummary {
  return {
    id: item.id,
    scopeType: item.scope_type,
    groupingMode: item.grouping_mode,
    reserveMonths: item.reserve_months,
    safetyFactor: item.safety_factor,
    demandStrategy: item.demand_strategy,
    includeInbound: item.include_inbound,
    inboundStatuses: item.inbound_statuses,
    horizonDays: item.horizon_days,
    rowCount: item.row_count,
    status: item.status,
    createdAt: item.created_at,
    summaryPayload: item.summary_payload,
  };
}

export function reserveCalculationApiToViewModel(response: any): ReserveCalculationResult {
  return {
    run: reserveRunApiToViewModel(response.run),
    rows: (response.rows ?? []).map(reserveRowApiToViewModel),
  };
}
