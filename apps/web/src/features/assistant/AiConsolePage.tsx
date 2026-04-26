import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArchiveRestore,
  ArrowUp,
  Boxes,
  Building2,
  Check,
  FileText,
  Info,
  Layers,
  PencilLine,
  ShieldAlert,
  SlidersHorizontal,
  Sparkles,
  SquarePen,
  Trash2,
  X,
} from "lucide-react";
import magamaxMark from "@/assets/magamax-mark.png";
import { SectionTitle } from "@/components/ui-ext/PageHeader";
import { QueryErrorState } from "@/components/ui-ext/QueryErrorState";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import type {
  AssistantMessage,
  AssistantPinnedContext,
  AssistantResponse,
  AssistantSection,
  AssistantSession,
} from "@/types";
import {
  useAssistantContextOptionsQuery,
  useAssistantMessagesQuery,
  useAssistantPromptSuggestionsQuery,
  useAssistantSessionsQuery,
} from "@/hooks/queries/use-assistant";
import {
  useAssistantMessageMutation,
  useCreateAssistantSessionMutation,
  useDeleteAssistantSessionMutation,
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
  sheetName: "Лист",
  dimensionName: "Измерение",
  metricName: "Показатель",
  metricYear: "Год",
  metricValue: "Значение",
};

function formatMetricName(value: string) {
  return (
    {
      revenue: "Выручка",
      profitability_pct: "Рентабельность",
      growth_rate: "Рост / падение",
      distribution_share: "Доля",
      total_receivables: "Дебиторка всего",
      overdue_receivables: "ПДЗ",
      overdue_receivables_reduction_rate: "Сокращение ПДЗ",
      demand_shortage: "СПРОС / недопоставки",
    }[value] ?? value
  );
}

