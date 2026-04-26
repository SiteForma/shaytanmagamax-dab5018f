import { fireEvent, screen, waitFor } from "@testing-library/react";
import AiConsolePage from "@/features/assistant/AiConsolePage";
import { renderWithProviders } from "@/test/render";

const useAssistantSessionsQuery = vi.fn();
const useAssistantMessagesQuery = vi.fn();
const useAssistantCapabilitiesQuery = vi.fn();
const useAssistantPromptSuggestionsQuery = vi.fn();
const useAssistantContextOptionsQuery = vi.fn();
const useCreateAssistantSessionMutation = vi.fn();
const useAssistantMessageMutation = vi.fn();
const useUpdateAssistantSessionMutation = vi.fn();

vi.mock("@/hooks/queries/use-assistant", () => ({
  useAssistantSessionsQuery: () => useAssistantSessionsQuery(),
  useAssistantMessagesQuery: (sessionId: string | null) => useAssistantMessagesQuery(sessionId),
  useAssistantCapabilitiesQuery: () => useAssistantCapabilitiesQuery(),
  useAssistantPromptSuggestionsQuery: () => useAssistantPromptSuggestionsQuery(),
  useAssistantContextOptionsQuery: () => useAssistantContextOptionsQuery(),
}));

vi.mock("@/hooks/mutations/use-assistant", () => ({
  useCreateAssistantSessionMutation: () => useCreateAssistantSessionMutation(),
  useAssistantMessageMutation: () => useAssistantMessageMutation(),
  useUpdateAssistantSessionMutation: () => useUpdateAssistantSessionMutation(),
}));

