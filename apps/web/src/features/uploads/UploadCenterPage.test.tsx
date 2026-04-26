import { fireEvent, screen } from "@testing-library/react";
import UploadCenterPage from "@/features/uploads/UploadCenterPage";
import { renderWithProviders } from "@/test/render";

const useUploadJobsQuery = vi.fn();
const useUploadFileDetailQuery = vi.fn();
const useCreateUploadMutation = vi.fn();
const useValidateUploadMutation = vi.fn();
const useApplyUploadMutation = vi.fn();
const useHasCapability = vi.fn();

vi.mock("@/hooks/queries/use-uploads", () => ({
  useUploadJobsQuery: () => useUploadJobsQuery(),
  useUploadFileDetailQuery: () => useUploadFileDetailQuery(),
  useCreateUploadMutation: () => useCreateUploadMutation(),
  useValidateUploadMutation: () => useValidateUploadMutation(),
  useApplyUploadMutation: () => useApplyUploadMutation(),
}));

vi.mock("@/hooks/queries/use-auth", () => ({
  useHasCapability: () => useHasCapability(),
}));

describe("UploadCenterPage", () => {
  beforeEach(() => {
    useUploadJobsQuery.mockReset();
    useUploadFileDetailQuery.mockReset();
    useCreateUploadMutation.mockReset();
    useValidateUploadMutation.mockReset();
    useApplyUploadMutation.mockReset();
    useHasCapability.mockReset();
    useHasCapability.mockReturnValue(true);
  });

  it("renders upload detail and allows apply action", () => {
    const applyAsync = vi.fn().mockResolvedValue({});

    useUploadJobsQuery.mockReturnValue({
      data: {
        items: [
          {
            id: "file_1",
            fileName: "sales_april.xlsx",
            sourceType: "sales",
            sizeBytes: 2048,
            uploadedAt: "2026-04-23T10:00:00Z",
            state: "ready_to_apply",
            rows: 120,
            issues: 2,
            appliedRows: 0,
            failedRows: 0,
            warningsCount: 1,
          },
        ],
        meta: { page: 1, pageSize: 12, total: 1 },
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    useUploadFileDetailQuery.mockReturnValue({
      data: {
        file: {
          id: "file_1",
          fileName: "sales_april.xlsx",
          sourceType: "sales",
          sizeBytes: 2048,
          uploadedAt: "2026-04-23T10:00:00Z",
          state: "ready_to_apply",
          rows: 120,
          issues: 2,
          appliedRows: 0,
          failedRows: 0,
          warningsCount: 1,
          canApply: true,
          canValidate: true,
        },
        preview: { headers: ["sku"], sampleRows: [], sampleRowCount: 3, fileId: "file_1", sourceType: "sales", detectedSourceType: "sales", parser: "csv", emptyRowCount: 0 },
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    useCreateUploadMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useValidateUploadMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useApplyUploadMutation.mockReturnValue({ mutateAsync: applyAsync, isPending: false });

    renderWithProviders(<UploadCenterPage />, "/uploads?file=file_1");

    expect(screen.getAllByText("sales_april.xlsx").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: /применить/i }));
    expect(applyAsync).toHaveBeenCalledWith("file_1");
  });
});
