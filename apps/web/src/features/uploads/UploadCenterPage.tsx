import { useEffect, useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { FileSpreadsheet, Upload, ArrowRight, ShieldAlert, Play } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui-ext/PageHeader";
import { QueryErrorState } from "@/components/ui-ext/QueryErrorState";
import { Skeleton } from "@/components/ui-ext/Skeleton";
import { cn } from "@/lib/utils";
import { fmtBytes, fmtInt, fmtRelative } from "@/lib/formatters";
import { SOURCE_TYPE_LABELS, formatSourceTypeLabel } from "@/lib/upload-labels";
import {
  useApplyUploadMutation,
  useCreateUploadMutation,
  useUploadFileDetailQuery,
  useUploadJobsQuery,
  useValidateUploadMutation,
} from "@/hooks/queries/use-uploads";
import { useHasCapability } from "@/hooks/queries/use-auth";
import type { UploadJob } from "@/types";

const STATE_TONE: Record<UploadJob["state"], string> = {
  uploaded: "text-ink-muted",
  parsing: "text-info",
  mapping_required: "text-warning",
  validating: "text-info",
  issues_found: "text-warning",
  ready_to_review: "text-info",
  ready_to_apply: "text-success",
  applying: "text-info",
  applied: "text-success",
  applied_with_warnings: "text-warning",
  failed: "text-danger",
  mapped: "text-info",
  normalized: "text-info",
  ready: "text-success",
};

const STATE_LABEL: Record<UploadJob["state"], string> = {
  uploaded: "загружен",
  parsing: "парсинг",
  mapping_required: "нужно сопоставление",
  validating: "проверка",
  issues_found: "есть проблемы",
  ready_to_review: "готов к просмотру",
  ready_to_apply: "готов к применению",
  applying: "применение",
  applied: "применён",
  applied_with_warnings: "применён с предупреждениями",
  failed: "ошибка",
  mapped: "сопоставлен",
  normalized: "нормализован",
  ready: "готов",
};

export default function UploadCenterPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedFileId = searchParams.get("file");
  const status = searchParams.get("status") ?? "all";
  const sourceType = searchParams.get("source") ?? "sales";
  const page = Number(searchParams.get("page") ?? "1");
  const pageSize = Number(searchParams.get("pageSize") ?? "12");
  const jobsQuery = useUploadJobsQuery({
    status: status === "all" ? undefined : status,
    sourceType: sourceType === "all" ? undefined : sourceType,
    page,
    pageSize,
  });
  const jobs = useMemo(() => jobsQuery.data?.items ?? [], [jobsQuery.data]);
  const jobsMeta = jobsQuery.data?.meta;
  const detailQuery = useUploadFileDetailQuery(selectedFileId);
  const createMutation = useCreateUploadMutation();
  const validateMutation = useValidateUploadMutation();
  const applyMutation = useApplyUploadMutation();
  const canWrite = useHasCapability("uploads:write");
  const canApply = useHasCapability("uploads:apply");
  const selectedDetail = detailQuery.data ?? null;
  const selected = selectedDetail?.file ?? null;

  useEffect(() => {
    if (!jobs.length || selectedFileId) {
      return;
    }
    const next = new URLSearchParams(searchParams);
    next.set("file", jobs[0].id);
    setSearchParams(next, { replace: true });
  }, [jobs, searchParams, selectedFileId, setSearchParams]);

  async function onFileSelected(file: File | null) {
    if (!file) return;
    try {
      const detail = await createMutation.mutateAsync({
        file,
        sourceType: sourceType === "all" ? "sales" : sourceType,
      });
      const next = new URLSearchParams(searchParams);
      next.set("file", detail.file.id);
      setSearchParams(next);
      toast.success("Файл загружен в ingestion lifecycle");
    } catch {
      toast.error("Не удалось загрузить файл");
    }
  }

  async function onValidate() {
    if (!selectedFileId) return;
    try {
      await validateMutation.mutateAsync(selectedFileId);
      toast.success("Проверка завершена");
    } catch {
      toast.error("Не удалось запустить проверку");
    }
  }

  async function onApply() {
    if (!selectedFileId) return;
    try {
      await applyMutation.mutateAsync(selectedFileId);
      toast.success("Нормализованные данные применены");
    } catch {
      toast.error("Не удалось применить данные");
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Приём данных"
        title="Центр загрузки"
        description="Оригинал файла, предпросмотр, сопоставление, проблемы проверки и журнал применения проходят через единый жизненный цикл загрузки данных."
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="panel flex h-48 flex-col items-center justify-center gap-3 border-dashed text-center">
            <div className="grid h-10 w-10 place-items-center rounded-lg border border-line-subtle bg-surface-muted text-brand">
              <Upload className="h-5 w-5" />
            </div>
            <div>
              <div className="text-sm font-medium text-ink">Загрузите файл в конвейер загрузки данных</div>
              <div className="text-xs text-ink-muted">
                CSV/XLSX. Сохраняем оригинал, строим предпросмотр, подсказываем сопоставление, фиксируем проблемы и след применения.
              </div>
            </div>
            <div className="flex items-center gap-2">
              <select
                value={sourceType}
                onChange={(event) => {
                  const next = new URLSearchParams(searchParams);
                  if (event.target.value === "all") next.delete("source");
                  else next.set("source", event.target.value);
                  next.delete("page");
                  setSearchParams(next);
                }}
                className="h-9 rounded-md border border-line-subtle bg-surface-panel px-3 text-sm text-ink"
              >
                {Object.entries(SOURCE_TYPE_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
              <label className="inline-flex">
                <input
                  type="file"
                  className="hidden"
                  disabled={!canWrite}
                  onChange={(event) => onFileSelected(event.target.files?.[0] ?? null)}
                />
                <Button asChild size="sm" disabled={!canWrite} className="cursor-pointer bg-brand text-brand-foreground hover:bg-brand-hover disabled:cursor-not-allowed">
                  <span>{createMutation.isPending ? "Загрузка…" : "Выбрать файл"}</span>
                </Button>
              </label>
            </div>
          </div>
        </div>

        <div className="panel p-5">
          <div className="flex items-center justify-between">
            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
              Выбранный файл
            </div>
            {selected ? (
              <span className={cn("text-xs font-medium uppercase tracking-wide", STATE_TONE[selected.state])}>
                {STATE_LABEL[selected.state]}
              </span>
            ) : null}
          </div>
          {detailQuery.isLoading ? (
            <div className="mt-4 space-y-3">
              <Skeleton className="h-8 w-2/3" />
              <Skeleton className="h-20" />
              <Skeleton className="h-9" />
            </div>
          ) : detailQuery.error ? (
            <QueryErrorState
              error={detailQuery.error}
              title="Детали загрузки пока недоступны"
              onRetry={() => void detailQuery.refetch()}
              className="mt-4"
            />
          ) : selected ? (
            <div className="mt-4 space-y-3 text-sm">
              <div>
                <div className="font-medium text-ink">{selected.fileName}</div>
                <div className="text-xs text-ink-muted">
                  {formatSourceTypeLabel(selected.sourceType)} · {fmtBytes(selected.sizeBytes)} · {fmtRelative(selected.uploadedAt)}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <Stat label="Строк" value={fmtInt(selected.rows)} />
                <Stat label="Проблем" value={fmtInt(selected.issues)} />
                <Stat label="Применено" value={fmtInt(selected.appliedRows ?? 0)} />
                <Stat label="Предупреждений" value={fmtInt(selected.warningsCount ?? 0)} />
              </div>
              <div className="rounded-lg border border-line-subtle bg-surface-muted/40 p-3 text-xs text-ink-secondary">
                {selectedDetail?.preview.headers.length ?? 0} колонок, в выборке {selectedDetail?.preview.sampleRowCount ?? 0} строк.
                {selected.duplicateOfBatchId ? ` Найден дубликат пакета ${selected.duplicateOfBatchId}.` : ""}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button asChild size="sm" variant="outline" className="border-line-subtle bg-surface-panel">
                  <Link to={`/mapping?file=${selected.id}`}>Открыть сопоставление</Link>
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="border-line-subtle bg-surface-panel"
                  disabled={!canWrite || !selected.canValidate || validateMutation.isPending || applyMutation.isPending}
                  onClick={onValidate}
                >
                  <ShieldAlert className="mr-1.5 h-3.5 w-3.5" />
                  {validateMutation.isPending ? "Проверка…" : "Проверить"}
                </Button>
                <Button
                  size="sm"
                  className="bg-brand text-brand-foreground hover:bg-brand-hover"
                  disabled={!canApply || !selected.canApply || validateMutation.isPending || applyMutation.isPending}
                  onClick={onApply}
                >
                  <Play className="mr-1.5 h-3.5 w-3.5" />
                  {applyMutation.isPending ? "Применение…" : "Применить"}
                </Button>
              </div>
            </div>
          ) : (
            <div className="mt-4 rounded-lg border border-line-subtle bg-surface-muted/30 p-4 text-sm text-ink-muted">
              Загрузите первый файл, чтобы появился предпросмотр и состояния жизненного цикла.
            </div>
          )}
        </div>
      </div>

      <section className="panel">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line-subtle px-4 py-3">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
            История загрузок
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={status}
              onChange={(event) => {
                const next = new URLSearchParams(searchParams);
                if (event.target.value === "all") next.delete("status");
                else next.set("status", event.target.value);
                next.delete("page");
                setSearchParams(next);
              }}
              className="h-8 rounded-md border border-line-subtle bg-surface-panel px-2 text-xs text-ink"
            >
              <option value="all">Все статусы</option>
              {Object.entries(STATE_LABEL).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        </div>
        {jobsQuery.error ? (
          <div className="p-4">
            <QueryErrorState
              error={jobsQuery.error}
              title="История загрузок пока недоступна"
              onRetry={() => void jobsQuery.refetch()}
            />
          </div>
        ) : (
          <>
            <ul className="divide-y divide-line-subtle">
            {jobsQuery.isLoading
              ? Array.from({ length: 6 }).map((_, index) => (
                  <li key={index} className="px-4 py-3">
                    <Skeleton className="h-12" />
                  </li>
                ))
              : jobs.map((job) => (
                  <li
                    key={job.id}
                    className={cn(
                      "flex cursor-pointer items-center gap-3 px-4 py-3 text-sm transition-colors hover:bg-surface-hover/40",
                      job.id === selectedFileId && "bg-surface-elevated/40",
                    )}
                    onClick={() => {
                      const next = new URLSearchParams(searchParams);
                      next.set("file", job.id);
                      setSearchParams(next);
                    }}
                  >
                    <FileSpreadsheet className="h-4 w-4 text-ink-muted" />
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-medium text-ink">{job.fileName}</div>
                      <div className="text-xs text-ink-muted">
                        {formatSourceTypeLabel(job.sourceType)} · {fmtBytes(job.sizeBytes)} · {fmtInt(job.rows)} строк · {fmtRelative(job.uploadedAt)}
                      </div>
                    </div>
                    <div className="hidden min-w-[128px] text-right text-xs text-ink-muted md:block">
                      {fmtInt(job.appliedRows ?? 0)} применено / {fmtInt(job.failedRows ?? 0)} пропущено
                    </div>
                    <span className={cn("text-xs font-medium uppercase tracking-wide", STATE_TONE[job.state])}>
                      {STATE_LABEL[job.state]}
                    </span>
                    {job.issues > 0 ? <span className="chip text-warning">{job.issues} проблем</span> : null}
                    <Link
                      to={`/mapping?file=${job.id}`}
                      className="inline-flex items-center gap-1 text-xs text-ink-muted transition-colors hover:text-ink"
                      onClick={(event) => event.stopPropagation()}
                    >
                      сопоставление
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </li>
                ))}
            {!jobsQuery.isLoading && jobs.length === 0 ? (
              <li className="px-4 py-10 text-center text-sm text-ink-muted">
                История пока пустая. Первая загрузка сразу создаст предпросмотр, подсказки сопоставления и сводку проверки.
              </li>
            ) : null}
            </ul>
            {jobsMeta ? (
              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line-subtle px-4 py-3 text-xs text-ink-muted">
                <div>
                  {jobsMeta.total > 0
                    ? `${(jobsMeta.page - 1) * jobsMeta.pageSize + 1}–${Math.min(
                        (jobsMeta.page - 1) * jobsMeta.pageSize + jobs.length,
                        jobsMeta.total,
                      )} из ${jobsMeta.total}`
                    : "0 загрузок"}
                </div>
                <div className="flex items-center gap-2">
                  <select
                    value={jobsMeta.pageSize}
                    onChange={(event) => {
                      const next = new URLSearchParams(searchParams);
                      next.set("pageSize", event.target.value);
                      next.delete("page");
                      setSearchParams(next);
                    }}
                    className="h-8 rounded-md border border-line-subtle bg-surface-panel px-2 text-xs text-ink"
                  >
                    {[12, 24, 48].map((value) => (
                      <option key={value} value={value}>
                        {value} / стр.
                      </option>
                    ))}
                  </select>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8 border-line-subtle bg-surface-panel"
                    disabled={jobsMeta.page <= 1}
                    onClick={() => {
                      const next = new URLSearchParams(searchParams);
                      next.set("page", String(Math.max(jobsMeta.page - 1, 1)));
                      setSearchParams(next);
                    }}
                  >
                    Назад
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8 border-line-subtle bg-surface-panel"
                    disabled={jobsMeta.page * jobsMeta.pageSize >= jobsMeta.total}
                    onClick={() => {
                      const next = new URLSearchParams(searchParams);
                      next.set("page", String(jobsMeta.page + 1));
                      setSearchParams(next);
                    }}
                  >
                    Далее
                  </Button>
                </div>
              </div>
            ) : null}
          </>
        )}
      </section>
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line-subtle bg-surface-muted/40 px-3 py-2">
      <div className="text-ink-muted">{label}</div>
      <div className="mt-1 text-num font-medium text-ink">{value}</div>
    </div>
  );
}
