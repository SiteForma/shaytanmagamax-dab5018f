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
const useDeleteAssistantSessionMutation = vi.fn();

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
  useDeleteAssistantSessionMutation: () => useDeleteAssistantSessionMutation(),
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
    useDeleteAssistantSessionMutation.mockReset();
  });

  function mockBaseQueries() {
    useAssistantCapabilitiesQuery.mockReturnValue({
      data: {
        provider: "deterministic",
        deterministicFallback: true,
        intents: [
          { key: "free_chat", label: "MAGAMAX AI", supported: true },
          { key: "reserve_calculation", label: "Расчёт резерва", supported: true },
        ],
        sessionSupport: true,
        pinnedContextSupport: true,
      },
    });
    useAssistantPromptSuggestionsQuery.mockReturnValue({
      data: [
        { id: "prompt_0", label: "Возможности консоли", prompt: "Что ты умеешь?", intent: "free_chat" },
        { id: "prompt_1", label: "Расчёт резерва", prompt: "Рассчитай резерв", intent: "reserve_calculation" },
      ],
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
          estimatedCostRub: 12,
          tokenUsage: {
            inputTokens: 12000,
            outputTokens: 3000,
            totalTokens: 15000,
            estimatedCostUsd: 0.04,
            estimatedCostRub: 12,
          },
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
    useDeleteAssistantSessionMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null });
    const mutateAsync = vi.fn().mockResolvedValue({});
    useAssistantMessageMutation.mockReturnValue({ mutateAsync, isPending: false, error: null });

    renderWithProviders(<AiConsolePage />, "/ai?session=asess_1");

    expect(await screen.findByText("Ниже резерва 2 позиции.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Расчёт резерва выполнен" })).not.toBeInTheDocument();
    expect(screen.getByText("2 сообщений: 12 руб.")).toBeInTheDocument();
    expect(screen.getByText("Reserve Run run_1")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /подробнее/i }));

    expect(await screen.findByRole("heading", { name: "Подробнее" })).toBeInTheDocument();
    expect(screen.getAllByText("Reserve Run run_1").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Трассировка и вызовы инструментов")).toBeInTheDocument();
    expect(screen.getByText("calculate_reserve")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Показать critical"));
    await waitFor(() =>
      expect(mutateAsync).toHaveBeenCalledWith(expect.objectContaining({
        sessionId: "asess_1",
        payload: expect.objectContaining({ text: "Покажи critical" }),
      })),
    );
  });

  it("hides generic free-chat heading and shows MAGAMAX AI label", async () => {
    mockBaseQueries();
    useAssistantSessionsQuery.mockReturnValue({
      data: [
        {
          id: "asess_free",
          title: "Новая сессия",
          status: "active",
          createdAt: "2026-04-23T10:00:00Z",
          updatedAt: "2026-04-23T10:00:00Z",
          lastMessageAt: "2026-04-23T10:05:00Z",
          messageCount: 1,
          pinnedContext: {},
          lastIntent: "free_chat",
          preferredMode: "deterministic",
          provider: "deterministic",
        },
      ],
      error: null,
    });
    useAssistantMessagesQuery.mockReturnValue({
      data: [
        {
          id: "msg_assistant_free",
          sessionId: "asess_free",
          role: "assistant",
          text: "Можно писать свободно.",
          createdAt: "2026-04-23T10:02:00Z",
          status: "completed",
          context: {},
          response: {
            answerId: "ans_free",
            sessionId: "asess_free",
            intent: "free_chat",
            status: "completed",
            confidence: 0.68,
            title: "Доменный чат MAGAMAX",
            summary: "Можно писать свободно, но только в контуре MAGAMAX.",
            sections: [],
            sourceRefs: [],
            toolCalls: [],
            followups: [],
            warnings: [],
            createdAt: "2026-04-23T10:02:00Z",
            provider: "deterministic",
            traceId: "trace_free",
            contextUsed: {},
          },
        },
      ],
      error: null,
    });
    useCreateAssistantSessionMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useUpdateAssistantSessionMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null });
    useDeleteAssistantSessionMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null });
    useAssistantMessageMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null });

    renderWithProviders(<AiConsolePage />, "/ai?session=asess_free");

    expect(await screen.findByText("MAGAMAX AI")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Доменный чат MAGAMAX" })).not.toBeInTheDocument();
    expect(screen.getByText("Можно писать свободно, но только в контуре MAGAMAX.")).toBeInTheDocument();
  });

  it("renders clarification fields and chips inline", async () => {
    mockBaseQueries();
    useAssistantSessionsQuery.mockReturnValue({
      data: [
        {
          id: "asess_clarify",
          title: "Уточнение",
          status: "active",
          createdAt: "2026-04-23T10:00:00Z",
          updatedAt: "2026-04-23T10:00:00Z",
          lastMessageAt: "2026-04-23T10:05:00Z",
          messageCount: 1,
          pinnedContext: {},
          lastIntent: "reserve_calculation",
          preferredMode: "deterministic",
          provider: "deterministic",
        },
      ],
      error: null,
    });
    useAssistantMessagesQuery.mockReturnValue({
      data: [
        {
          id: "msg_clarify",
          sessionId: "asess_clarify",
          role: "assistant",
          text: "По какому клиенту посчитать резерв?",
          createdAt: "2026-04-23T10:02:00Z",
          status: "needs_clarification",
          context: {},
          response: {
            answerId: "ans_clarify",
            sessionId: "asess_clarify",
            type: "clarification",
            intent: "reserve_calculation",
            status: "needs_clarification",
            confidence: 0.62,
            title: "Нужно уточнение",
            summary: "По какому клиенту посчитать резерв?",
            sections: [],
            sourceRefs: [],
            toolCalls: [],
            followups: [],
            warnings: [],
            createdAt: "2026-04-23T10:02:00Z",
            provider: "deterministic",
            traceId: "trace_clarify",
            contextUsed: {},
            missingFields: [{ name: "client_id", label: "клиент", question: "По какому клиенту?" }],
            suggestedChips: ["OBI Россия", "Леман Про"],
            pendingIntent: "reserve_calculation",
          },
        },
      ],
      error: null,
    });
    const mutateAsync = vi.fn().mockResolvedValue({});
    useCreateAssistantSessionMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useUpdateAssistantSessionMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null });
    useDeleteAssistantSessionMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null });
    useAssistantMessageMutation.mockReturnValue({ mutateAsync, isPending: false, error: null });

    renderWithProviders(<AiConsolePage />, "/ai?session=asess_clarify");

    expect(await screen.findByText("По какому клиенту посчитать резерв?")).toBeInTheDocument();
    expect(screen.getByText("Нужно уточнение")).toBeInTheDocument();
    expect(screen.getByText("Не хватает: клиент")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "OBI Россия" }));
    await waitFor(() =>
      expect(mutateAsync).toHaveBeenCalledWith(expect.objectContaining({
        sessionId: "asess_clarify",
        payload: expect.objectContaining({ text: "OBI Россия" }),
      })),
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
    useDeleteAssistantSessionMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null });
    useAssistantMessageMutation.mockReturnValue({
      mutateAsync: messageMutateAsync,
      isPending: false,
      error: null,
    });

    renderWithProviders(<AiConsolePage />, "/ai");

    fireEvent.change(screen.getByPlaceholderText(/напишите сообщение/i), {
      target: { value: "Покажи текущий дефицит" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Отправить запрос" }).closest("form")!);

    await waitFor(() => expect(createMutateAsync).toHaveBeenCalled());
    await waitFor(() =>
      expect(messageMutateAsync).toHaveBeenCalledWith(expect.objectContaining({
        sessionId: "asess_2",
        payload: expect.objectContaining({ text: "Покажи текущий дефицит" }),
      })),
    );
  });

  it("opens context controls in a side drawer", async () => {
    mockBaseQueries();
    useAssistantSessionsQuery.mockReturnValue({ data: [], error: null });
    useAssistantMessagesQuery.mockReturnValue({ data: [], error: null });
    useCreateAssistantSessionMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useUpdateAssistantSessionMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null });
    useDeleteAssistantSessionMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null });
    useAssistantMessageMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null });

    renderWithProviders(<AiConsolePage />, "/ai");

    expect(screen.queryByText("Контекст ИИ-консоли")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Открыть контекст ИИ-консоли" }));

    expect(await screen.findByText("Контекст ИИ-консоли")).toBeInTheDocument();
    expect(screen.getByText("Клиент")).toBeInTheDocument();
    expect(screen.getByText("SKU")).toBeInTheDocument();
  });

  it("shows branded rotating generation indicator while answer is pending", async () => {
    mockBaseQueries();
    useAssistantSessionsQuery.mockReturnValue({ data: [], error: null });
    useAssistantMessagesQuery.mockReturnValue({ data: [], error: null });
    useCreateAssistantSessionMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useUpdateAssistantSessionMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null });
    useDeleteAssistantSessionMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null });
    useAssistantMessageMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: true, error: null });

    renderWithProviders(<AiConsolePage />, "/ai");

    expect(await screen.findByRole("status")).toHaveTextContent("Формирую ответ");
    expect(screen.getByRole("status")).toHaveTextContent("MAGAMAX AI");
  });

  it("renames and deletes a session from hover rail actions", async () => {
    mockBaseQueries();
    const updateMutateAsync = vi.fn().mockResolvedValue({});
    const deleteMutateAsync = vi.fn().mockResolvedValue(undefined);
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
    useDeleteAssistantSessionMutation.mockReturnValue({
      mutateAsync: deleteMutateAsync,
      isPending: false,
      error: null,
    });

    renderWithProviders(<AiConsolePage />, "/ai?session=asess_1");

    expect(screen.queryByText("Переименовать")).not.toBeInTheDocument();
    expect(screen.queryByText("В историю")).not.toBeInTheDocument();

    fireEvent.click(await screen.findByRole("button", { name: "Переименовать чат" }));
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

    fireEvent.click(screen.getByRole("button", { name: "Удалить чат" }));

    await waitFor(() => expect(deleteMutateAsync).toHaveBeenCalledWith("asess_1"));
  });
});