describe("AiConsolePage", () => {
  beforeEach(() => {
    useAssistantSessionsQuery.mockReset();
    useAssistantMessagesQuery.mockReset();
    useAssistantCapabilitiesQuery.mockReset();
    useAssistantPromptSuggestionsQuery.mockReset();
    useAssistantContextOptionsQuery.mockReset();
    useCreateAssistantSessionMutation.mockReset();
    useAssistantMessageMutation.mockReset();
    useUpdateAssistantSessionMutation.mockReset();
  });

  function mockBaseQueries() {
    useAssistantCapabilitiesQuery.mockReturnValue({
      data: {
        provider: "deterministic",
        deterministicFallback: true,
        intents: [{ key: "reserve_calculation", label: "Расчёт резерва", supported: true }],
        sessionSupport: true,
        pinnedContextSupport: true,
      },
    });
    useAssistantPromptSuggestionsQuery.mockReturnValue({
      data: [{ id: "prompt_1", label: "Расчёт резерва", prompt: "Рассчитай резерв", intent: "reserve_calculation" }],
    });
    useAssistantContextOptionsQuery.mockReturnValue({
      data: {
        clients: [{ id: "client_1", label: "Леман Про", hint: "СПб" }],
        skus: [{ id: "sku_1", label: "K-2650-CR · Ручка", hint: "Ручки" }],
        uploads: [{ id: "file_1", label: "sales.csv", hint: "applied" }],
        reserveRuns: [{ id: "run_1", label: "run_1 · client_sku_list", hint: "2026-04-23" }],
        categories: [{ id: "cat_1", label: "Ручки", hint: "handles" }],
      },
      error: null,
    });
  }

  it("renders structured assistant response from persisted session", async () => {
    mockBaseQueries();
    useAssistantSessionsQuery.mockReturnValue({
      data: [
        {
          id: "asess_1",
          title: "Резерв по Леман Про",
          status: "active",
          createdAt: "2026-04-23T10:00:00Z",
          updatedAt: "2026-04-23T10:00:00Z",
          lastMessageAt: "2026-04-23T10:05:00Z",
          messageCount: 2,
          pinnedContext: { selectedClientId: "client_1", selectedSkuId: "sku_1", selectedUploadIds: [] },
          lastIntent: "reserve_calculation",
          preferredMode: "deterministic",
          provider: "deterministic",
          latestTraceId: "trace_1",
        },
      ],
      error: null,
    });
    useAssistantMessagesQuery.mockReturnValue({
      data: [
        {
          id: "msg_user",
          sessionId: "asess_1",
          role: "user",
          text: "Рассчитай резерв",
          createdAt: "2026-04-23T10:01:00Z",
          status: "completed",
          context: {},
        },
        {
          id: "msg_assistant",
          sessionId: "asess_1",
          role: "assistant",
          text: "Расчёт готов",
          createdAt: "2026-04-23T10:02:00Z",
          status: "completed",
          context: {},
          response: {
            answerId: "ans_1",
            sessionId: "asess_1",
            intent: "reserve_calculation",
            status: "completed",
            confidence: 0.91,
            title: "Расчёт резерва выполнен",
            summary: "Ниже резерва 2 позиции.",
            sections: [
              {
                id: "sec_1",
                type: "metric_summary",
                title: "Ключевые метрики",
                body: null,
                metrics: [{ key: "shortage", label: "Дефицит", value: "243 шт.", tone: "critical" }],
                rows: [],
                items: [],
              },
            ],
            sourceRefs: [
              {
                sourceType: "reserve_engine",
                sourceLabel: "Reserve Run run_1",
                entityType: "reserve_run",
                entityId: "run_1",
                role: "primary",
                route: "/reserve?run=run_1",
                detail: "2 строки расчёта",
              },
            ],
            toolCalls: [
              {
                toolName: "calculate_reserve",
                status: "completed",
                arguments: { client_id: "client_1", sku_ids: ["sku_1"] },
                summary: "Инструмент выполнил расчёт по 2 строкам",
                latencyMs: 42,
              },
            ],
            followups: [{ id: "f_1", label: "Показать critical", prompt: "Покажи critical", action: "query" }],
            warnings: [],
            createdAt: "2026-04-23T10:02:00Z",
            provider: "deterministic",
            traceId: "trace_1",
            contextUsed: {},
          },
        },
      ],
      error: null,
    });
    useCreateAssistantSessionMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useUpdateAssistantSessionMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null });
    const mutateAsync = vi.fn().mockResolvedValue({});
    useAssistantMessageMutation.mockReturnValue({ mutateAsync, isPending: false, error: null });

    renderWithProviders(<AiConsolePage />, "/ai?session=asess_1");

    expect(await screen.findByText("Расчёт резерва выполнен")).toBeInTheDocument();
    expect(screen.getByText("Reserve Run run_1")).toBeInTheDocument();
    expect(screen.getByText("Трассировка и вызовы инструментов")).toBeInTheDocument();
    expect(screen.getByText("calculate_reserve")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Показать critical"));
    await waitFor(() =>
      expect(mutateAsync).toHaveBeenCalledWith({
        sessionId: "asess_1",
        payload: expect.objectContaining({ text: "Покажи critical" }),
      }),
    );
  });

  it("creates a new session before sending the first question", async () => {
    mockBaseQueries();
    useAssistantSessionsQuery.mockReturnValue({ data: [], error: null });
    useAssistantMessagesQuery.mockReturnValue({ data: [], error: null });
    const createMutateAsync = vi.fn().mockResolvedValue({
      id: "asess_2",
      title: "Новая сессия",
      status: "active",
      createdAt: "2026-04-23T10:00:00Z",
      updatedAt: "2026-04-23T10:00:00Z",
      lastMessageAt: null,
      messageCount: 0,
      pinnedContext: {},
      preferredMode: "deterministic",
      provider: "deterministic",
    });
    const messageMutateAsync = vi.fn().mockResolvedValue({});
    useCreateAssistantSessionMutation.mockReturnValue({
      mutateAsync: createMutateAsync,
      isPending: false,
    });
    useUpdateAssistantSessionMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null });
    useAssistantMessageMutation.mockReturnValue({
      mutateAsync: messageMutateAsync,
      isPending: false,
      error: null,
    });

    renderWithProviders(<AiConsolePage />, "/ai");

    fireEvent.change(screen.getByPlaceholderText(/спросите о резерве/i), {
      target: { value: "Покажи текущий дефицит" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Отправить запрос" }).closest("form")!);

    await waitFor(() => expect(createMutateAsync).toHaveBeenCalled());
    await waitFor(() =>
      expect(messageMutateAsync).toHaveBeenCalledWith({
        sessionId: "asess_2",
        payload: expect.objectContaining({ text: "Покажи текущий дефицит" }),
      }),
    );
  });

  it("renames and archives a session from the rail", async () => {
    mockBaseQueries();
    const updateMutateAsync = vi.fn().mockResolvedValue({});
    useAssistantSessionsQuery.mockReturnValue({
      data: [
        {
          id: "asess_1",
          title: "Черновик",
          status: "active",
          createdAt: "2026-04-23T10:00:00Z",
          updatedAt: "2026-04-23T10:00:00Z",
          lastMessageAt: "2026-04-23T10:05:00Z",
          messageCount: 2,
          pinnedContext: { selectedClientId: "client_1", selectedSkuId: null, selectedUploadIds: [] },
          lastIntent: "reserve_calculation",
          preferredMode: "deterministic",
          provider: "deterministic",
          latestTraceId: "trace_1",
        },
      ],
      error: null,
    });
    useAssistantMessagesQuery.mockReturnValue({ data: [], error: null });
    useCreateAssistantSessionMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useAssistantMessageMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null });
    useUpdateAssistantSessionMutation.mockReturnValue({
      mutateAsync: updateMutateAsync,
      isPending: false,
      error: null,
    });

    renderWithProviders(<AiConsolePage />, "/ai?session=asess_1");

    fireEvent.click(await screen.findByText("Переименовать"));
    fireEvent.change(screen.getByDisplayValue("Черновик"), {
      target: { value: "Сессия по Леман Про" },
    });
    fireEvent.click(screen.getByText("Сохранить"));

    await waitFor(() =>
      expect(updateMutateAsync).toHaveBeenCalledWith({
        sessionId: "asess_1",
        payload: { title: "Сессия по Леман Про" },
      }),
    );

    fireEvent.click(screen.getByText("В архив"));

    await waitFor(() =>
      expect(updateMutateAsync).toHaveBeenCalledWith({
        sessionId: "asess_1",
        payload: { status: "archived" },
      }),
    );
  });
});
