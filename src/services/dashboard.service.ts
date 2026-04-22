import type { DashboardSummary, ReserveRow, Sku, DiyClient } from "@/types";
import { DASHBOARD_SUMMARY, SKUS, DIY_CLIENTS, buildReserveRows } from "@/mocks/data/seed";
import { latency } from "./_latency";

export interface DashboardOverview {
  summary: DashboardSummary;
  topRiskSkus: { sku: Sku; shortage: number; coverageMonths: number }[];
  mostExposedClients: DiyClient[];
  coverageSeries: { month: string; coverage: number; target: number }[];
  inboundVsShortage: { month: string; inbound: number; shortage: number }[];
}

export async function getDashboardOverview(): Promise<DashboardOverview> {
  await latency();

  const sample = buildReserveRows({
    clientIds: DIY_CLIENTS.slice(0, 4).map((c) => c.id),
    reserveMonths: 3,
    safetyFactor: 1.1,
  });

  const topRiskSkus = sample
    .filter((r) => r.shortageQty > 0)
    .sort((a, b) => b.shortageQty - a.shortageQty)
    .slice(0, 6)
    .map((r) => ({
      sku: SKUS.find((s) => s.id === r.skuId)!,
      shortage: r.shortageQty,
      coverageMonths: r.coverageMonths,
    }));

  const mostExposedClients = [...DIY_CLIENTS]
    .sort((a, b) => b.shortageQty - a.shortageQty)
    .slice(0, 5);

  const months = Array.from({ length: 8 }).map((_, i) => {
    const d = new Date();
    d.setMonth(d.getMonth() - (7 - i));
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  });

  const coverageSeries = months.map((m, i) => ({
    month: m,
    coverage: +(1.2 + Math.sin(i / 2) * 0.4 + i * 0.05).toFixed(2),
    target: 2,
  }));

  const inboundVsShortage = months.map((m, i) => ({
    month: m,
    inbound: 8000 + Math.round(Math.cos(i / 2) * 2400 + i * 600),
    shortage: 12000 - Math.round(i * 700 + Math.sin(i) * 1400),
  }));

  return {
    summary: DASHBOARD_SUMMARY,
    topRiskSkus,
    mostExposedClients,
    coverageSeries,
    inboundVsShortage,
  };
}
