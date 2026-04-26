import { fireEvent, screen, waitFor } from "@testing-library/react";
import ClientsPage from "@/features/clients/ClientsPage";
import { renderWithProviders } from "@/test/render";

const useClientsQuery = vi.fn();
const useClientDetailQuery = vi.fn();
const useClientTopSkusQuery = vi.fn();
const useClientCategoryExposureQuery = vi.fn();
const useHasCapability = vi.fn();
const useClientExposureExportMutation = vi.fn();
const useDiyExposureReportPackExportMutation = vi.fn();

vi.mock("@/hooks/queries/use-clients", () => ({
  useClientsQuery: () => useClientsQuery(),
  useClientDetailQuery: (clientId: string | null) => useClientDetailQuery(clientId),
  useClientTopSkusQuery: (clientId: string | null) => useClientTopSkusQuery(clientId),
  useClientCategoryExposureQuery: (clientId: string | null) => useClientCategoryExposureQuery(clientId),
}));

vi.mock("@/hooks/queries/use-auth", () => ({
  useHasCapability: (capability: string) => useHasCapability(capability),
}));

vi.mock("@/hooks/mutations/use-exports", () => ({
  useClientExposureExportMutation: () => useClientExposureExportMutation(),
  useDiyExposureReportPackExportMutation: () => useDiyExposureReportPackExportMutation(),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe("ClientsPage", () => {
  beforeEach(() => {
    useClientsQuery.mockReset();
    useClientDetailQuery.mockReset();
    useClientTopSkusQuery.mockReset();
    useClientCategoryExposureQuery.mockReset();
    useHasCapability.mockReset();
    useClientExposureExportMutation.mockReset();
    useDiyExposureReportPackExportMutation.mockReset();
  });

  it("renders export actions and triggers both DIY export flows", async () => {
    const clientExposureMutateAsync = vi.fn().mockResolvedValue({ id: "exp_1", canDownload: true });
    const reportPackMutateAsync = vi.fn().mockResolvedValue({ id: "exp_2", canDownload: false });

    useClientsQuery.mockReturnValue({
      data: [
        {
          id: "client_1",
          name: "Леман Про",
          region: "ЦФО",
          reserveMonths: 3,
          positionsTracked: 12,
          criticalPositions: 2,
          shortageQty: 180,
          coverageMonths: 1.2,
          expectedInboundRelief: 50,
        },
      ],
      isLoading: false,
      error: null,
    });
    useClientDetailQuery.mockReturnValue({ data: null, isLoading: false, error: null });
    useClientTopSkusQuery.mockReturnValue({ data: [], isLoading: false, error: null });
    useClientCategoryExposureQuery.mockReturnValue({ data: [], isLoading: false, error: null });
    useHasCapability.mockReturnValue(true);
    useClientExposureExportMutation.mockReturnValue({ mutateAsync: clientExposureMutateAsync, isPending: false });
    useDiyExposureReportPackExportMutation.mockReturnValue({ mutateAsync: reportPackMutateAsync, isPending: false });

    renderWithProviders(<ClientsPage />, "/clients");

    fireEvent.click(screen.getByRole("button", { name: /экспорт экспозиции/i }));
    fireEvent.click(screen.getByRole("button", { name: /отчётный пакет diy/i }));

    await waitFor(() => expect(clientExposureMutateAsync).toHaveBeenCalledWith("xlsx"));
    await waitFor(() => expect(reportPackMutateAsync).toHaveBeenCalledWith());
    expect(screen.getByText("Леман Про")).toBeInTheDocument();
  });
});
