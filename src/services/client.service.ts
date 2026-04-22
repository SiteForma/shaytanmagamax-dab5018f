import type { DiyClient, ReserveRow } from "@/types";
import { DIY_CLIENTS, buildReserveRows } from "@/mocks/data/seed";
import { latency } from "./_latency";

export async function listClients(): Promise<DiyClient[]> {
  await latency(160);
  return DIY_CLIENTS;
}

export async function getClientReserve(clientId: string): Promise<ReserveRow[]> {
  await latency();
  return buildReserveRows({
    clientIds: [clientId],
    reserveMonths: DIY_CLIENTS.find((c) => c.id === clientId)?.reserveMonths ?? 3,
    safetyFactor: 1.1,
  });
}
