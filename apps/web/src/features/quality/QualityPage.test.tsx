import { fireEvent, screen } from "@testing-library/react";
import QualityPage from "@/features/quality/QualityPage";
import { renderWithProviders } from "@/test/render";

const useQualityIssuesQuery = vi.fn();

vi.mock("@/hooks/queries/use-quality", () => ({
  useQualityIssuesQuery: () => useQualityIssuesQuery(),
}));

describe("QualityPage", () => {
  beforeEach(() => {
    useQualityIssuesQuery.mockReset();
  });

  it("renders issue list and opens detail drawer", () => {
    useQualityIssuesQuery.mockReturnValue({
      data: {
        items: [
          {
            id: "issue_1",
            type: "missing_sku",
            severity: "error",
            entity: "sales:sku_001",
            description: "SKU referenced in sales not present in master",
            detectedAt: "2026-04-23T10:00:00Z",
            source: "sales_april.xlsx",
          },
        ],
        meta: { page: 1, pageSize: 20, total: 1 },
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    renderWithProviders(<QualityPage />, "/quality");

    fireEvent.click(screen.getByText("sales:sku_001"));
    expect(screen.getByText("sales_april.xlsx")).toBeInTheDocument();
    expect(screen.getAllByText(/SKU из продаж отсутствует в мастер-каталоге/i).length).toBeGreaterThan(0);
  });
});