function formatAssistantCell(column: string, value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  if (column === "metricName") return formatMetricName(String(value));
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

function formatSessionCostRub(value: number | undefined | null) {
  const cost = Number(value ?? 0);
  if (!Number.isFinite(cost) || cost <= 0) return "0 руб.";
  if (cost < 1) return `${cost.toFixed(2).replace(".", ",")} руб.`;
  return `${Math.round(cost).toLocaleString("ru-RU")} руб.`;
}

function formatSessionUsage(session: AssistantSession) {
  return `${session.messageCount} сообщений: ${formatSessionCostRub(session.estimatedCostRub ?? session.tokenUsage?.estimatedCostRub ?? 0)}`;
}

function formatToolArgument(value: unknown) {
  if (value === null || value === undefined) return "—";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "—";
  if (typeof value === "boolean") return value ? "Да" : "Нет";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function responseTextLength(response: AssistantResponse) {
  return response.summary.length;
}

function createTextRevealer(visibleChars: number) {
  let remaining = visibleChars;
  return (value: string | null | undefined) => {
    if (value === null || value === undefined || value.length === 0) return value ?? null;
    if (remaining <= 0) return "";
    if (remaining >= value.length) {
      remaining -= value.length;
      return value;
    }
    const visible = value.slice(0, remaining);
    remaining = 0;
    return visible;
  };
}

function revealResponseText(response: AssistantResponse, visibleChars: number): AssistantResponse {
  const reveal = createTextRevealer(visibleChars);
  return {
    ...response,
    title: response.title,
    summary: reveal(response.summary) ?? "",
    sections: response.sections.map((section) => ({
      ...section,
      title: reveal(section.title) ?? "",
      body: reveal(section.body) ?? null,
      items: section.items.map((item) => reveal(item) ?? "").filter(Boolean),
    })),
  };
}

function MagamaxAssistantIcon({ className }: { className?: string }) {
  return (
    <img
      src={magamaxMark}
      alt=""
      aria-hidden="true"
      className={cn("block object-contain", className)}
      draggable={false}
    />
  );
}

function useTypewriterCursor(totalChars: number, active: boolean, onDone?: () => void) {
  const [visibleChars, setVisibleChars] = useState(active ? 0 : totalChars);
  const onDoneRef = useRef(onDone);

  useEffect(() => {
    onDoneRef.current = onDone;
  }, [onDone]);

  useEffect(() => {
    if (!active) {
      setVisibleChars(totalChars);
      return;
    }

    setVisibleChars(0);
    if (totalChars <= 0) {
      onDoneRef.current?.();
      return;
    }

    const step = Math.max(2, Math.ceil(totalChars / 180));
    const intervalId = window.setInterval(() => {
      setVisibleChars((current) => {
        const next = Math.min(totalChars, current + step);
        if (next >= totalChars) {
          window.clearInterval(intervalId);
          window.setTimeout(() => onDoneRef.current?.(), 120);
        }
        return next;
      });
    }, 20);

    return () => window.clearInterval(intervalId);
  }, [active, totalChars]);

  return active ? visibleChars : totalChars;
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

function AssistantDetailsDialog({
  response,
  open,
  onOpenChange,
  onFollowup,
}: {
  response: AssistantResponse;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onFollowup: (prompt: string) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[86vh] max-w-5xl overflow-hidden border-line-subtle bg-surface-elevated p-0 text-ink shadow-[0_32px_110px_rgba(0,0,0,0.45)]">
        <DialogHeader className="border-b border-line-subtle px-6 py-5 pr-12">
          <div className="flex items-center gap-3">
            <span className="grid h-9 w-9 place-items-center rounded-full border border-brand/30 bg-brand/15 text-brand">
              <Info className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <DialogTitle className="truncate text-lg text-ink">Подробнее</DialogTitle>
              <DialogDescription className="mt-1 text-sm text-ink-muted">
                Расшифровка ответа, источники, ограничения и трассировка инструментов.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="max-h-[calc(86vh-92px)] overflow-y-auto px-6 py-5">
          <div className="space-y-6">
            <section className="rounded-2xl border border-line-subtle bg-surface-muted/35 px-4 py-4">
              <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
                Краткий вывод
              </div>
              <p className="mt-2 text-sm leading-relaxed text-ink-secondary">{response.summary}</p>
              <div className="mt-3 flex flex-wrap gap-2 text-[10px] uppercase tracking-[0.12em] text-ink-muted">
                <span className="rounded-full border border-line-subtle bg-surface-panel/70 px-2 py-1">
                  Уверенность {Math.round(response.confidence * 100)}%
                </span>
                <span className="rounded-full border border-line-subtle bg-surface-panel/70 px-2 py-1">
                  Trace {response.traceId.slice(0, 8)}
                </span>
              </div>
            </section>

            {response.sections.map((section) => (
              <ResponseSection key={section.id} section={section} />
            ))}

            {response.toolCalls.length ? (
              <section className="rounded-2xl border border-line-subtle bg-surface-muted/25 px-4 py-4">
                <SectionTitle>Трассировка и вызовы инструментов</SectionTitle>
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
              </section>
            ) : null}

            <div className="grid gap-4 lg:grid-cols-2">
              <section>
                <SectionTitle>Источники данных</SectionTitle>
                {response.sourceRefs.length ? (
                  <ul className="mt-3 space-y-2">
                    {response.sourceRefs.map((source) => (
                      <li
                        key={`${source.sourceType}-${source.entityId ?? source.sourceLabel}`}
                        className="rounded-xl border border-line-subtle bg-surface-muted/35 px-3 py-3 text-sm"
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
                ) : (
                  <div className="mt-3 rounded-xl border border-line-subtle bg-surface-muted/35 px-3 py-3 text-sm text-ink-muted">
                    Для этого ответа доменные источники не использовались.
                  </div>
                )}
              </section>

              <section>
                <SectionTitle>Следующие шаги</SectionTitle>
                <div className="mt-3 flex flex-wrap gap-2">
                  {response.followups.map((followup) =>
                    followup.action === "open" && followup.route ? (
                      <Link
                        key={followup.id}
                        to={followup.route}
                        className="rounded-full border border-line-subtle bg-surface-muted/50 px-3 py-1.5 text-xs text-ink-secondary transition-colors hover:bg-surface-hover hover:text-ink"
                      >
                        {followup.label}
                      </Link>
                    ) : (
                      <button
                        key={followup.id}
                        onClick={() => onFollowup(followup.prompt)}
                        className="rounded-full border border-line-subtle bg-surface-muted/50 px-3 py-1.5 text-xs text-ink-secondary transition-colors hover:bg-surface-hover hover:text-ink"
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
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function AssistantResponseCard({
  response,
  onFollowup,
  animate = false,
  onTypingDone,
  onTypingProgress,
}: {
  response: AssistantResponse;
  onFollowup: (prompt: string) => void;
  animate?: boolean;
  onTypingDone?: () => void;
  onTypingProgress?: () => void;
}) {
  const totalChars = useMemo(() => responseTextLength(response), [response]);
  const visibleChars = useTypewriterCursor(totalChars, animate, onTypingDone);
  const isTyping = animate && visibleChars < totalChars;
  const renderedResponse = animate ? revealResponseText(response, visibleChars) : response;
  const [detailsOpen, setDetailsOpen] = useState(false);

  useEffect(() => {
    if (animate) {
      onTypingProgress?.();
    }
  }, [animate, onTypingProgress, visibleChars]);

  return (
    <article className="group flex gap-4 py-7">
      <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-brand/30 bg-brand/15 text-brand shadow-[0_0_22px_rgba(255,106,28,0.12)]">
        <MagamaxAssistantIcon className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1 space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">MAGAMAX AI</div>
            <p className="mt-1 max-w-3xl text-sm leading-relaxed text-ink-secondary">
              {renderedResponse.summary}
            </p>
          </div>
          {!isTyping ? (
            <Button
              size="sm"
              variant="outline"
              className="h-9 shrink-0 rounded-full border-line-subtle bg-surface-muted/40 text-xs text-ink-secondary hover:bg-surface-hover hover:text-ink"
              onClick={() => setDetailsOpen(true)}
            >
              <Info className="mr-1.5 h-3.5 w-3.5 text-brand" />
              Подробнее
            </Button>
          ) : null}
        </div>

        {isTyping ? (
          <div className="flex items-center gap-2 text-sm text-ink-muted">
            <span className="h-4 w-2 animate-pulse rounded-sm bg-brand/80" />
            <span>печатает…</span>
          </div>
        ) : null}
        {!isTyping ? (
          <AssistantDetailsDialog
            response={response}
            open={detailsOpen}
            onOpenChange={setDetailsOpen}
            onFollowup={onFollowup}
          />
        ) : null}
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
  onRestore,
  onDelete,
  isCreating,
  isUpdating,
  isDeleting,
}: {
  sessions: AssistantSession[];
  sessionId: string | null;
  onSelect: (sessionId: string) => void;
  onNew: () => void;
  onRename: (sessionId: string, title: string) => void;
  onRestore: (session: AssistantSession) => void;
  onDelete: (session: AssistantSession) => void;
  isCreating: boolean;
  isUpdating: boolean;
  isDeleting: boolean;
}) {
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const activeSessions = sessions.filter((session) => session.status !== "archived");
  const archivedSessions = sessions.filter((session) => session.status === "archived");

  return (
    <aside className="flex h-full min-h-0 flex-col border-r border-line-subtle bg-surface-panel/70">
      <div className="border-b border-line-subtle p-3">
        <Button
          variant="outline"
          className="h-10 w-full justify-start rounded-xl border-line-subtle bg-surface-muted/40 text-sm"
          onClick={onNew}
          disabled={isCreating}
        >
          <span className="mr-2 grid h-7 w-7 place-items-center rounded-lg bg-brand/10 text-brand">
            <SquarePen className="h-4 w-4" />
          </span>
          Новый чат
        </Button>
      </div>
      <div className="min-h-0 flex-1 space-y-1 overflow-y-auto px-2 py-3">
        {sessions.length === 0 ? (
          <div className="rounded-xl border border-line-subtle bg-surface-muted/30 p-4 text-sm text-ink-muted">
            История пока пуста. Первый вопрос создаст сохранённую сессию.
          </div>
        ) : (
          <>
            {activeSessions.map((session) => (
              <div
                key={session.id}
                className={cn(
                  "group relative rounded-xl border border-transparent p-2.5 transition-colors hover:border-line-subtle hover:bg-surface-muted/40 focus-within:border-line-subtle focus-within:bg-surface-muted/40",
                  session.id === sessionId && "border-line-subtle bg-surface-muted/70",
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
                    <button onClick={() => onSelect(session.id)} className="w-full pr-20 text-left">
                      <div className="line-clamp-1 text-sm font-medium text-ink">{session.title}</div>
                      <div className="mt-1 flex items-center gap-2 text-[11px] text-ink-muted">
                        <span className="whitespace-nowrap">{formatSessionUsage(session)}</span>
                      </div>
                    </button>
                    <div className="absolute right-2 top-2 flex gap-1 opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100">
                      <button
                        type="button"
                        aria-label="Переименовать чат"
                        title="Переименовать"
                        className="flex h-8 w-8 items-center justify-center rounded-lg border border-line-subtle bg-surface-panel/90 text-ink-muted shadow-[0_12px_28px_rgba(0,0,0,0.25)] transition-colors hover:border-brand/40 hover:bg-brand/10 hover:text-brand disabled:cursor-not-allowed disabled:opacity-50"
                        onClick={() => {
                          setEditingSessionId(session.id);
                          setEditingTitle(session.title);
                        }}
                        disabled={isUpdating}
                      >
                        <PencilLine className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        aria-label="Удалить чат"
                        title="Удалить"
                        className="flex h-8 w-8 items-center justify-center rounded-lg border border-line-subtle bg-surface-panel/90 text-ink-muted shadow-[0_12px_28px_rgba(0,0,0,0.25)] transition-colors hover:border-danger/40 hover:bg-danger/10 hover:text-danger disabled:cursor-not-allowed disabled:opacity-50"
                        onClick={() => onDelete(session)}
                        disabled={isDeleting}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))}

            {archivedSessions.length ? (
              <div className="space-y-1 pt-4">
                <div className="px-1 text-[11px] uppercase tracking-[0.12em] text-ink-muted">История</div>
                {archivedSessions.map((session) => (
                  <div
                    key={session.id}
                    className="group relative rounded-xl border border-transparent p-2.5 opacity-75 transition-colors hover:border-line-subtle hover:bg-surface-muted/30 focus-within:border-line-subtle focus-within:bg-surface-muted/30"
                  >
                    <button onClick={() => onSelect(session.id)} className="w-full pr-20 text-left">
                      <div className="flex items-center justify-between gap-2">
                        <div className="line-clamp-1 text-sm font-medium text-ink">{session.title}</div>
                        <span className="rounded-full border border-line-subtle px-2 py-1 text-[10px] uppercase tracking-[0.12em] text-ink-muted">
                          история
                        </span>
                      </div>
                    </button>
                    <div className="absolute right-2 top-2 flex gap-1 opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100">
                      <button
                        type="button"
                        aria-label="Вернуть чат из истории"
                        title="Вернуть"
                        className="flex h-8 w-8 items-center justify-center rounded-lg border border-line-subtle bg-surface-panel/90 text-ink-muted shadow-[0_12px_28px_rgba(0,0,0,0.25)] transition-colors hover:border-brand/40 hover:bg-brand/10 hover:text-brand disabled:cursor-not-allowed disabled:opacity-50"
                        onClick={() => onRestore(session)}
                        disabled={isUpdating}
                      >
                        <ArchiveRestore className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        aria-label="Удалить чат"
                        title="Удалить"
                        className="flex h-8 w-8 items-center justify-center rounded-lg border border-line-subtle bg-surface-panel/90 text-ink-muted shadow-[0_12px_28px_rgba(0,0,0,0.25)] transition-colors hover:border-danger/40 hover:bg-danger/10 hover:text-danger disabled:cursor-not-allowed disabled:opacity-50"
                        onClick={() => onDelete(session)}
                        disabled={isDeleting}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
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
  const [isContextOpen, setIsContextOpen] = useState(false);
  const [typingMessageId, setTypingMessageId] = useState<string | null>(null);
  const [deletedSessionIds, setDeletedSessionIds] = useState<Set<string>>(() => new Set());
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const sessionsQuery = useAssistantSessionsQuery();
  const messagesQuery = useAssistantMessagesQuery(sessionId);
  const suggestionsQuery = useAssistantPromptSuggestionsQuery();
  const contextOptionsQuery = useAssistantContextOptionsQuery();
  const createSessionMutation = useCreateAssistantSessionMutation();
  const messageMutation = useAssistantMessageMutation();
  const updateSessionMutation = useUpdateAssistantSessionMutation();
  const deleteSessionMutation = useDeleteAssistantSessionMutation();
  const isPending =
    createSessionMutation.isPending ||
    messageMutation.isPending ||
    updateSessionMutation.isPending ||
    deleteSessionMutation.isPending;

  const sessions = useMemo(
    () => (sessionsQuery.data ?? []).filter((item) => !deletedSessionIds.has(item.id)),
    [deletedSessionIds, sessionsQuery.data],
  );
  const messages = useMemo(() => messagesQuery.data ?? [], [messagesQuery.data]);
  const options = contextOptionsQuery.data;

  const activeSession = useMemo(
    () => sessions.find((item) => item.id === sessionId) ?? null,
    [sessionId, sessions],
  );

  const scrollChatToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    window.requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView?.({ behavior, block: "end" });
    });
  }, []);

  useEffect(() => {
    if (!sessionId && sessions.length > 0) {
      const next = new URLSearchParams(searchParams);
      next.set("session", sessions[0].id);
      setSearchParams(next, { replace: true });
    }
  }, [sessionId, sessions, searchParams, setSearchParams]);

  useEffect(() => {
    scrollChatToBottom("auto");
  }, [sessionId, scrollChatToBottom]);

  useEffect(() => {
    scrollChatToBottom(messages.length > 1 ? "smooth" : "auto");
  }, [isPending, messages.length, messages[messages.length - 1]?.id, scrollChatToBottom, typingMessageId]);

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
    const result = await messageMutation.mutateAsync({
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
    setTypingMessageId(result.assistantMessage?.id ?? null);
  }

  async function renameSession(nextSessionId: string, title: string) {
    await updateSessionMutation.mutateAsync({
      sessionId: nextSessionId,
      payload: { title },
    });
  }

  async function restoreSession(session: AssistantSession) {
    await updateSessionMutation.mutateAsync({
      sessionId: session.id,
      payload: { status: "active" },
    });
  }

  async function deleteSession(session: AssistantSession) {
    await deleteSessionMutation.mutateAsync(session.id);
    setDeletedSessionIds((current) => new Set(current).add(session.id));
    if (sessionId !== session.id) return;

    const remainingSession = sessions.find((item) => item.id !== session.id && item.status !== "archived")
      ?? sessions.find((item) => item.id !== session.id);
    const next = new URLSearchParams(searchParams);
    if (remainingSession) {
      next.set("session", remainingSession.id);
    } else {
      next.delete("session");
    }
    setSearchParams(next, { replace: true });
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

  async function persistContextAndClose() {
    await persistContext();
    setIsContextOpen(false);
  }

  const selectedContextCount = [
    selectedClientId,
    selectedSkuId,
    selectedFileId,
    selectedCategoryId,
    selectedRunId,
  ].filter(Boolean).length;
  const contextControls = (
    <div className="space-y-3">
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
        onClick={() => void persistContextAndClose()}
        disabled={!sessionId || updateSessionMutation.isPending}
      >
        <Check className="mr-2 h-4 w-4" />
        Сохранить контекст в сессию
      </Button>
    </div>
  );
  const activeTitle = activeSession?.title ?? "Новый чат";

  return (
    <>
      <div className="chatgpt-shell relative grid h-[calc(100vh-112px)] overflow-hidden rounded-[28px] border border-line-subtle bg-surface-panel shadow-[0_30px_90px_rgba(0,0,0,0.28)] xl:grid-cols-[300px_minmax(0,1fr)]">
        <SessionRail
          sessions={sessions}
          sessionId={sessionId}
          onSelect={selectSession}
          onNew={() => void createNewSession()}
          onRename={(nextSessionId, title) => void renameSession(nextSessionId, title)}
          onRestore={(session) => void restoreSession(session)}
          onDelete={(session) => void deleteSession(session)}
          isCreating={createSessionMutation.isPending}
          isUpdating={updateSessionMutation.isPending}
          isDeleting={deleteSessionMutation.isPending}
        />

        <div className="flex min-h-0 flex-col bg-[radial-gradient(circle_at_50%_0%,rgba(255,106,28,0.07),transparent_34%),linear-gradient(180deg,rgba(255,255,255,0.02),transparent)]">
          <header className="flex h-16 shrink-0 items-center justify-between gap-4 border-b border-line-subtle bg-surface-panel/85 px-4 backdrop-blur sm:px-6">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-full border border-brand/30 bg-brand/15 text-brand">
                  <Sparkles className="h-3.5 w-3.5" />
                </span>
                <h1 className="truncate text-sm font-semibold text-ink">{activeTitle}</h1>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                className="relative h-9 w-9 rounded-full border-line-subtle bg-surface-muted/40 p-0"
                onClick={() => setIsContextOpen(true)}
                aria-label="Открыть контекст ИИ-консоли"
                aria-expanded={isContextOpen}
              >
                <SlidersHorizontal className="h-4 w-4 text-brand" />
                {selectedContextCount ? (
                  <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full border border-brand/40 bg-brand px-1 text-[10px] font-semibold text-brand-foreground">
                    {selectedContextCount}
                  </span>
                ) : null}
              </Button>
            </div>
          </header>

          <section className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-8">
            <div className="mx-auto max-w-4xl">
              {sessionsQuery.error ? (
                <QueryErrorState error={sessionsQuery.error} title="Не удалось загрузить список сессий" className="mb-4" />
              ) : null}
              {messagesQuery.error ? (
                <QueryErrorState error={messagesQuery.error} title="Не удалось загрузить историю ИИ-консоли" className="mb-4" />
              ) : null}
              {messageMutation.error ? (
                <QueryErrorState
                  error={messageMutation.error}
                  title="Ассистент сейчас недоступен"
                  onRetry={() => void send(draft || suggestionsQuery.data?.[0]?.prompt || "")}
                  className="mb-4"
                />
              ) : null}
              {updateSessionMutation.error ? (
                <QueryErrorState error={updateSessionMutation.error} title="Не удалось обновить сессию" className="mb-4" />
              ) : null}
              {deleteSessionMutation.error ? (
                <QueryErrorState error={deleteSessionMutation.error} title="Не удалось удалить сессию" className="mb-4" />
              ) : null}

              {messages.length === 0 && !isPending ? (
                <div className="flex min-h-[48vh] flex-col items-center justify-center text-center">
                  <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-brand/30 bg-brand/15 text-brand shadow-[0_0_34px_rgba(255,106,28,0.18)]">
                    <MagamaxAssistantIcon className="h-8 w-8" />
                  </div>
                  <h2 className="mt-5 text-2xl font-semibold tracking-tight text-ink">Чем помочь?</h2>
                  <p className="mt-3 max-w-xl text-sm leading-relaxed text-ink-secondary">
                    Пишите как в обычном чате. Если вопрос требует данных MAGAMAX, ассистент подключит реальные инструменты и покажет источники.
                  </p>
                  <div className="mt-6 grid w-full max-w-2xl gap-2 sm:grid-cols-2">
                    {(suggestionsQuery.data ?? []).slice(0, 4).map((item) => (
                      <button
                        key={item.id}
                        onClick={() => void send(item.prompt)}
                        className="rounded-2xl border border-line-subtle bg-surface-muted/35 px-4 py-3 text-left text-sm text-ink-secondary transition-colors hover:border-brand/40 hover:bg-brand/10 hover:text-ink"
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="divide-y divide-line-subtle/70">
                {messages.map((message: AssistantMessage) =>
                  message.role === "user" ? (
                    <article key={message.id} className="flex justify-end py-7">
                      <div className="max-w-[78%] rounded-[24px] bg-surface-muted px-5 py-3 text-sm leading-relaxed text-ink shadow-sm">
                        {message.text}
                      </div>
                    </article>
                  ) : message.response ? (
                    <AssistantResponseCard
                      key={message.id}
                      response={message.response}
                      onFollowup={(prompt) => void send(prompt)}
                      animate={message.id === typingMessageId}
                      onTypingProgress={() => scrollChatToBottom("smooth")}
                      onTypingDone={() => setTypingMessageId(null)}
                    />
                  ) : (
                    <article key={message.id} className="flex gap-4 py-7 text-sm text-ink-secondary">
                      <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-brand/30 bg-brand/15 text-brand">
                        <MagamaxAssistantIcon className="h-4 w-4" />
                      </div>
                      <div className="rounded-2xl bg-surface-muted/35 px-5 py-3">{message.text}</div>
                    </article>
                  ),
                )}
              </div>

              {isPending ? (
                <div className="flex gap-4 py-7">
                  <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-brand/30 bg-brand/15 text-brand">
                    <MagamaxAssistantIcon className="h-4 w-4" />
                  </div>
                  <div className="rounded-2xl border border-line-subtle bg-surface-muted/35 px-5 py-3 text-sm text-ink-muted">
                    Формирую ответ. Если вопрос требует данных, подключаю нужные инструменты…
                  </div>
                </div>
              ) : null}
              <div ref={messagesEndRef} aria-hidden="true" />
            </div>
          </section>

          <div className="shrink-0 border-t border-line-subtle bg-surface-panel/85 px-4 py-4 backdrop-blur sm:px-8">
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void send(draft);
              }}
              className="mx-auto max-w-4xl"
            >
              <div className="flex items-end gap-2 rounded-[26px] border border-line-subtle bg-surface-muted/50 p-2 shadow-[0_14px_45px_rgba(0,0,0,0.22)] focus-within:border-brand/50">
                <Textarea
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      void send(draft);
                    }
                  }}
                  rows={1}
                  placeholder="Напишите сообщение MAGAMAX…"
                  className="max-h-40 min-h-[44px] resize-none border-0 bg-transparent px-3 py-3 text-sm text-ink placeholder:text-ink-muted focus-visible:ring-0 focus-visible:ring-offset-0"
                />
                <Button
                  type="submit"
                  size="sm"
                  aria-label="Отправить запрос"
                  disabled={isPending || !draft.trim()}
                  className="mb-1 h-9 w-9 shrink-0 rounded-full bg-brand p-0 text-brand-foreground hover:bg-brand-hover"
                >
                  <ArrowUp className="h-4 w-4" />
                </Button>
              </div>
              <div className="mt-2 text-center text-[11px] text-ink-muted">
                Enter отправляет сообщение, Shift+Enter переносит строку.
              </div>
            </form>
          </div>
        </div>
      </div>

      <Sheet open={isContextOpen} onOpenChange={setIsContextOpen}>
        <SheetContent className="w-[88vw] overflow-y-auto border-l border-line-subtle bg-surface-elevated p-5 sm:max-w-[430px]">
          <SheetHeader className="pr-8">
            <SheetTitle className="text-ink">Контекст ИИ-консоли</SheetTitle>
            <SheetDescription className="text-xs leading-relaxed text-ink-muted">
              Закрепите клиента, SKU, файл или reserve run. MAGAMAX AI использует это как подсказку, а операционные вопросы — как вход для инструментов.
            </SheetDescription>
          </SheetHeader>
          <div className="mt-6">{contextControls}</div>
        </SheetContent>
      </Sheet>
    </>
  );
}
