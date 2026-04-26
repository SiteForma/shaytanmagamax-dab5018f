import type { InboundDelivery, Sku, DiyClient } from "@/types";
import { api } from "@/lib/api/client";

export interface InboundWithRefs extends InboundDelivery {
  sku: Sku;
  clients: DiyClient[];
  containerRef?: string | null;
  freeStockAfterAllocation: number;
  clientOrderQty: number;
  sheetStatus?: string | null;
  clientAllocations: Record<string, number>;
  sourceSyncedAt?: string | null;
}

export interface InboundSyncResult {
  status: string;
  sourceUrl: string;
  syncedAt: string;
  rowsSeen: number;
  rowsImported: number;
  rowsSkipped: number;
  deliveriesReplaced: number;
  skuCreated: number;
  clientsCreated: number;
  totalInTransitQty: number;
  totalFreeStockAfterAllocationQty: number;
  totalClientOrderQty: number;
  warnings: string[];
}

export async function getInboundTimeline(): Promise<InboundWithRefs[]> {
  const [timeline, clients] = await Promise.all([api.get<any[]>("/inbound/timeline"), api.get<any[]>("/clients")]);
  const clientMap = new Map(
    clients.map((client) => [
      client.id,
      {
        id: client.id,
        name: client.name,
        region: client.region,
        reserveMonths: client.reserve_months,
        positionsTracked: client.positions_tracked,
        shortageQty: client.shortage_qty,
        criticalPositions: client.critical_positions,
        coverageMonths: client.coverage_months,
        expectedInboundRelief: client.expected_inbound_relief,
      },
    ]),
  );

  return timeline.map((item) => ({
    id: item.id,
    skuId: item.sku_id,
    containerRef: item.container_ref ?? null,
    qty: item.qty,
    freeStockAfterAllocation: item.free_stock_after_allocation ?? 0,
    clientOrderQty: item.client_order_qty ?? 0,
    eta: item.eta,
    status: item.status,
    sheetStatus: item.sheet_status ?? null,
    affectedClients: item.affected_clients,
    clientAllocations: item.client_allocations ?? {},
    reserveImpact: item.reserve_impact,
    sourceSyncedAt: item.source_synced_at ?? null,
    sku: {
      id: item.sku_id,
      article: item.article,
      name: item.sku_name,
      category: null,
      brand: "MAGAMAX",
      unit: "pcs",
      active: true,
    },
    clients: item.affected_clients
      .map((clientId: string) => clientMap.get(clientId))
      .filter(Boolean) as DiyClient[],
  }));
}

export async function syncInboundSheet(): Promise<InboundSyncResult> {
  const response = await api.post<any>("/inbound/sync", {});
  return {
    status: response.status,
    sourceUrl: response.source_url,
    syncedAt: response.synced_at,
    rowsSeen: response.rows_seen,
    rowsImported: response.rows_imported,
    rowsSkipped: response.rows_skipped,
    deliveriesReplaced: response.deliveries_replaced,
    skuCreated: response.sku_created,
    clientsCreated: response.clients_created,
    totalInTransitQty: response.total_in_transit_qty,
    totalFreeStockAfterAllocationQty: response.total_free_stock_after_allocation_qty,
    totalClientOrderQty: response.total_client_order_qty,
    warnings: response.warnings ?? [],
  };
}
