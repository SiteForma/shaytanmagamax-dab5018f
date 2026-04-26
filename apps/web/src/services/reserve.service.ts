import type { ReserveCalculationRequest, ReserveCalculationResult, ReserveRow, ReserveRunSummary } from "@/types";
import {
  reserveCalculationApiToViewModel,
  reserveRowApiToViewModel,
  reserveRunApiToViewModel,
} from "@/adapters/reserve.adapter";
import { api } from "@/lib/api/client";

export function mapReserveRow(item: any): ReserveRow {
  return reserveRowApiToViewModel(item);
}

function mapReserveRun(item: any): ReserveRunSummary {
  return reserveRunApiToViewModel(item);
}

export async function calculateReserve(req: ReserveCalculationRequest): Promise<ReserveCalculationResult> {
  const response = await api.post<any>("/reserve/calculate", {
    clientIds: req.clientIds,
    skuIds: req.skuIds,
    skuCodes: req.skuCodes,
    categoryIds: req.categoryIds,
    reserveMonths: req.reserveMonths,
    safetyFactor: req.safetyFactor,
    demandStrategy:
      req.demandStrategy ??
      (req.demandBasis === "sales_3m"
        ? "strict_recent_average"
        : req.demandBasis === "sales_6m"
          ? "conservative_fallback"
          : "weighted_recent_average"),
    includeInbound: req.includeInbound ?? true,
    inboundStatusesToCount: req.inboundStatusesToCount ?? ["confirmed"],
    asOfDate: req.asOfDate,
    groupingMode: req.groupingMode ?? "client_sku",
    persistRun: req.persistRun ?? true,
    horizonDays: req.horizonDays ?? 60,
  });
  return reserveCalculationApiToViewModel(response);
}
