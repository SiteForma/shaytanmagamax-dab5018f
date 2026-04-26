import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Archive,
  ArchiveRestore,
  ArrowUp,
  Bot,
  Boxes,
  Building2,
  Check,
  FileText,
  Layers,
  PencilLine,
  Plus,
  ShieldAlert,
  Sparkles,
  Wrench,
  X,
} from "lucide-react";
import { PageHeader, SectionTitle } from "@/components/ui-ext/PageHeader";
import { QueryErrorState } from "@/components/ui-ext/QueryErrorState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type {
  AssistantMessage,
  AssistantPinnedContext,
  AssistantResponse,
  AssistantSection,
  AssistantSession,
} from "@/types";
import {
  useAssistantCapabilitiesQuery,
  useAssistantContextOptionsQuery,
  useAssistantMessagesQuery,
  useAssistantPromptSuggestionsQuery,
  useAssistantSessionsQuery,
} from "@/hooks/queries/use-assistant";
import {
  useAssistantMessageMutation,
  useCreateAssistantSessionMutation,
  useUpdateAssistantSessionMutation,
} from "@/hooks/mutations/use-assistant";

function buildContext(
  selectedClientId: string,
  selectedSkuId: string,
  selectedFileId: string,
  selectedCategoryId: string,
  selectedRunId: string,
): AssistantPinnedContext {
  return {
    selectedClientId: selectedClientId || null,
    selectedSkuId: selectedSkuId || null,
    selectedUploadIds: selectedFileId ? [selectedFileId] : [],
    selectedCategoryId: selectedCategoryId || null,
    selectedReserveRunId: selectedRunId || null,
  };
}

const ASSISTANT_COLUMN_LABELS: Record<string, string> = {
  article: "Артикул",
  clientName: "Клиент",
  productName: "Товар",
  shortageQty: "Дефицит",
  coverageMonths: "Покрытие",
  status: "Статус",
  eta: "ETA",
  reserveImpact: "Влияние на резерв",
  fileName: "Файл",
  rows: "Строки",
  issues: "Проблемы",
  type: "Тип",
  severity: "Критичность",
  entity: "Сущность",
  source: "Источник",
  share: "Доля",
};

function formatAssistantCell(column: string, value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  if (column === "status") {
    return (
      {
        critical: "Критично",
        warning: "Предупреждение",
        healthy: "В норме",
        no_history: "Без истории",
        inactive: "Неактивно",
        overstocked: "Избыточно",
      }[String(value)] ?? String(value)
    );
  }
  return String(value);
}

function formatToolStatus(status: string) {
  return (
    {
      completed: "выполнен",
      failed: "ошибка",
      skipped: "пропущен",
    }[status] ?? status
  );
}

