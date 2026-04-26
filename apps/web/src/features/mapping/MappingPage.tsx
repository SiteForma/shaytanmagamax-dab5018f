import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AlertCircle, ArrowRight, Check, MinusCircle, Save, Wand2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui-ext/StatusBadge";
import { PageHeader } from "@/components/ui-ext/PageHeader";
import { QueryErrorState } from "@/components/ui-ext/QueryErrorState";
import { Skeleton } from "@/components/ui-ext/Skeleton";
import { cn } from "@/lib/utils";
import { fmtInt, fmtRelative } from "@/lib/formatters";
import {
  canonicalFieldLabel,
  formatSourceTypeLabel,
  translateUploadIssueMessage,
  uploadIssueCodeLabel,
} from "@/lib/upload-labels";
import {
  useApplyMappingTemplateMutation,
  useApplyUploadMutation,
  useCreateMappingTemplateMutation,
  useMappingTemplatesQuery,
  useSaveUploadMappingMutation,
  useSuggestMappingMutation,
  useUploadFileDetailQuery,
  useUploadIssuesQuery,
  useUploadJobsQuery,
  useValidateUploadMutation,
} from "@/hooks/queries/use-uploads";
import type { MappingField } from "@/types";

const EMPTY_FIELDS: MappingField[] = [];

