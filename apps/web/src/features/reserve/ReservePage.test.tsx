import { screen, waitFor } from "@testing-library/react";
import ReservePage from "@/features/reserve/ReservePage";
import { renderWithProviders } from "@/test/render";

const useClientsQuery = vi.fn();
const useSkusQuery = vi.fn();
const useReserveCalculationMutation = vi.fn();

vi.mock("@/hooks/queries/use-clients", () => ({
  useClientsQuery: () => useClientsQuery(),
}));

vi.mock("@/hooks/queries/use-sku", () => ({
  useSkusQuery: () => useSkusQuery(),
}));

vi.mock("@/hooks/queries/use-reserve", () => ({
  useReserveCalculationMutation: () => useReserveCalculationMutation(),
}));

describe("ReservePage", () => {
  beforeEach(() => {
    useClientsQuery.mockReset();
    useSkusQuery.mockReset();
    useReserveCalculationMutation.mockReset();
  });

  it("runs reserve calculation for selected client and sku list", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({
      run: {
        id: "run_1",
        scopeType: "client_sku_list",
        groupingMode: "client_sku",
        reserveMonths: 3,
        safetyFactor: 1.1,
        demandStrategy: "weighted_recent_average",
        includeInbound: true,
        inboundStatuses: ["confirmed"],
        horizonDays: 60,
        rowCount: 1,
        status: "completed",
        createdAt: "2026-04-23T10:00:00Z",
        summaryPayload: {},
      },
      rows: [
        {
          clientId: "client_1",
          clientName: "Леман Про",
          skuId: "sku_1",
          article: "K-100",
          productName: "Направляющая",
          category: "Фурнитура",
          avgMonthly3m: 120,
          avgMonthly6m: 110,
          demandPerMonth: 116,
          reserveMonths: 3,
          safetyFactor: 1.1,
          targetReserveQty: 383,
          freeStock: 90,
          inboundWithinHorizon: 50,
          availableQty: 140,
          shortageQty: 243,
          coverageMonths: 1.2,
          status: "critical",
          statusReason: "Покрытие значительно ниже целевого резерва",
        },
      ],
    });

    useClientsQuery.mockReturnValue({
      data: [{ id: "client_1", name: "Леман Про", region: "ЦФО", reserveMonths: 3, positionsTracked: 10, shortageQty: 200, criticalPositions: 1, coverageMonths: 1, expectedInboundRelief: 30 }],
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    useSkusQuery.mockReturnValue({
      data: [{ id: "sku_1", article: "K-100", name: "Направляющая", category: "Фурнитура", brand: "MAGAMAX", unit: "pcs", active: true }],
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    useReserveCalculationMutation.mockReturnValue({
      mutateAsync,
      isPending: false,
      error: null,
    });

    renderWithProviders(
      <ReservePage />,
      "/reserve?client=client_1&skus=sku_1&horizon=3&safety=1.1&strategy=weighted_recent_average",
    );

    await waitFor(() => expect(mutateAsync).toHaveBeenCalled());
    expect(await screen.findByText("Направляющая")).toBeInTheDocument();
    expect(screen.getAllByText("Леман Про").length).toBeGreaterThan(0);
  });
});
