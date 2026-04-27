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
    categoryPath: item.category_path,
    brand: item.brand,
    unit: item.unit,
    active: item.active,
    costRub: item.cost_rub,
    costProductName: item.cost_product_name,
  }));
}

export interface SkuCostItem {
  article: string;
  productName: string;
  costRub: number;
  uploadFileId?: string | null;
  sourceRowNumber?: number | null;
  updatedAt: string;
}

export async function listSkuCosts(query?: string): Promise<SkuCostItem[]> {
  const params = new URLSearchParams();
  params.set("limit", "10000");
  if (query) {
    params.set("query", query);
  }
  const response = await api.get<any[]>(`/catalog/sku-costs?${params.toString()}`);
  return response.map((item) => ({
    article: item.article,
    productName: item.product_name,
    costRub: item.cost_rub,
    uploadFileId: item.upload_file_id,
    sourceRowNumber: item.source_row_number,
    updatedAt: item.updated_at,
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
  cost?: {
    article: string;
    productName: string;
    costRub: number;
    uploadFileId?: string | null;
    sourceRowNumber?: number | null;
    updatedAt: string;
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
        categoryPath: response.sku.category_path,
        brand: response.sku.brand,
        unit: response.sku.unit,
        active: response.sku.active,
        costRub: response.sku.cost_rub,
        costProductName: response.sku.cost_product_name,
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
      cost: response.cost
        ? {
            article: response.cost.article,
            productName: response.cost.product_name,
            costRub: response.cost.cost_rub,
            uploadFileId: response.cost.upload_file_id,
            sourceRowNumber: response.cost.source_row_number,
            updatedAt: response.cost.updated_at,
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