export default function MappingPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [mappingDraft, setMappingDraft] = useState<Record<string, string>>({});
  const [templateId, setTemplateId] = useState("");
  const [templateName, setTemplateName] = useState("");
  const selectedFileId = searchParams.get("file");
  const uploadsQuery = useUploadJobsQuery({});
  const uploads = useMemo(() => uploadsQuery.data?.items ?? [], [uploadsQuery.data]);
  const detailQuery = useUploadFileDetailQuery(selectedFileId);
  const detail = detailQuery.data ?? null;
  const issuesQuery = useUploadIssuesQuery(selectedFileId);
  const templatesQuery = useMappingTemplatesQuery(detail?.file.sourceType);
  const templates = useMemo(() => templatesQuery.data ?? [], [templatesQuery.data]);
  const suggestMutation = useSuggestMappingMutation();
  const saveMutation = useSaveUploadMappingMutation();
  const validateMutation = useValidateUploadMutation();
  const applyMutation = useApplyUploadMutation();
  const createTemplateMutation = useCreateMappingTemplateMutation();
  const applyTemplateMutation = useApplyMappingTemplateMutation();

  useEffect(() => {
    if (!uploads.length || selectedFileId) {
      return;
    }
    const next = new URLSearchParams(searchParams);
    next.set("file", uploads[0].id);
    setSearchParams(next, { replace: true });
  }, [searchParams, selectedFileId, setSearchParams, uploads]);

  useEffect(() => {
    if (!detail) {
      return;
    }
    setMappingDraft(detail.mapping.activeMapping);
    setTemplateId(detail.mapping.templateId ?? templates[0]?.id ?? "");
    setTemplateName(`${formatSourceTypeLabel(detail.file.sourceType)}: шаблон`);
  }, [detail, templates]);

  const selectedUpload = detail?.file ?? null;
  const suggestionRows = detail?.mapping.suggestions ?? EMPTY_FIELDS;
  const sampleRows = detail?.preview.sampleRows ?? [];
  const issueRows = issuesQuery.data?.items ?? detail?.issuesPreview ?? [];
  const busy =
    suggestMutation.isPending ||
    saveMutation.isPending ||
    validateMutation.isPending ||
    applyMutation.isPending ||
    createTemplateMutation.isPending ||
    applyTemplateMutation.isPending;

  const groupedCandidates = useMemo(() => {
    const options = new Set(detail?.mapping.canonicalFields ?? []);
    suggestionRows.forEach((row) => row.candidates?.forEach((candidate) => options.add(candidate)));
    return Array.from(options);
  }, [detail?.mapping.canonicalFields, suggestionRows]);

  async function onSuggest() {
    if (!detail) return;
    try {
      await suggestMutation.mutateAsync({ fileId: detail.file.id, templateId: templateId || undefined });
      toast.success("Подсказки сопоставления обновлены");
    } catch {
      toast.error("Не удалось обновить подсказки");
    }
  }

  async function onApplyTemplate() {
    if (!detail || !templateId) return;
    try {
      await applyTemplateMutation.mutateAsync({ templateId, fileId: detail.file.id });
      toast.success("Шаблон применён");
    } catch {
      toast.error("Не удалось применить шаблон");
    }
  }

  async function onSave() {
    if (!detail) return;
    try {
      await saveMutation.mutateAsync({
        fileId: detail.file.id,
        mappings: mappingDraft,
        templateId: templateId || undefined,
      });
      toast.success("Сопоставление сохранено");
    } catch {
      toast.error("Не удалось сохранить сопоставление");
    }
  }

  async function onValidate() {
    if (!detail) return;
    try {
      await validateMutation.mutateAsync(detail.file.id);
      toast.success("Проверка завершена");
    } catch {
      toast.error("Не удалось выполнить проверку");
    }
  }

  async function onApply() {
    if (!detail) return;
    try {
      await applyMutation.mutateAsync(detail.file.id);
      toast.success("Нормализованные данные применены");
    } catch {
      toast.error("Не удалось применить данные");
    }
  }

  async function onCreateTemplate() {
    if (!detail || !templateName.trim()) return;
    try {
      const created = await createTemplateMutation.mutateAsync({
        name: templateName.trim(),
        sourceType: detail.file.sourceType,
        mappings: mappingDraft,
        requiredFields: detail.mapping.requiredFields,
      });
      setTemplateId(created.id);
      toast.success("Шаблон сохранён");
    } catch {
      toast.error("Не удалось сохранить шаблон");
    }
  }

  function updateField(source: string, canonical: string) {
    setMappingDraft((current) => {
      const next = { ...current };
      if (canonical) next[source] = canonical;
      else delete next[source];
      return next;
    });
  }

  const sidebarError = uploadsQuery.error ?? detailQuery.error;

  return (
    <>
      <PageHeader
        eyebrow="Нормализация"
        title="Сопоставление данных"
        description="Подсказки по заголовкам, повторное использование шаблонов, предпросмотр выборки и проблемы проверки идут через реальный контур загрузки данных."
      />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[320px,minmax(0,1fr)]">
        <aside className="space-y-4">
          <section className="panel p-4">
            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">Файл</div>
            <select
              value={selectedUpload?.id ?? ""}
              onChange={(event) => {
                const next = new URLSearchParams(searchParams);
                next.set("file", event.target.value);
                setSearchParams(next);
              }}
              className="mt-3 h-10 w-full rounded-md border border-line-subtle bg-surface-panel px-3 text-sm text-ink"
            >
              {uploads.map((upload) => (
                <option key={upload.id} value={upload.id}>
                  {upload.fileName}
                </option>
              ))}
            </select>
            {detailQuery.isLoading ? (
              <div className="mt-4 space-y-2">
                <Skeleton className="h-8" />
                <Skeleton className="h-16" />
              </div>
            ) : selectedUpload ? (
              <div className="mt-4 space-y-3 text-sm">
                <div>
                  <div className="font-medium text-ink">{selectedUpload.fileName}</div>
                  <div className="text-xs text-ink-muted">
                    {formatSourceTypeLabel(selectedUpload.sourceType)} · {fmtRelative(selectedUpload.uploadedAt)}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <Metric label="Строк" value={fmtInt(selectedUpload.rows)} />
                  <Metric label="Проблем" value={fmtInt(selectedUpload.issues)} />
                  <Metric label="Корректно" value={fmtInt(detail?.validation.validRows ?? 0)} />
                  <Metric label="Отклонено" value={fmtInt(detail?.validation.failedRows ?? 0)} />
                </div>
              </div>
            ) : (
              <div className="mt-4 text-sm text-ink-muted">Выберите загрузку из реальной истории.</div>
            )}
          </section>

          <section className="panel p-4">
            <div className="flex items-center justify-between">
              <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">Шаблоны</div>
              <span className="text-xs text-ink-muted">{templates.length} доступно</span>
            </div>
            <select
              value={templateId}
              onChange={(event) => setTemplateId(event.target.value)}
              className="mt-3 h-10 w-full rounded-md border border-line-subtle bg-surface-panel px-3 text-sm text-ink"
            >
              <option value="">Без шаблона</option>
              {templates.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name} · v{template.version}
                </option>
              ))}
            </select>
            <input
              value={templateName}
              onChange={(event) => setTemplateName(event.target.value)}
              placeholder="Название нового шаблона"
              className="mt-3 h-10 w-full rounded-md border border-line-subtle bg-surface-panel px-3 text-sm text-ink"
            />
            <div className="mt-3 flex gap-2">
              <Button
                size="sm"
                variant="outline"
                className="flex-1 border-line-subtle bg-surface-panel"
                disabled={!detail || !templateId || busy}
                onClick={() => void onApplyTemplate()}
              >
                {applyTemplateMutation.isPending ? "Применение…" : "Применить"}
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="flex-1 border-line-subtle bg-surface-panel"
                disabled={!detail || busy}
                onClick={() => void onSuggest()}
              >
                <Wand2 className="mr-1.5 h-3.5 w-3.5" />
                {suggestMutation.isPending ? "Поиск…" : "Подсказать"}
              </Button>
            </div>
            <Button
              size="sm"
              variant="outline"
              className="mt-2 w-full border-line-subtle bg-surface-panel"
              disabled={!detail || !templateName.trim() || busy}
              onClick={() => void onCreateTemplate()}
            >
              {createTemplateMutation.isPending ? "Сохранение…" : "Сохранить как шаблон"}
            </Button>
          </section>

          <section className="panel p-4">
            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">Применение</div>
            <div className="mt-3 space-y-2 text-xs text-ink-secondary">
              <div>Блокирующие проблемы: {detail?.validation.hasBlockingIssues ? "да" : "нет"}</div>
              <div>Предупреждения: {fmtInt(detail?.validation.warningsCount ?? 0)}</div>
              <div>Шаблон: {detail?.mapping.templateId ?? "ручной черновик"}</div>
            </div>
            <div className="mt-4 flex flex-col gap-2">
              <Button
                size="sm"
                variant="outline"
                className="border-line-subtle bg-surface-panel"
                disabled={!selectedUpload?.canValidate || busy}
                onClick={() => void onValidate()}
              >
                {validateMutation.isPending ? "Проверка…" : "Проверить"}
              </Button>
              <Button
                size="sm"
                className="bg-brand text-brand-foreground hover:bg-brand-hover"
                disabled={!selectedUpload?.canApply || busy}
                onClick={() => void onApply()}
              >
                {applyMutation.isPending ? "Применение…" : "Применить"}
              </Button>
            </div>
          </section>

          {sidebarError ? (
            <QueryErrorState
              error={sidebarError}
              title="Контекст сопоставления пока недоступен"
              onRetry={() => {
                void uploadsQuery.refetch();
                void detailQuery.refetch();
              }}
            />
          ) : null}
        </aside>

        <div className="space-y-4">
          <section className="panel overflow-hidden">
            <div className="grid grid-cols-12 border-b border-line-subtle bg-surface-elevated/40 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-muted">
              <div className="col-span-3">Поле источника</div>
              <div className="col-span-1" />
              <div className="col-span-4">Каноническое поле</div>
              <div className="col-span-2">Пример</div>
              <div className="col-span-1">Статус</div>
              <div className="col-span-1 text-right">Уверенность</div>
            </div>
            {detailQuery.isLoading ? (
              <div className="p-4 space-y-2">
                {Array.from({ length: 8 }).map((_, index) => (
                  <Skeleton key={index} className="h-10" />
                ))}
              </div>
            ) : detailQuery.error ? (
              <div className="p-4">
                <QueryErrorState
                  error={detailQuery.error}
                  title="Не удалось загрузить структуру сопоставления"
                  onRetry={() => void detailQuery.refetch()}
                />
              </div>
            ) : (
              <>
                <ul>
                  {suggestionRows.map((field) => (
                    <li
                      key={field.source}
                      className="grid grid-cols-12 items-center gap-2 border-b border-line-subtle/60 px-4 py-2.5 text-sm hover:bg-surface-hover/50"
                    >
                      <div className="col-span-3 min-w-0">
                        <div className="truncate text-ink">{field.source}</div>
                        {field.required ? <div className="text-[11px] uppercase tracking-wide text-warning">обязательно</div> : null}
                      </div>
                      <div className="col-span-1 text-ink-muted">
                        <ArrowRight className="h-3.5 w-3.5" />
                      </div>
                      <div className="col-span-4">
                        <select
                          value={mappingDraft[field.source] ?? ""}
                          onChange={(event) => updateField(field.source, event.target.value)}
                          className="h-9 w-full rounded-md border border-line-subtle bg-surface-panel px-3 text-sm text-ink"
                        >
                          <option value="">Не сопоставлено</option>
                          {groupedCandidates.map((candidate) => (
                            <option key={candidate} value={candidate}>
                              {canonicalFieldLabel(candidate)}
                            </option>
                          ))}
                        </select>
                        {field.candidates?.length ? (
                          <div className="mt-1 text-[11px] text-ink-muted">
                            Кандидаты: {field.candidates.map((candidate) => canonicalFieldLabel(candidate)).join(", ")}
                          </div>
                        ) : null}
                      </div>
                      <div className="col-span-2 truncate text-xs text-ink-muted">{field.sample ?? "—"}</div>
                      <div className="col-span-1">
                        {field.status === "ok" && <Check className="h-3.5 w-3.5 text-success" />}
                        {field.status === "review" && <AlertCircle className="h-3.5 w-3.5 text-warning" />}
                        {field.status === "missing" && <MinusCircle className="h-3.5 w-3.5 text-danger" />}
                      </div>
                      <div className="col-span-1 text-right">
                        <span className={cn("text-num text-xs", field.status === "missing" ? "text-danger" : "text-ink")}>
                          {Math.round(field.confidence * 100)}%
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
                <div className="flex items-center justify-end gap-2 border-t border-line-subtle px-4 py-3">
                  <Button
                    size="sm"
                    variant="outline"
                    className="border-line-subtle bg-surface-panel"
                    disabled={!detail || busy}
                    onClick={() => void onSave()}
                  >
                    <Save className="mr-1.5 h-3.5 w-3.5" />
                    {saveMutation.isPending ? "Сохранение…" : "Сохранить сопоставление"}
                  </Button>
                </div>
              </>
            )}
          </section>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr),360px]">
            <section className="panel overflow-hidden">
              <div className="border-b border-line-subtle px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-muted">
                Предпросмотр
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-line-subtle bg-surface-elevated/20 text-[11px] uppercase tracking-[0.08em] text-ink-muted">
                      {(detail?.preview.headers ?? []).map((header) => (
                        <th key={header} className="px-4 py-2.5 font-semibold">
                          {header}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sampleRows.map((row, index) => (
                      <tr key={index} className="border-b border-line-subtle/60">
                        {(detail?.preview.headers ?? []).map((header) => (
                          <td key={header} className="max-w-[220px] truncate px-4 py-2.5 text-ink-secondary">
                            {String(row[header] ?? "—")}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="panel">
              <div className="border-b border-line-subtle px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-muted">
                Проблемы проверки
              </div>
              {issuesQuery.error ? (
                <div className="p-4">
                  <QueryErrorState
                    error={issuesQuery.error}
                    title="Не удалось загрузить список проблем"
                    onRetry={() => void issuesQuery.refetch()}
                  />
                </div>
              ) : (
                <ul className="divide-y divide-line-subtle">
                  {issueRows.map((issue) => (
                    <li key={issue.id} className="px-4 py-3 text-sm">
                      <div className="flex items-center justify-between gap-2">
                        <div className="font-medium text-ink">{uploadIssueCodeLabel(issue.code)}</div>
                        <StatusBadge value={issue.severity as any} />
                      </div>
                      <div className="mt-1 text-xs text-ink-secondary">{translateUploadIssueMessage(issue.message)}</div>
                      <div className="mt-1 text-[11px] text-ink-muted">
                        строка {issue.rowNumber}
                        {issue.fieldName ? ` · ${canonicalFieldLabel(issue.fieldName)}` : ""}
                      </div>
                    </li>
                  ))}
                  {!issuesQuery.isLoading && issueRows.length === 0 ? (
                    <li className="px-4 py-6 text-sm text-ink-muted">Пока без зафиксированных проблем.</li>
                  ) : null}
                </ul>
              )}
            </section>
          </div>
        </div>
      </div>
    </>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line-subtle bg-surface-muted/40 px-3 py-2">
      <div className="text-ink-muted">{label}</div>
      <div className="mt-1 text-num font-medium text-ink">{value}</div>
    </div>
  );
}
