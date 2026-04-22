import type { InboundDelivery, Sku, DiyClient } from "@/types";
import { INBOUND, SKUS, DIY_CLIENTS } from "@/mocks/data/seed";
import { latency } from "./_latency";

export interface InboundWithRefs extends InboundDelivery {
  sku: Sku;
  clients: DiyClient[];
}

export async function getInboundTimeline(): Promise<InboundWithRefs[]> {
  await latency();
  return INBOUND.map((i) => ({
    ...i,
    sku: SKUS.find((s) => s.id === i.skuId)!,
    clients: DIY_CLIENTS.filter((c) => i.affectedClients.includes(c.id)),
  })).sort((a, b) => +new Date(a.eta) - +new Date(b.eta));
}
