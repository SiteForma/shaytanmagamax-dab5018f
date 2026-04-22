import type { ReserveCalculationRequest, ReserveRow } from "@/types";
import { buildReserveRows, DIY_CLIENTS } from "@/mocks/data/seed";
import { latency } from "./_latency";

export async function calculateReserve(req: ReserveCalculationRequest): Promise<ReserveRow[]> {
  await latency(420);
  return buildReserveRows({
    clientIds: req.clientIds.length ? req.clientIds : DIY_CLIENTS.slice(0, 3).map((c) => c.id),
    skuIds: req.skuIds,
    categories: req.categories,
    reserveMonths: req.reserveMonths,
    safetyFactor: req.safetyFactor,
  });
}
