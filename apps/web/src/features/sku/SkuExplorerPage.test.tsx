import { screen } from "@testing-library/react";
import SkuExplorerPage from "@/features/sku/SkuExplorerPage";
import { renderWithProviders } from "@/test/render";

const useSkusQuery = vi.fn();
const useSkuDetailQuery = vi.fn();

vi.mock("@/hooks/queries/use-sku", () => ({
  useSkusQuery: () => useSkusQuery(),
  useSkuDetailQuery: () => useSkuDetailQuery(),
}));

describe("SkuExplorerPage", () => {
  beforeEach(() => {
    useSkusQuery.mockReset();
    useSkuDetailQuery.mockReset();
  });

  it("renders sku detail drawer from real API-shaped data", () => {
    useSkusQuery.mockReturnValue({
      data: [{ id: "sku_1", article: "K-100", name: "Направляющая", category: "Фурнитура", brand: "MAGAMAX", unit: "pcs", active: true }],
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    useSkuDetailQuery.mockReturnValue({
      data: {
        sku: { id: "sku_1", article: "K-100", name: "Направляющая", category: "Фурнитура", brand: "MAGAMAX", unit: "pcs", active: true },
        sales: [],
        stock: { skuId: "sku_1", freeStock: 120, reservedLike: 20, warehouse: "Щёлково", updatedAt: "2026-04-23T10:00:00Z" },
        inbound: [],
        clientSplit: [],
        reserveSummary: { shortageQtyTotal: 200, affectedClientsCount: 2, avgCoverageMonths: 0.8, worstStatus: "warning", latestRunId: "run_1" },
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    renderWithProviders(<SkuExplorerPage />, "/sku?sku=sku_1");

    expect(screen.getAllByText("Направляющая").length).toBeGreaterThan(0);
    expect(screen.getByText("K-100 · Фурнитура")).toBeInTheDocument();
    expect(screen.getByText("Общий дефицит")).toBeInTheDocument();
  });
});
