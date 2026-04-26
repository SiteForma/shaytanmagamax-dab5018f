import type { DashboardSummary, DiyClient, Sku } from "@/types";

export interface DashboardOverviewViewModel {
  summary: DashboardSummary & {
    openQualityIssues: number;
    latestRunId?: string | null;
  };
  topRiskSkus: {
    sku: Sku;
    shortage: number;
    coverageMonths: number | null;
    affectedClientsCount: number;
    worstStatus: string;
  }[];
  mostExposedClients: DiyClient[];
  coverageDistribution: { bucket: string; count: number }[];
  inboundVsShortage: { month: string; inbound: number; shortage: number }[];
  freshness: {
    lastUploadAt?: string | null;
    lastReserveRunAt?: string | null;
    freshnessHours: number;
    openQualityIssues: number;
    latestRunId?: string | null;
  };
}

export function dashboardOverviewApiToViewModel(response: any): DashboardOverviewViewModel {
  return {
    summary: {
      totalSkusTracked: response.summary.total_skus_tracked,
      diyClientsUnderReserve: response.summary.active_diy_clients,
      positionsAtRisk: response.summary.positions_at_risk,
      totalReserveShortage: response.summary.total_shortage_qty,
      inboundWithinHorizon: response.summary.inbound_qty_within_horizon,
      avgCoverageMonths: response.summary.avg_coverage_months ?? 0,
      lastUpdate: response.summary.last_update,
      freshnessHours: response.summary.freshness_hours,
      openQualityIssues: response.summary.open_quality_issues,
      latestRunId: response.summary.latest_run_id,
    },
    topRiskSkus: (response.top_risk_skus ?? []).map((item: any) => ({
      sku: {
        id: item.sku_id,
        article: item.sku_code,
        name: item.product_name,
        category: item.category_name,
        brand: "MAGAMAX",
        unit: "pcs",
        active: true,
      },
      shortage: item.shortage_qty_total,
      coverageMonths: item.min_coverage_months,
      affectedClientsCount: item.affected_clients_count,
      worstStatus: item.worst_status,
    })),
    mostExposedClients: (response.exposed_clients ?? []).map((item: any) => ({
      id: item.client_id,
      name: item.client_name,
      region: "",
      reserveMonths: 3,
      positionsTracked: item.positions_tracked,
      shortageQty: item.shortage_qty_total,
      criticalPositions: item.critical_positions,
      warningPositions: item.warning_positions,
      coverageMonths: item.avg_coverage_months ?? 0,
      expectedInboundRelief: item.inbound_relief_qty,
    })),
    coverageDistribution: (response.coverage_distribution ?? []).map((item: any) => ({
      bucket: item.bucket,
      count: item.count,
    })),
    inboundVsShortage: (response.inbound_vs_shortage ?? []).map((item: any) => ({
      month: item.month,
      inbound: item.inbound_qty,
      shortage: item.shortage_qty,
    })),
    freshness: {
      lastUploadAt: response.freshness.last_upload_at,
      lastReserveRunAt: response.freshness.last_reserve_run_at,
      freshnessHours: response.freshness.freshness_hours,
      openQualityIssues: response.freshness.open_quality_issues,
      latestRunId: response.freshness.latest_run_id,
    },
  };
}
