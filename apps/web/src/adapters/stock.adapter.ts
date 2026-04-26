import type { PaginatedResult, Sku, StockSnapshot } from "@/types";
import { mapPaginatedResult, type ApiPaginationEnvelope } from "@/adapters/common";

export interface StockCoverageRowViewModel {
  sku: Sku;
  free: number;
  reservedLike: number;
  demandPerMonth: number;
  coverageMonths: number | null;
  warehouse: StockSnapshot["warehouse"];
  shortageQtyTotal: number;
  affectedClientsCount: number;
  worstStatus: string;
  inboundQtyWithinHorizon: number;
}

export interface PotentialStockoutRowViewModel {
  clientId: string;
  clientName: string;
  skuId: string;
  article: string;
  productName: string;
  categoryName?: string | null;
  shortageQty: number;
  coverageMonths: number | null;
  status: string;
  targetReserveQty: number;
  availableQty: number;
}

export function stockCoverageRowApiToViewModel(item: any): StockCoverageRowViewModel {
  return {
    sku: {
      id: item.sku_id,
      article: item.article,
      name: item.product_name,
      category: item.category_name,
      brand: "MAGAMAX",
      unit: "pcs",
      active: true,
    },
    free: item.free,
    reservedLike: item.reserved_like,
    demandPerMonth: item.demand_per_month,
    coverageMonths: item.coverage_months,
    warehouse: item.warehouse ?? "Не указан",
    shortageQtyTotal: item.shortage_qty_total,
    affectedClientsCount: item.affected_clients_count,
    worstStatus: item.worst_status,
    inboundQtyWithinHorizon: item.inbound_qty_within_horizon,
  };
}

export function paginatedStockCoverageApiToViewModel(
  payload: ApiPaginationEnvelope<any>,
): PaginatedResult<StockCoverageRowViewModel> {
  return mapPaginatedResult(payload, stockCoverageRowApiToViewModel);
}

export function stockoutRowApiToViewModel(item: any): PotentialStockoutRowViewModel {
  return {
    clientId: item.client_id,
    clientName: item.client_name,
    skuId: item.sku_id,
    article: item.article,
    productName: item.product_name,
    categoryName: item.category_name,
    shortageQty: item.shortage_qty,
    coverageMonths: item.coverage_months,
    status: item.status,
    targetReserveQty: item.target_reserve_qty,
    availableQty: item.available_qty,
  };
}
