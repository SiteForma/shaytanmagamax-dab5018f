import { useMemo, useState } from "react";
import { toast } from "sonner";
import type { ColumnDef } from "@tanstack/react-table";
import { PageHeader, SectionTitle } from "@/components/ui-ext/PageHeader";
import { KpiCard } from "@/components/ui-ext/KpiCard";
import { DataTable } from "@/components/ui-ext/DataTable";
import { QueryErrorState } from "@/components/ui-ext/QueryErrorState";
import { Skeleton } from "@/components/ui-ext/Skeleton";
import { StatusBadge } from "@/components/ui-ext/StatusBadge";
import { Button } from "@/components/ui/button";
import { useHasCapability } from "@/hooks/queries/use-auth";
import {
  useAdminAuditEventsQuery,
  useAdminHealthDetailsQuery,
  useAdminJobsQuery,
  useAdminSystemFreshnessQuery,
  useAdminUsersQuery,
} from "@/hooks/queries/use-admin";
import { useRetryAdminJobMutation, useUpdateAdminUserRoleMutation } from "@/hooks/mutations/use-admin";
import { useDownloadExportMutation } from "@/hooks/mutations/use-exports";
import { useExportJobsQuery } from "@/hooks/queries/use-exports";
import type { AdminJob, AdminUser, AuditEvent, ExportJob } from "@/types";
import { fmtRelative } from "@/lib/formatters";
import { Activity, Archive, Download, History, RefreshCw, ShieldCheck, Wrench } from "lucide-react";

const ROLE_OPTIONS = [
  { value: "admin", label: "Администратор" },
  { value: "operator", label: "Оператор" },
  { value: "analyst", label: "Аналитик" },
  { value: "viewer", label: "Наблюдатель" },
] as const;

const QUEUE_LABELS: Record<string, string> = {
  ingestion: "Загрузка",
  analytics: "Аналитика",
  exports: "Экспорты",
};

const EXPORT_TYPE_LABELS: Record<string, string> = {
  reserve_run: "Расчёт резерва",
  stock_coverage: "Покрытие склада",
  dashboard_top_risk: "SKU с максимальным риском",
  quality_issues: "Проблемы качества",
  client_exposure: "Экспозиция клиентов",
  diy_exposure_report_pack: "DIY-пакет отчётов",
};