function formatToolArgument(value: unknown) {
  if (value === null || value === undefined) return "—";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "—";
  if (typeof value === "boolean") return value ? "Да" : "Нет";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function ResponseSection({ section }: { section: AssistantSection }) {
  if (section.type === "metric_summary") {
    return (
      <section className="space-y-3">
        <SectionTitle>{section.title}</SectionTitle>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {section.metrics.map((metric) => (
            <div
              key={metric.key}
              className={cn(
                "rounded-xl border px-3 py-3",
                metric.tone === "critical"
                  ? "border-danger/40 bg-danger/10"
                  : metric.tone === "warning"
                    ? "border-warning/40 bg-warning/10"
                    : metric.tone === "positive"
                      ? "border-success/40 bg-success/10"
                      : "border-line-subtle bg-surface-muted/50",
              )}
            >
              <div className="text-[11px] uppercase tracking-[0.12em] text-ink-muted">{metric.label}</div>
              <div className="mt-1 text-lg font-semibold text-ink">{metric.value}</div>
            </div>
          ))}
        </div>
      </section>
    );
  }

  if (section.type === "reserve_table_preview" && section.rows.length) {
    const columns = Object.keys(section.rows[0]);
    return (
      <section className="space-y-3">
        <SectionTitle>{section.title}</SectionTitle>
        <div className="overflow-hidden rounded-xl border border-line-subtle">
          <div
            className="grid bg-surface-muted/60 px-3 py-2 text-[11px] uppercase tracking-[0.12em] text-ink-muted"
            style={{ gridTemplateColumns: `repeat(${columns.length}, minmax(0, 1fr))` }}
          >
            {columns.map((column) => (
              <div key={column}>{ASSISTANT_COLUMN_LABELS[column] ?? column}</div>
            ))}
          </div>
          <div className="divide-y divide-line-subtle">
            {section.rows.map((row, index) => (
              <div
                key={`${section.id}-${index}`}
                className="grid px-3 py-3 text-sm text-ink-secondary"
                style={{ gridTemplateColumns: `repeat(${columns.length}, minmax(0, 1fr))` }}
              >
                {columns.map((column) => (
                  <div key={column} className={cn(column.toLowerCase().includes("qty") && "text-num")}>
                    {formatAssistantCell(column, row[column])}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </section>
    );
  }

  if ((section.type === "warning_block" || section.type === "next_actions" || section.items.length) && section.items.length) {
    return (
      <section className="space-y-3">
        <SectionTitle>{section.title}</SectionTitle>
        <div className="rounded-xl border border-line-subtle bg-surface-muted/50 px-4 py-3">
          <ul className="space-y-2 text-sm text-ink-secondary">
            {section.items.map((item, index) => (
              <li key={`${section.id}-${index}`}>{item}</li>
            ))}
          </ul>
        </div>
      </section>
    );
  }

  return (
    <section className="space-y-3">
      <SectionTitle>{section.title}</SectionTitle>
      <div className="rounded-xl border border-line-subtle bg-surface-muted/50 px-4 py-3 text-sm leading-relaxed text-ink-secondary">
        {section.body ?? "—"}
      </div>
    </section>
  );
}

function AssistantResponseCard({
  response,
  onFollowup,
}: {
  response: AssistantResponse;
  onFollowup: (prompt: string) => void;
}) {
  return (
    <article className="panel animate-fade-in space-y-5 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">Ответ</div>
          <h3 className="mt-1 text-base font-semibold text-ink">{response.title}</h3>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-ink-secondary">{response.summary}</p>
        </div>
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.12em] text-ink-muted">
          <span className="rounded-full border border-line-subtle px-2 py-1">{response.provider}</span>
          <span className="rounded-full border border-line-subtle px-2 py-1">
            уверенность {Math.round(response.confidence * 100)}%
          </span>
          <span className="rounded-full border border-line-subtle px-2 py-1">
            trace {response.traceId.slice(0, 8)}
          </span>
        </div>
      </div>

      {response.sections.map((section) => (
        <ResponseSection key={section.id} section={section} />
      ))}

      {response.toolCalls.length ? (
        <details className="rounded-xl border border-line-subtle bg-surface-muted/30 px-4 py-3">
          <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium text-ink">
            <Wrench className="h-4 w-4 text-brand" />
            Трассировка и вызовы инструментов
          </summary>
          <div className="mt-4 space-y-3">
            {response.toolCalls.map((tool, index) => (
              <div
                key={`${tool.toolName}-${index}`}
                className="rounded-xl border border-line-subtle bg-surface-panel/80 px-3 py-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-sm font-medium text-ink">{tool.toolName}</div>
                  <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.12em] text-ink-muted">
                    <span className="rounded-full border border-line-subtle px-2 py-1">
                      {formatToolStatus(tool.status)}
                    </span>
                    <span className="rounded-full border border-line-subtle px-2 py-1">{tool.latencyMs} ms</span>
                  </div>
                </div>
                <p className="mt-2 text-sm text-ink-secondary">{tool.summary}</p>
                {Object.keys(tool.arguments ?? {}).length ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {Object.entries(tool.arguments).map(([key, value]) => (
                      <span
                        key={key}
                        className="rounded-md border border-line-subtle bg-surface-muted/60 px-2 py-1 text-xs text-ink-secondary"
                      >
                        {key}: {formatToolArgument(value)}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </details>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <section>
          <SectionTitle>Источники данных</SectionTitle>
          <ul className="mt-3 space-y-2">
            {response.sourceRefs.map((source) => (
              <li
                key={`${source.sourceType}-${source.entityId ?? source.sourceLabel}`}
                className="rounded-xl border border-line-subtle bg-surface-muted/40 px-3 py-3 text-sm"
              >
                <div className="flex items-center gap-2 text-ink">
                  <FileText className="h-3.5 w-3.5 text-brand" />
                  {source.route ? (
                    <Link to={source.route} className="font-medium hover:text-brand">
                      {source.sourceLabel}
                    </Link>
                  ) : (
                    <span className="font-medium">{source.sourceLabel}</span>
                  )}
                </div>
                <div className="mt-1 text-xs text-ink-muted">
                  {source.detail ?? source.sourceType}
                  {source.freshnessAt ? ` · ${source.freshnessAt}` : ""}
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section>
          <SectionTitle>Следующие шаги</SectionTitle>
          <div className="mt-3 flex flex-wrap gap-2">
            {response.followups.map((followup) =>
              followup.action === "open" && followup.route ? (
                <Link
                  key={followup.id}
                  to={followup.route}
                  className="rounded-md border border-line-subtle bg-surface-muted/60 px-2.5 py-1.5 text-xs text-ink-secondary transition-colors hover:bg-surface-hover hover:text-ink"
                >
                  {followup.label}
                </Link>
              ) : (
                <button
                  key={followup.id}
                  onClick={() => onFollowup(followup.prompt)}
                  className="rounded-md border border-line-subtle bg-surface-muted/60 px-2.5 py-1.5 text-xs text-ink-secondary transition-colors hover:bg-surface-hover hover:text-ink"
                >
                  {followup.label}
                </button>
              ),
            )}
          </div>
          {response.warnings.length ? (
            <div className="mt-4 rounded-xl border border-warning/40 bg-warning/10 px-3 py-3">
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.12em] text-warning">
                <ShieldAlert className="h-3.5 w-3.5" /> Ограничения
              </div>
              <ul className="mt-2 space-y-1 text-sm text-ink-secondary">
                {response.warnings.map((warning) => (
                  <li key={warning.code}>{warning.message}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>
      </div>
    </article>
  );
}

function SessionRail({
  sessions,
  sessionId,
  onSelect,
  onNew,
  onRename,
  onArchiveToggle,
  isCreating,
  isUpdating,
}: {
  sessions: AssistantSession[];
  sessionId: string | null;
  onSelect: (sessionId: string) => void;
  onNew: () => void;
  onRename: (sessionId: string, title: string) => void;
  onArchiveToggle: (session: AssistantSession) => void;
  isCreating: boolean;
  isUpdating: boolean;
}) {
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const activeSessions = sessions.filter((session) => session.status !== "archived");
  const archivedSessions = sessions.filter((session) => session.status === "archived");

  return (
    <aside className="space-y-3">
      <div className="flex items-center justify-between">
        <SectionTitle>Сессии</SectionTitle>
        <Button size="sm" variant="outline" className="h-8" onClick={onNew} disabled={isCreating}>
          <Plus className="mr-1 h-3.5 w-3.5" /> Новая
        </Button>
      </div>
      <div className="space-y-2">
        {sessions.length === 0 ? (
          <div className="panel p-4 text-sm text-ink-muted">История пока пуста. Первый вопрос создаст сохранённую сессию.</div>
        ) : (
          <>
            {activeSessions.map((session) => (
              <div
                key={session.id}
                className={cn(
                  "panel p-4 transition-colors",
                  session.id === sessionId && "border-brand/60 bg-brand/10",
                )}
              >
                {editingSessionId === session.id ? (
                  <div className="space-y-3">
                    <Input
                      value={editingTitle}
                      onChange={(event) => setEditingTitle(event.target.value)}
                      className="h-9"
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        className="h-8 bg-brand text-brand-foreground hover:bg-brand-hover"
                        onClick={() => {
                          onRename(session.id, editingTitle);
                          setEditingSessionId(null);
                        }}
                        disabled={isUpdating}
                      >
                        <Check className="mr-1 h-3.5 w-3.5" /> Сохранить
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-8"
                        onClick={() => {
                          setEditingSessionId(null);
                          setEditingTitle("");
                        }}
                      >
                        <X className="mr-1 h-3.5 w-3.5" /> Отмена
                      </Button>
                    </div>
                  </div>
                ) : (
                  <>
                    <button onClick={() => onSelect(session.id)} className="w-full text-left">
                      <div className="text-sm font-medium text-ink">{session.title}</div>
                      <div className="mt-2 flex items-center gap-2 text-[11px] uppercase tracking-[0.12em] text-ink-muted">
                        <span>{session.messageCount} сообщений</span>
                        <span>{session.provider}</span>
                      </div>
                      <div className="mt-1 text-xs text-ink-muted">{session.lastMessageAt ?? session.createdAt}</div>
                    </button>
                    <div className="mt-3 flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-8"
                        onClick={() => {
                          setEditingSessionId(session.id);
                          setEditingTitle(session.title);
                        }}
                        disabled={isUpdating}
                      >
                        <PencilLine className="mr-1 h-3.5 w-3.5" /> Переименовать
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-8"
                        onClick={() => onArchiveToggle(session)}
                        disabled={isUpdating}
                      >
                        <Archive className="mr-1 h-3.5 w-3.5" /> В архив
                      </Button>
                    </div>
                  </>
                )}
              </div>
            ))}

            {archivedSessions.length ? (
              <div className="space-y-2 pt-2">
                <div className="px-1 text-[11px] uppercase tracking-[0.12em] text-ink-muted">Архив</div>
                {archivedSessions.map((session) => (
                  <div key={session.id} className="panel p-4 opacity-80">
                    <button onClick={() => onSelect(session.id)} className="w-full text-left">
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-sm font-medium text-ink">{session.title}</div>
                        <span className="rounded-full border border-line-subtle px-2 py-1 text-[10px] uppercase tracking-[0.12em] text-ink-muted">
                          архив
                        </span>
                      </div>
                      <div className="mt-2 text-xs text-ink-muted">{session.lastMessageAt ?? session.createdAt}</div>
                    </button>
                    <div className="mt-3">
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-8"
                        onClick={() => onArchiveToggle(session)}
                        disabled={isUpdating}
                      >
                        <ArchiveRestore className="mr-1 h-3.5 w-3.5" /> Вернуть
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
          </>
        )}
      </div>
    </aside>
  );
}

export default function AiConsolePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const sessionId = searchParams.get("session");
  const [draft, setDraft] = useState("");
  const [selectedClientId, setSelectedClientId] = useState("");
  const [selectedSkuId, setSelectedSkuId] = useState("");
  const [selectedFileId, setSelectedFileId] = useState("");
  const [selectedCategoryId, setSelectedCategoryId] = useState("");
  const [selectedRunId, setSelectedRunId] = useState("");

  const sessionsQuery = useAssistantSessionsQuery();
  const messagesQuery = useAssistantMessagesQuery(sessionId);
  const capabilitiesQuery = useAssistantCapabilitiesQuery();
  const suggestionsQuery = useAssistantPromptSuggestionsQuery();
  const contextOptionsQuery = useAssistantContextOptionsQuery();
  const createSessionMutation = useCreateAssistantSessionMutation();
  const messageMutation = useAssistantMessageMutation();
  const updateSessionMutation = useUpdateAssistantSessionMutation();

  const sessions = useMemo(() => sessionsQuery.data ?? [], [sessionsQuery.data]);
  const messages = useMemo(() => messagesQuery.data ?? [], [messagesQuery.data]);
  const options = contextOptionsQuery.data;
  const capabilities = capabilitiesQuery.data;

  const activeSession = useMemo(
    () => sessions.find((item) => item.id === sessionId) ?? null,
    [sessionId, sessions],
  );

  useEffect(() => {
    if (!sessionId && sessions.length > 0) {
      const next = new URLSearchParams(searchParams);
      next.set("session", sessions[0].id);
      setSearchParams(next, { replace: true });
    }
  }, [sessionId, sessions, searchParams, setSearchParams]);

  useEffect(() => {
    if (activeSession) {
      setSelectedClientId(activeSession.pinnedContext.selectedClientId ?? "");
      setSelectedSkuId(activeSession.pinnedContext.selectedSkuId ?? "");
      setSelectedFileId(activeSession.pinnedContext.selectedUploadIds?.[0] ?? "");
      setSelectedCategoryId(activeSession.pinnedContext.selectedCategoryId ?? "");
      setSelectedRunId(activeSession.pinnedContext.selectedReserveRunId ?? "");
    }
  }, [activeSession]);

  function selectSession(nextSessionId: string) {
    const next = new URLSearchParams(searchParams);
    next.set("session", nextSessionId);
    setSearchParams(next, { replace: true });
  }

  async function createNewSession() {
    const session = await createSessionMutation.mutateAsync({
      pinnedContext: buildContext(
        selectedClientId,
        selectedSkuId,
        selectedFileId,
        selectedCategoryId,
        selectedRunId,
      ),
    });
    selectSession(session.id);
  }

  async function ensureSessionId() {
    if (sessionId) return sessionId;
    const session = await createSessionMutation.mutateAsync({
      pinnedContext: buildContext(
        selectedClientId,
        selectedSkuId,
        selectedFileId,
        selectedCategoryId,
        selectedRunId,
      ),
    });
    selectSession(session.id);
    return session.id;
  }

  async function send(text: string) {
    if (!text.trim()) return;
    const nextText = text.trim();
    setDraft("");
    const ensuredSessionId = await ensureSessionId();
    await messageMutation.mutateAsync({
      sessionId: ensuredSessionId,
      payload: {
        text: nextText,
        context: buildContext(
          selectedClientId,
          selectedSkuId,
          selectedFileId,
          selectedCategoryId,
          selectedRunId,
        ),
      },
    });
  }

  async function renameSession(nextSessionId: string, title: string) {
    await updateSessionMutation.mutateAsync({
      sessionId: nextSessionId,
      payload: { title },
    });
  }

  async function toggleArchive(session: AssistantSession) {
    await updateSessionMutation.mutateAsync({
      sessionId: session.id,
      payload: { status: session.status === "archived" ? "active" : "archived" },
    });
  }

  async function persistContext() {
    if (!sessionId) return;
    await updateSessionMutation.mutateAsync({
      sessionId,
      payload: {
        pinnedContext: buildContext(
          selectedClientId,
          selectedSkuId,
          selectedFileId,
          selectedCategoryId,
          selectedRunId,
        ),
      },
    });
  }

  const isPending =
    createSessionMutation.isPending || messageMutation.isPending || updateSessionMutation.isPending;
  const latestAssistantMessage = [...messages].reverse().find((message) => message.role === "assistant");

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[280px_minmax(0,1fr)_320px]">
      <SessionRail
        sessions={sessions}
        sessionId={sessionId}
        onSelect={selectSession}
        onNew={() => void createNewSession()}
        onRename={(nextSessionId, title) => void renameSession(nextSessionId, title)}
        onArchiveToggle={(session) => void toggleArchive(session)}
        isCreating={createSessionMutation.isPending}
        isUpdating={updateSessionMutation.isPending}
      />

      <div className="space-y-6">
        <PageHeader
          eyebrow="Ассистент"
          title="ИИ-консоль"
          description="Ассистент работает поверх реальных модулей резерва, склада, поставок, качества данных и ingestion-контура. Источники и вызовы инструментов остаются видимыми."
        />

        <section className="panel p-4">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void send(draft);
            }}
            className="flex items-center gap-2"
          >
            <Sparkles className="ml-1 h-4 w-4 text-brand" />
            <Input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Спросите о резерве, покрытиях, поставках, обновлении данных или проблемах качества…"
              className="h-10 border-0 bg-transparent text-sm focus-visible:ring-0"
            />
            <Button
              type="submit"
              size="sm"
              aria-label="Отправить запрос"
              disabled={isPending}
              className="h-9 bg-brand text-brand-foreground hover:bg-brand-hover"
            >
              <ArrowUp className="h-3.5 w-3.5" />
            </Button>
          </form>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {(suggestionsQuery.data ?? []).map((item) => (
              <button
                key={item.id}
                onClick={() => void send(item.prompt)}
                className="rounded-md border border-line-subtle bg-surface-muted/60 px-2.5 py-1 text-xs text-ink-secondary hover:bg-surface-hover hover:text-ink"
              >
                {item.label}
              </button>
            ))}
          </div>
        </section>

        {capabilities ? (
          <section className="panel grid gap-3 p-4 sm:grid-cols-3">
            <div>
              <div className="text-[11px] uppercase tracking-[0.12em] text-ink-muted">Провайдер</div>
              <div className="mt-1 text-sm font-medium text-ink">{capabilities.provider}</div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-[0.12em] text-ink-muted">Резервный режим</div>
              <div className="mt-1 text-sm font-medium text-ink">
                {capabilities.deterministicFallback ? "Детерминированный включён" : "Отключён"}
              </div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-[0.12em] text-ink-muted">Поддерживаемые сценарии</div>
              <div className="mt-1 text-sm font-medium text-ink">{capabilities.intents.length}</div>
            </div>
          </section>
        ) : null}

        {sessionsQuery.error ? (
          <QueryErrorState error={sessionsQuery.error} title="Не удалось загрузить список сессий" />
        ) : null}

        <section className="space-y-4">
          {messagesQuery.error ? (
            <QueryErrorState error={messagesQuery.error} title="Не удалось загрузить историю ИИ-консоли" />
          ) : null}
          {messageMutation.error ? (
            <QueryErrorState
              error={messageMutation.error}
              title="Ассистент сейчас недоступен"
              onRetry={() => void send(draft || suggestionsQuery.data?.[0]?.prompt || "")}
            />
          ) : null}
          {updateSessionMutation.error ? (
            <QueryErrorState error={updateSessionMutation.error} title="Не удалось обновить сессию" />
          ) : null}
          {isPending ? (
            <div className="panel p-5 text-sm text-ink-muted">Собираю контекст, вызываю инструменты и формирую ответ…</div>
          ) : null}

          {messages.length === 0 && !isPending ? (
            <div className="panel p-6">
              <div className="flex items-center gap-2 text-brand">
                <Bot className="h-4 w-4" />
                <span className="text-[11px] uppercase tracking-[0.14em]">Новая сессия</span>
              </div>
              <h3 className="mt-3 text-lg font-semibold text-ink">Задайте первый операционный вопрос</h3>
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-secondary">
                Ассистент опирается на reserve engine, покрытие склада, входящие поставки, происхождение загрузок и quality issues. Ответы остаются объяснимыми и показывают источники.
              </p>
            </div>
          ) : null}

          {messages.map((message: AssistantMessage) =>
            message.role === "user" ? (
              <article key={message.id} className="panel ml-auto max-w-3xl p-4">
                <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">Вопрос</div>
                <p className="mt-1 text-sm text-ink">{message.text}</p>
              </article>
            ) : message.response ? (
              <AssistantResponseCard
                key={message.id}
                response={message.response}
                onFollowup={(prompt) => void send(prompt)}
              />
            ) : (
              <article key={message.id} className="panel p-4 text-sm text-ink-secondary">
                {message.text}
              </article>
            ),
          )}

          {!messages.length && latestAssistantMessage?.response ? (
            <AssistantResponseCard
              response={latestAssistantMessage.response}
              onFollowup={(prompt) => void send(prompt)}
            />
          ) : null}
        </section>
      </div>

      <aside className="space-y-3 xl:sticky xl:top-20 xl:self-start">
        <SectionTitle>Контекст</SectionTitle>
        {contextOptionsQuery.error ? (
          <QueryErrorState error={contextOptionsQuery.error} title="Контекстные справочники не загрузились" />
        ) : null}
        {[
          {
            icon: Building2,
            label: "Клиент",
            value: selectedClientId,
            onChange: setSelectedClientId,
            options: options?.clients ?? [],
          },
          {
            icon: Boxes,
            label: "SKU",
            value: selectedSkuId,
            onChange: setSelectedSkuId,
            options: options?.skus ?? [],
          },
          {
            icon: Layers,
            label: "Файл загрузки",
            value: selectedFileId,
            onChange: setSelectedFileId,
            options: options?.uploads ?? [],
          },
          {
            icon: FileText,
            label: "Категория",
            value: selectedCategoryId,
            onChange: setSelectedCategoryId,
            options: options?.categories ?? [],
          },
        ].map((item) => (
          <div key={item.label} className="panel p-4">
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.14em] text-ink-muted">
              <item.icon className="h-3.5 w-3.5" />
              {item.label}
            </div>
            <select
              value={item.value}
              onChange={(event) => item.onChange(event.target.value)}
              className="mt-3 h-9 w-full rounded-md border border-line-subtle bg-surface-panel px-2 text-sm text-ink"
            >
              <option value="">Не выбран</option>
              {item.options.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        ))}

        <div className="panel p-4">
          <div className="text-[11px] uppercase tracking-[0.14em] text-ink-muted">Reserve run</div>
          <select
            value={selectedRunId}
            onChange={(event) => setSelectedRunId(event.target.value)}
            className="mt-3 h-9 w-full rounded-md border border-line-subtle bg-surface-panel px-2 text-sm text-ink"
          >
            <option value="">Последний релевантный</option>
            {(options?.reserveRuns ?? []).map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <Button
          variant="outline"
          className="w-full"
          onClick={() => void persistContext()}
          disabled={!sessionId || updateSessionMutation.isPending}
        >
          <Check className="mr-2 h-4 w-4" />
          Сохранить контекст в сессию
        </Button>
      </aside>
    </div>
  );
}
