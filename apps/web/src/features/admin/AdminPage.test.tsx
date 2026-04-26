import { fireEvent, screen } from "@testing-library/react";
import AdminPage from "@/features/admin/AdminPage";
import { renderWithProviders } from "@/test/render";

const useHasCapability = vi.fn();
const useAdminUsersQuery = vi.fn();
const useAdminJobsQuery = vi.fn();
const useAdminAuditEventsQuery = vi.fn();
const useAdminSystemFreshnessQuery = vi.fn();
const useAdminHealthDetailsQuery = vi.fn();
const useExportJobsQuery = vi.fn();
const useUpdateAdminUserRoleMutation = vi.fn();
const useRetryAdminJobMutation = vi.fn();
const useDownloadExportMutation = vi.fn();

vi.mock("@/hooks/queries/use-auth", () => ({
  useHasCapability: (capability: string) => useHasCapability(capability),
}));

vi.mock("@/hooks/queries/use-admin", () => ({
  useAdminUsersQuery: () => useAdminUsersQuery(),
  useAdminJobsQuery: (filters: Record<string, unknown>) => useAdminJobsQuery(filters),
  useAdminAuditEventsQuery: (filters: Record<string, unknown>) => useAdminAuditEventsQuery(filters),
  useAdminSystemFreshnessQuery: () => useAdminSystemFreshnessQuery(),
  useAdminHealthDetailsQuery: () => useAdminHealthDetailsQuery(),
}));

vi.mock("@/hooks/queries/use-exports", () => ({
  useExportJobsQuery: (status?: string) => useExportJobsQuery(status),
}));

vi.mock("@/hooks/mutations/use-admin", () => ({
  useUpdateAdminUserRoleMutation: () => useUpdateAdminUserRoleMutation(),
  useRetryAdminJobMutation: () => useRetryAdminJobMutation(),
}));

vi.mock("@/hooks/mutations/use-exports", () => ({
  useDownloadExportMutation: () => useDownloadExportMutation(),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe("AdminPage", () => {
  beforeEach(() => {
    useHasCapability.mockReset();
    useAdminUsersQuery.mockReset();
    useAdminJobsQuery.mockReset();
    useAdminAuditEventsQuery.mockReset();
    useAdminSystemFreshnessQuery.mockReset();
    useAdminHealthDetailsQuery.mockReset();
    useExportJobsQuery.mockReset();
    useUpdateAdminUserRoleMutation.mockReset();
    useRetryAdminJobMutation.mockReset();
    useDownloadExportMutation.mockReset();
  });

  it("renders richer ops diagnostics and status filters", () => {
    useHasCapability.mockReturnValue(true);
    useAdminUsersQuery.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    });
    useAdminJobsQuery.mockReturnValue({
      data: { items: [], meta: { page: 1, pageSize: 25, total: 0 } },
      isLoading: false,
      error: null,
    });
    useAdminAuditEventsQuery.mockReturnValue({
      data: { items: [], meta: { page: 1, pageSize: 25, total: 0 } },
      isLoading: false,
      error: null,
    });
    useAdminSystemFreshnessQuery.mockReturnValue({
      data: {
        failedJobsCount: 2,
        pendingJobsCount: 1,
        exportBacklogCount: 3,
        failedExportsCount: 1,
        runningExportsCount: 1,
        lastSalesIngestAt: "2026-04-23T10:00:00Z",
        lastStockSnapshotAt: "2026-04-23T10:10:00Z",
        lastInboundUpdateAt: "2026-04-23T10:20:00Z",
        lastQualityRunAt: "2026-04-23T10:30:00Z",
        lastReserveRefreshAt: "2026-04-23T10:40:00Z",
      },
      error: null,
    });
    useAdminHealthDetailsQuery.mockReturnValue({
      data: {
        appEnv: "production",
        appDebug: false,
        appRelease: "2026.04.23-1",
        databaseOk: true,
        redisConfigured: true,
        objectStorageMode: "s3",
        exportRoot: "/data/exports",
        exportAsyncEnabled: true,
        exportAsyncRowThreshold: 500,
        assistantProvider: "deterministic",
        sentryEnabled: true,
        otelEnabled: true,
        startupSchemaMode: "migrations_only",
        startupSeedSampleData: false,
        startupMaterializeAnalytics: false,
        workerQueues: ["ingestion", "analytics", "exports"],
        environmentWarnings: ["Sentry не настроен не должен здесь появиться"],
        requestIdHeader: "X-Request-Id",
        corsOrigins: ["http://127.0.0.1:8090"],
      },
      error: null,
    });
    useExportJobsQuery.mockReturnValue({
      data: { items: [], meta: { page: 1, pageSize: 25, total: 0 } },
      isLoading: false,
      error: null,
    });
    useUpdateAdminUserRoleMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useRetryAdminJobMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useDownloadExportMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });

    renderWithProviders(<AdminPage />, "/admin");

    expect(screen.getByText("Операционные предупреждения")).toBeInTheDocument();
    expect(screen.getByText("Только миграции")).toBeInTheDocument();
    expect(screen.getByText("Загрузка, Аналитика, Экспорты")).toBeInTheDocument();
    expect(screen.getByText("Упавших экспортов")).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "С ошибкой" })[0]!);
    expect(useAdminJobsQuery).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: "failed" }),
    );
  });
});
