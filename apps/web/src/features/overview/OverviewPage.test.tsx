import { screen } from "@testing-library/react";
import OverviewPage from "@/features/overview/OverviewPage";
import { renderWithProviders } from "@/test/render";

const useDashboardOverviewQuery = vi.fn();

vi.mock("@/hooks/queries/use-dashboard", () => ({
  useDashboardOverviewQuery: () => useDashboardOverviewQuery(),
}));

describe("OverviewPage", () => {
  beforeEach(() => {
    useDashboardOverviewQuery.mockReset();
  });

  it("renders live overview data", () => {
    useDashboardOverviewQuery.mockReturnValue({
      data: {
        summary: {
          totalSkusTracked: 128,
          diyClientsUnderReserve: 3,
          positionsAtRisk: 21,
          totalReserveShortage: 9420,
          inboundWithinHorizon: 4300,
          avgCoverageMonths: 1.8,
          lastUpdate: "2026-04-23T10:00:00Z",
          freshnessHours: 2,
          openQualityIssues: 4,
          latestRunId: "run_1",
        },
        topRiskSkus: [
          {
            sku: { id: "sku_1", article: "K-100", name: "Направляющая", category: "Фурнитура", brand: "MAGAMAX", unit: "pcs", active: true },
            shortage: 1200,
            coverageMonths: 0.8,
            affectedClientsCount: 2,
            worstStatus: "critical",
          },
        ],
        mostExposedClients: [
          {
            id: "client_1",
            name: "Леман Про",
            region: "ЦФО",
            reserveMonths: 3,
            positionsTracked: 22,
            shortageQty: 2200,
            criticalPositions: 5,
            warningPositions: 4,
            coverageMonths: 0.9,
            expectedInboundRelief: 600,
          },
        ],
        coverageDistribution: [{ bucket: "under_1m", count: 12 }],
        inboundVsShortage: [{ month: "2026-04", inbound: 2000, shortage: 1500 }],
        freshness: {
          lastUploadAt: "2026-04-23T09:00:00Z",
          lastReserveRunAt: "2026-04-23T10:00:00Z",
          freshnessHours: 2,
          openQualityIssues: 4,
          latestRunId: "run_1",
        },
      },
      error: null,
    });

    renderWithProviders(<OverviewPage />);

    expect(screen.getByText("128")).toBeInTheDocument();
    expect(screen.getByText("Направляющая")).toBeInTheDocument();
    expect(screen.getByText("Леман Про")).toBeInTheDocument();
  });
});
