import { screen } from "@testing-library/react";
import MappingPage from "@/features/mapping/MappingPage";
import { renderWithProviders } from "@/test/render";

const useUploadJobsQuery = vi.fn();
const useUploadFileDetailQuery = vi.fn();
const useUploadIssuesQuery = vi.fn();
const useMappingTemplatesQuery = vi.fn();
const useSuggestMappingMutation = vi.fn();
const useSaveUploadMappingMutation = vi.fn();
const useValidateUploadMutation = vi.fn();
const useApplyUploadMutation = vi.fn();
const useCreateMappingTemplateMutation = vi.fn();
const useApplyMappingTemplateMutation = vi.fn();

vi.mock("@/hooks/queries/use-uploads", () => ({
  useUploadJobsQuery: () => useUploadJobsQuery(),
  useUploadFileDetailQuery: () => useUploadFileDetailQuery(),
  useUploadIssuesQuery: () => useUploadIssuesQuery(),
  useMappingTemplatesQuery: () => useMappingTemplatesQuery(),
  useSuggestMappingMutation: () => useSuggestMappingMutation(),
  useSaveUploadMappingMutation: () => useSaveUploadMappingMutation(),
  useValidateUploadMutation: () => useValidateUploadMutation(),
  useApplyUploadMutation: () => useApplyUploadMutation(),
  useCreateMappingTemplateMutation: () => useCreateMappingTemplateMutation(),
  useApplyMappingTemplateMutation: () => useApplyMappingTemplateMutation(),
}));

describe("MappingPage", () => {
  beforeEach(() => {
    [
      useUploadJobsQuery,
      useUploadFileDetailQuery,
      useUploadIssuesQuery,
      useMappingTemplatesQuery,
      useSuggestMappingMutation,
      useSaveUploadMappingMutation,
      useValidateUploadMutation,
      useApplyUploadMutation,
      useCreateMappingTemplateMutation,
      useApplyMappingTemplateMutation,
    ].forEach((mocked) => mocked.mockReset());
  });

  it("renders mapping rows and issue state", async () => {
    useUploadJobsQuery.mockReturnValue({
      data: {
        items: [{ id: "file_1", fileName: "sales_april.xlsx" }],
        meta: { page: 1, pageSize: 12, total: 1 },
      },
      error: null,
      refetch: vi.fn(),
    });
    useUploadFileDetailQuery.mockReturnValue({
      data: {
        file: { id: "file_1", fileName: "sales_april.xlsx", sourceType: "sales", uploadedAt: "2026-04-23T10:00:00Z", rows: 10, issues: 1, canValidate: true, canApply: false },
        preview: {
          headers: ["SKU", "Client", "Qty"],
          sampleRows: [{ SKU: "K-100", Client: "Леман Про", Qty: 12 }],
          sampleRowCount: 1,
        },
        mapping: {
          activeMapping: { SKU: "sku_code" },
          suggestions: [
            { source: "SKU", confidence: 0.98, status: "ok", sample: "K-100", candidates: ["sku_code"], required: true },
          ],
          canonicalFields: ["sku_code", "client_name"],
          requiredFields: ["sku_code", "client_name"],
          templateId: null,
        },
        validation: { validRows: 9, failedRows: 1, warningsCount: 0, hasBlockingIssues: true },
        issuesPreview: [{ id: "issue_1", code: "mapping_required", severity: "error", message: "Required canonical field 'client_name' is not mapped", rowNumber: 1 }],
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    useUploadIssuesQuery.mockReturnValue({
      data: {
        items: [{ id: "issue_1", code: "mapping_required", severity: "error", message: "Required canonical field 'client_name' is not mapped", rowNumber: 1 }],
        meta: { page: 1, pageSize: 25, total: 1 },
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    useMappingTemplatesQuery.mockReturnValue({ data: [], error: null });
    [
      useSuggestMappingMutation,
      useSaveUploadMappingMutation,
      useValidateUploadMutation,
      useApplyUploadMutation,
      useCreateMappingTemplateMutation,
      useApplyMappingTemplateMutation,
    ].forEach((mocked) => mocked.mockReturnValue({ mutateAsync: vi.fn(), isPending: false }));

    renderWithProviders(<MappingPage />, "/mapping?file=file_1");

    await screen.findAllByText("SKU");
    expect(screen.getAllByText("SKU").length).toBeGreaterThan(0);
    expect(screen.getByText("Проблемы проверки")).toBeInTheDocument();
  });
});
