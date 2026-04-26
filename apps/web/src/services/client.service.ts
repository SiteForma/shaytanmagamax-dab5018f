import type { DiyClient, ReserveRow } from "@/types";
import { api } from "@/lib/api/client";
import { mapReserveRow } from "./reserve.service";

export async function listClients(): Promise<DiyClient[]> {
  const response = await api.get<any[]>("/clients/diy");
  return response.map((item) => ({
    id: item.id,
    name: item.name,
    region: item.region,
    reserveMonths: item.reserve_months,
    positionsTracked: item.positions_tracked,
    shortageQty: item.shortage_qty,
    criticalPositions: item.critical_positions,
    warningPositions: item.warning_positions,
    coverageMonths: item.coverage_months ?? 0,
    expectedInboundRelief: item.expected_inbound_relief,
    latestRunId: item.latest_run_id,
  }));
}

export async function getClientReserve(clientId: string): Promise<ReserveRow[]> {
  const response = await api.get<any[]>(`/clients/diy/${clientId}/reserve-rows`);
  return response.map(mapReserveRow);
}

export interface ClientDetail extends DiyClient {
  code: string;
  networkType: string;
  policyActive: boolean;
  safetyFactor: number;
  priorityLevel: number;
  allowedFallbackDepth: number;
  notes?: string | null;
}

export async function getClientDetail(clientId: string): Promise<ClientDetail> {
  const item = await api.get<any>(`/clients/diy/${clientId}/reserve-summary`);
  return {
    id: item.id,
    name: item.name,
    region: item.region,
    reserveMonths: item.reserve_months,
    positionsTracked: item.positions_tracked,
    shortageQty: item.shortage_qty,
    criticalPositions: item.critical_positions,
    warningPositions: item.warning_positions,
    coverageMonths: item.coverage_months ?? 0,
    expectedInboundRelief: item.expected_inbound_relief,
    latestRunId: item.latest_run_id,
    code: item.code,
    networkType: item.network_type,
    policyActive: item.policy_active,
    safetyFactor: item.safety_factor,
    priorityLevel: item.priority_level,
    allowedFallbackDepth: item.allowed_fallback_depth,
    notes: item.notes,
  };
}

export interface ClientTopSku {
  skuId: string;
  skuCode: string;
  productName: string;
  categoryName?: string | null;
  status: string;
  shortageQty: number;
  coverageMonths?: number | null;
  targetReserveQty: number;
  availableQty: number;
}

export async function getClientTopSkus(clientId: string): Promise<ClientTopSku[]> {
  return api.get<ClientTopSku[]>(`/clients/diy/${clientId}/top-skus`);
}

export interface ClientCategoryExposure {
  categoryName: string;
  positions: number;
  shortageQtyTotal: number;
}

export async function getClientCategoryExposure(clientId: string): Promise<ClientCategoryExposure[]> {
  const response = await api.get<any[]>(`/clients/diy/${clientId}/category-exposure`);
  return response.map((item) => ({
    categoryName: item.category_name,
    positions: item.positions,
    shortageQtyTotal: item.shortage_qty_total,
  }));
}
