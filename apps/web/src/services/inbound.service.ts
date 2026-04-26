import type { InboundDelivery, Sku, DiyClient } from "@/types";
import { api } from "@/lib/api/client";

export interface InboundWithRefs extends InboundDelivery {
  sku: Sku;
  clients: DiyClient[];
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
    qty: item.qty,
    eta: item.eta,
    status: item.status,
    affectedClients: item.affected_clients,
    reserveImpact: item.reserve_impact,
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
