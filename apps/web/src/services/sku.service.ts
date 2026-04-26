import type { Sku, MonthlySalesPoint, StockSnapshot, InboundDelivery, DiyClient } from "@/types";
import { api } from "@/lib/api/client";
import { isApiError } from "@/lib/errors";

export async function listSkus(query?: string): Promise<Sku[]> {
  const search = query ? `?query=${encodeURIComponent(query)}` : "";
  const response = await api.get<any[]>(`/catalog/skus${search}`);
  return response.map((item) => ({
    id: item.id,
    article: item.article,
    name: item.name,
    category: item.category,
    brand: item.brand,
    unit: item.unit,
    active: item.active,
  }));
}

export interface SkuDetail {
  sku: Sku;
  sales: MonthlySalesPoint[];
  stock: StockSnapshot | undefined;
  inbound: InboundDelivery[];
  clientSplit: {
    client: DiyClient;
    share: number;
    reservePosition: number;
    shortageQty: number;
    coverageMonths: number | null;
    status: string;
  }[];
  reserveSummary?: {
    shortageQtyTotal: number;
    affectedClientsCount: number;
    avgCoverageMonths: number | null;
    worstStatus: string;
    latestRunId?: string | null;
  } | null;
}

export async function getSkuDetail(skuId: string): Promise<SkuDetail | null> {
  try {
    const response = await api.get<any>(`/catalog/skus/${skuId}`);
    return {
      sku: {
        id: response.sku.id,
        article: response.sku.article,
        name: response.sku.name,
        category: response.sku.category,
        brand: response.sku.brand,
        unit: response.sku.unit,
        active: response.sku.active,
      },
      sales: response.sales.map((item: any): MonthlySalesPoint => ({
        month: item.month,
        qty: item.qty,
      })),
      stock: response.stock
        ? ({
            skuId: response.stock.sku_id,
            freeStock: response.stock.free_stock,
            reservedLike: response.stock.reserved_like,
            warehouse: response.stock.warehouse,
            updatedAt: response.stock.updated_at,
          } satisfies StockSnapshot)
        : undefined,
      inbound: response.inbound.map((item: any): InboundDelivery => ({
        id: item.id,
        skuId: item.sku_id,
        qty: item.qty,
        eta: item.eta,
        status: item.status,
        affectedClients: item.affected_clients,
        reserveImpact: item.reserve_impact,
      })),
      clientSplit: response.client_split.map((item: any) => ({
        client: {
          id: item.client_id,
          name: item.client_name,
          region: "",
          reserveMonths: 3,
          positionsTracked: 0,
          shortageQty: 0,
          criticalPositions: 0,
          coverageMonths: 0,
          expectedInboundRelief: 0,
        } satisfies DiyClient,
        share: item.share,
        reservePosition: item.reserve_position,
        shortageQty: item.shortage_qty,
        coverageMonths: item.coverage_months,
        status: item.status,
      })),
      reserveSummary: response.reserve_summary
        ? {
            shortageQtyTotal: response.reserve_summary.shortage_qty_total,
            affectedClientsCount: response.reserve_summary.affected_clients_count,
            avgCoverageMonths: response.reserve_summary.avg_coverage_months,
            worstStatus: response.reserve_summary.worst_status,
            latestRunId: response.reserve_summary.latest_run_id,
          }
        : null,
    };
  } catch (error) {
    if (isApiError(error) && error.status === 404) {
      return null;
    }
    throw error;
  }
}
