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
      data: [{ id: "sku_1", article: "K-100", name: "Направляющая", category: "Фурнитура", brand: "MAGAMAX", unit: "pcs", active: true, costRub: 125.5, costProductName: "Направляющая из файла" }],
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    useSkuDetailQuery.mockReturnValue({
      data: {
        sku: { id: "sku_1", article: "K-100", name: "Направляющая", category: "Фурнитура", categoryPath: "Магамакс / Фурнитура", brand: "Kerron", unit: "pcs", active: true, costRub: 125.5, costProductName: "Направляющая из файла" },
        sales: [],
        stock: { skuId: "sku_1", freeStock: 120, reservedLike: 20, warehouse: "Щёлково", updatedAt: "2026-04-23T10:00:00Z" },
        inbound: [],
        clientSplit: [],
        reserveSummary: { shortageQtyTotal: 200, affectedClientsCount: 2, avgCoverageMonths: 0.8, worstStatus: "warning", latestRunId: "run_1" },
        cost: { article: "K-100", productName: "Направляющая из файла", costRub: 125.5, uploadFileId: "file_1", sourceRowNumber: 2, updatedAt: "2026-04-27T10:00:00Z" },
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    renderWithProviders(<SkuExplorerPage />, "/sku?sku=sku_1");

    expect(screen.getAllByText("Направляющая").length).toBeGreaterThan(0);
    expect(screen.getByText("K-100 · Магамакс / Фурнитура")).toBeInTheDocument();
    expect(screen.getByText("Общий дефицит")).toBeInTheDocument();
    expect(screen.getAllByText("Себестоимость").length).toBeGreaterThan(0);
    expect(screen.getByText("Направляющая из файла")).toBeInTheDocument();
    expect(screen.queryByText("Справочник себестоимости")).not.toBeInTheDocument();
  });
});