export default function AdminPage() {
  const [jobStatusFilter, setJobStatusFilter] = useState<string>("all");
  const [jobQueueFilter, setJobQueueFilter] = useState<string>("all");
  const [exportStatusFilter, setExportStatusFilter] = useState<string>("all");
  const freshnessQuery = useAdminSystemFreshnessQuery();
  const healthQuery = useAdminHealthDetailsQuery();
  const usersQuery = useAdminUsersQuery();
  const jobsQuery = useAdminJobsQuery({
    status: jobStatusFilter === "all" ? undefined : jobStatusFilter,
    queueName: jobQueueFilter === "all" ? undefined : jobQueueFilter,
  });
  const auditQuery = useAdminAuditEventsQuery({ page: 1, pageSize: 25 });
  const exportJobsQuery = useExportJobsQuery(exportStatusFilter === "all" ? undefined : exportStatusFilter);
  const updateRoleMutation = useUpdateAdminUserRoleMutation();
  const retryJobMutation = useRetryAdminJobMutation();
  const downloadExportMutation = useDownloadExportMutation();
  const canManageUsers = useHasCapability("admin:manage-users");

  const topError =
    freshnessQuery.error ??
    healthQuery.error ??
    usersQuery.error ??
    jobsQuery.error ??
    auditQuery.error ??
    exportJobsQuery.error;

  const usersColumns: ColumnDef<AdminUser>[] = [
    { accessorKey: "fullName", header: "Пользователь", cell: (info) => <div><div className="font-medium text-ink">{info.row.original.fullName}</div><div className="text-xs text-ink-muted">{info.row.original.email}</div></div> },
    { accessorKey: "roles", header: "Роль", cell: (info) => {
      const user = info.row.original;
      return (
        <select
          value={user.roles[0] ?? "viewer"}
          onChange={async (event) => {
            try {
              await updateRoleMutation.mutateAsync({ userId: user.id, role: event.target.value });
              toast.success("Роль обновлена");
            } catch {
              toast.error("Не удалось обновить роль");
            }
          }}
          disabled={!canManageUsers || updateRoleMutation.isPending}
          className="h-8 rounded-md border border-line-subtle bg-surface-panel px-2 text-xs text-ink disabled:opacity-60"
        >
          {ROLE_OPTIONS.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
      );
    } },
    { accessorKey: "capabilities", header: "Доступы", cell: (info) => <span className="text-xs text-ink-muted">{formatCapabilitiesCount((info.getValue() as string[]).length)}</span> },
    { accessorKey: "createdAt", header: "Создан", cell: (info) => <span className="text-xs text-ink-muted">{fmtRelative(info.getValue() as string)}</span> },
  ];

  const jobsColumns: ColumnDef<AdminJob>[] = [
    { accessorKey: "jobName", header: "Задача", cell: (info) => <div><div className="font-medium text-ink">{formatJobName(info.getValue() as string)}</div><div className="text-xs text-ink-muted">{formatQueueName(info.row.original.queueName)}</div></div> },
    { accessorKey: "status", header: "Статус", cell: (info) => <StatusBadge value={info.getValue() as any} /> },
    { accessorKey: "createdAt", header: "Создана", cell: (info) => <span className="text-xs text-ink-muted">{fmtRelative(info.getValue() as string)}</span> },
    { accessorKey: "errorMessage", header: "Ошибка", enableSorting: false, cell: (info) => <span className="text-xs text-ink-muted">{(info.getValue() as string | null) ?? "—"}</span> },
    { id: "actions", header: "Действие", enableSorting: false, cell: (info) => (
      <Button
        size="sm"
        variant="outline"
        className="h-8 border-line-subtle bg-surface-panel"
        disabled={!info.row.original.canRetry || retryJobMutation.isPending}
        onClick={async () => {
          try {
            await retryJobMutation.mutateAsync(info.row.original.id);
            toast.success("Повторный запуск выполнен");
          } catch {
            toast.error("Повторный запуск не удался");
          }
        }}
      >
        <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
        Повторить
      </Button>
    ) },
  ];

  const exportColumns: ColumnDef<ExportJob>[] = [
    { accessorKey: "exportType", header: "Экспорт", cell: (info) => <span className="font-medium text-ink">{formatExportType(info.getValue() as string)}</span> },
    { accessorKey: "format", header: "Формат", cell: (info) => <span className="chip uppercase">{info.getValue() as string}</span> },
    { accessorKey: "status", header: "Статус", cell: (info) => <StatusBadge value={info.getValue() as any} /> },
    { accessorKey: "requestedAt", header: "Запрошен", cell: (info) => <span className="text-xs text-ink-muted">{fmtRelative(info.getValue() as string)}</span> },
    { id: "download", header: "Файл", enableSorting: false, cell: (info) => (
      <Button
        size="sm"
        variant="outline"
        className="h-8 border-line-subtle bg-surface-panel"
        disabled={!info.row.original.canDownload || downloadExportMutation.isPending}
        onClick={async () => {
          try {
            await downloadExportMutation.mutateAsync(info.row.original.id);
          } catch {
            toast.error("Не удалось скачать экспорт");
          }
        }}
      >
        <Download className="mr-1.5 h-3.5 w-3.5" />
        Скачать
      </Button>
    ) },
  ];

  const auditColumns: ColumnDef<AuditEvent>[] = [
    { accessorKey: "action", header: "Событие", cell: (info) => <span className="font-medium text-ink">{formatAuditAction(info.getValue() as string)}</span> },
    { accessorKey: "targetType", header: "Цель", cell: (info) => <span className="chip">{formatTargetType(info.getValue() as string)}</span> },
    { accessorKey: "status", header: "Статус", cell: (info) => <StatusBadge value={info.getValue() as any} /> },
    { accessorKey: "requestId", header: "ID запроса", cell: (info) => <span className="text-[11px] text-ink-muted">{(info.getValue() as string | null) ?? "—"}</span> },
    { accessorKey: "createdAt", header: "Время", cell: (info) => <span className="text-xs text-ink-muted">{fmtRelative(info.getValue() as string)}</span> },
  ];

  const metrics = useMemo(() => freshnessQuery.data, [freshnessQuery.data]);
  const health = healthQuery.data;

  return (
    <>
      <PageHeader
        eyebrow="Операции и контроль"
        title="Администрирование"
        description="Пользователи, роли, фоновые задачи, экспортные артефакты, журнал аудита и состояние операционного контура."
      />

      {topError ? (
        <QueryErrorState
          error={topError}
          title="Операционная панель пока недоступна"
          onRetry={() => {
            void freshnessQuery.refetch();
            void healthQuery.refetch();
            void usersQuery.refetch();
            void jobsQuery.refetch();
            void auditQuery.refetch();
            void exportJobsQuery.refetch();
          }}
        />
      ) : null}

      <section className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {metrics ? (
          <>
            <KpiCard label="Ошибки джобов" value={metrics.failedJobsCount} format="int" icon={Wrench} emphasis={metrics.failedJobsCount > 0 ? "danger" : "default"} />
            <KpiCard label="В очереди" value={metrics.pendingJobsCount} format="int" icon={Activity} emphasis={metrics.pendingJobsCount > 0 ? "warning" : "default"} />
            <KpiCard label="Экспортов в работе" value={metrics.exportBacklogCount} format="int" icon={Archive} emphasis={metrics.exportBacklogCount > 0 ? "brand" : "default"} />
            <KpiCard label="Упавших экспортов" value={metrics.failedExportsCount} format="int" icon={Download} emphasis={metrics.failedExportsCount > 0 ? "danger" : "default"} />
            <KpiCard label="Продажи" value={metrics.lastSalesIngestAt ? fmtRelative(metrics.lastSalesIngestAt) : "—"} format="raw" icon={History} />
            <KpiCard label="Склад" value={metrics.lastStockSnapshotAt ? fmtRelative(metrics.lastStockSnapshotAt) : "—"} format="raw" icon={ShieldCheck} />
            <KpiCard label="Резерв" value={metrics.lastReserveRefreshAt ? fmtRelative(metrics.lastReserveRefreshAt) : "—"} format="raw" icon={RefreshCw} />
          </>
        ) : (
          Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-[120px]" />)
        )}
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="panel p-5 xl:col-span-2">
          <div className="mb-4 flex items-center justify-between">
            <SectionTitle>Пользователи и роли</SectionTitle>
            <span className="chip">{usersQuery.data?.length ?? 0} пользователей</span>
          </div>
          <DataTable
            data={usersQuery.data ?? []}
            columns={usersColumns}
            loading={usersQuery.isLoading}
            searchPlaceholder="Поиск по имени или email…"
            density="compact"
            emptyTitle="Пользователи не найдены"
          />
        </div>
        <div className="panel p-5">
          <div className="mb-4 flex items-center justify-between">
            <SectionTitle>Контур окружения</SectionTitle>
            <StatusBadge value={health?.databaseOk ? "healthy" : "critical"} />
          </div>
          {health ? (
            <div className="space-y-3 text-sm">
              <MetricRow label="Окружение" value={formatEnvironment(health.appEnv)} />
              <MetricRow label="Релиз" value={health.appRelease ?? "локально"} />
              <MetricRow label="Отладка" value={health.appDebug ? "вкл" : "выкл"} />
              <MetricRow label="Redis" value={health.redisConfigured ? "настроен" : "не задан"} />
              <MetricRow label="Хранилище" value={formatStorageMode(health.objectStorageMode)} />
              <MetricRow label="Асинхронный экспорт" value={health.exportAsyncEnabled ? `вкл · от ${health.exportAsyncRowThreshold} строк` : "выкл"} />
              <MetricRow label="Режим схемы" value={formatSchemaMode(health.startupSchemaMode)} />
              <MetricRow label="Провайдер ИИ" value={formatAssistantProvider(health.assistantProvider)} />
              <MetricRow label="Sentry" value={health.sentryEnabled ? "вкл" : "выкл"} />
              <MetricRow label="OpenTelemetry" value={health.otelEnabled ? "вкл" : "выкл"} />
              <MetricRow label="Очереди" value={health.workerQueues.map(formatQueueName).join(", ")} />
              <MetricRow label="Заголовок request id" value={health.requestIdHeader} />
              <MetricRow label="Разрешённых origin" value={String(health.corsOrigins.length)} />
              {health.environmentWarnings.length ? (
                <div className="rounded-md border border-warning/30 bg-warning/5 p-3">
                  <div className="mb-2 text-[11px] uppercase tracking-wide text-warning">Операционные предупреждения</div>
                  <div className="space-y-1 text-xs text-ink-secondary">
                    {health.environmentWarnings.map((warning) => (
                      <div key={warning}>• {warning}</div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="space-y-3">
              <Skeleton className="h-8" />
              <Skeleton className="h-8" />
              <Skeleton className="h-8" />
            </div>
          )}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div className="panel p-5">
          <div className="mb-4 flex items-center justify-between">
            <SectionTitle>Фоновые задачи</SectionTitle>
            <span className="chip">{jobsQuery.data?.meta.total ?? 0}</span>
          </div>
          <DataTable
            data={jobsQuery.data?.items ?? []}
            columns={jobsColumns}
            loading={jobsQuery.isLoading}
            searchPlaceholder="Поиск по имени задачи…"
            density="compact"
            rightToolbar={
              <div className="flex flex-wrap items-center gap-2">
                <FilterPillGroup
                  value={jobStatusFilter}
                  onChange={setJobStatusFilter}
                  options={[
                    { value: "all", label: "Все" },
                    { value: "queued", label: "В очереди" },
                    { value: "running", label: "В работе" },
                    { value: "failed", label: "С ошибкой" },
                  ]}
                />
                <FilterPillGroup
                  value={jobQueueFilter}
                  onChange={setJobQueueFilter}
                  options={[
                    { value: "all", label: "Все очереди" },
                    { value: "ingestion", label: "Загрузка" },
                    { value: "analytics", label: "Аналитика" },
                    { value: "exports", label: "Экспорты" },
                  ]}
                />
              </div>
            }
            emptyTitle="Задачи не найдены"
          />
        </div>
        <div className="panel p-5">
          <div className="mb-4 flex items-center justify-between">
            <SectionTitle>Экспортные артефакты</SectionTitle>
            <span className="chip">{exportJobsQuery.data?.meta.total ?? 0}</span>
          </div>
          <DataTable
            data={exportJobsQuery.data?.items ?? []}
            columns={exportColumns}
            loading={exportJobsQuery.isLoading}
            searchPlaceholder="Поиск по типу экспорта…"
            density="compact"
            rightToolbar={
              <FilterPillGroup
                value={exportStatusFilter}
                onChange={setExportStatusFilter}
                options={[
                  { value: "all", label: "Все" },
                  { value: "queued", label: "В очереди" },
                  { value: "running", label: "В работе" },
                  { value: "failed", label: "С ошибкой" },
                  { value: "completed", label: "Готово" },
                ]}
              />
            }
            emptyTitle="Экспорты ещё не создавались"
          />
        </div>
      </section>

      <section className="panel p-5">
        <div className="mb-4 flex items-center justify-between">
          <SectionTitle>Журнал аудита</SectionTitle>
          <span className="chip">{auditQuery.data?.meta.total ?? 0} событий</span>
        </div>
        <DataTable
          data={auditQuery.data?.items ?? []}
          columns={auditColumns}
          loading={auditQuery.isLoading}
          searchPlaceholder="Поиск по событию, цели или id запроса…"
          density="compact"
          emptyTitle="События аудита пока не найдены"
        />
      </section>
    </>
  );
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 rounded-md border border-line-subtle bg-surface-muted/30 px-3 py-2">
      <span className="text-ink-muted">{label}</span>
      <span className="text-right font-medium text-ink">{value}</span>
    </div>
  );
}

function formatCapabilitiesCount(count: number) {
  const rem10 = count % 10;
  const rem100 = count % 100;
  let suffix = "доступов";
  if (rem10 === 1 && rem100 !== 11) suffix = "доступ";
  else if (rem10 >= 2 && rem10 <= 4 && (rem100 < 12 || rem100 > 14)) suffix = "доступа";
  return `${count} ${suffix}`;
}

function formatQueueName(queueName: string) {
  return QUEUE_LABELS[queueName] ?? queueName;
}

function formatExportType(exportType: string) {
  return EXPORT_TYPE_LABELS[exportType] ?? exportType.replaceAll("_", " ");
}

function formatEnvironment(environment: string) {
  const labels: Record<string, string> = {
    development: "Разработка",
    staging: "Предпрод",
    production: "Боевое",
    test: "Тесты",
  };
  return labels[environment] ?? environment;
}

function formatStorageMode(mode: string) {
  const labels: Record<string, string> = {
    local: "Локальное хранилище",
    s3: "S3 / совместимое",
  };
  return labels[mode] ?? mode;
}

function formatSchemaMode(mode: string) {
  const labels: Record<string, string> = {
    auto_create: "Автосоздание",
    migrations_only: "Только миграции",
  };
  return labels[mode] ?? mode;
}

function formatAssistantProvider(provider: string) {
  const labels: Record<string, string> = {
    deterministic: "Детерминированный",
    openai_compatible: "Совместимый с OpenAI",
  };
  return labels[provider] ?? provider;
}

function formatJobName(jobName: string) {
  const labels: Record<string, string> = {
    validate_upload: "Проверка загрузки",
    apply_upload: "Применение загрузки",
    refresh_analytics: "Обновление аналитики",
    generate_export: "Генерация экспорта",
    process_upload_batch: "Обработка batch",
    suggest_upload_mapping: "Подсказка сопоставления",
  };
  return labels[jobName] ?? jobName;
}

function formatAuditAction(action: string) {
  const labels: Record<string, string> = {
    "auth.permission_denied": "Отказ в доступе",
    "exports.job_created": "Создан экспорт",
    "exports.job_downloaded": "Скачан экспорт",
    "exports.job_failed": "Экспорт завершился ошибкой",
    "reserve.run_created": "Создан расчёт резерва",
    "uploads.file_uploaded": "Файл загружен",
    "uploads.batch_uploaded": "Пакет файлов загружен",
  };
  return labels[action] ?? action;
}

function formatTargetType(targetType: string) {
  const labels: Record<string, string> = {
    export_job: "Экспорт",
    upload_batch: "Пакет загрузки",
    upload_file: "Файл загрузки",
    reserve_run: "Запуск резерва",
    user: "Пользователь",
    job_run: "Фоновая задача",
  };
  return labels[targetType] ?? targetType;
}

function FilterPillGroup({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {options.map((option) => (
        <Button
          key={option.value}
          size="sm"
          variant="outline"
          className={
            value === option.value
              ? "h-8 border-brand/40 bg-brand/10 text-brand"
              : "h-8 border-line-subtle bg-surface-panel"
          }
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </Button>
      ))}
    </div>
  );
}
