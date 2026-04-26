import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { ColumnDef } from "@tanstack/react-table";
import { toast } from "sonner";
import { PageHeader } from "@/components/ui-ext/PageHeader";
import { DataTable } from "@/components/ui-ext/DataTable";
import { StatusBadge } from "@/components/ui-ext/StatusBadge";
import { FilterChips } from "@/components/ui-ext/FilterChips";
import { QueryErrorState } from "@/components/ui-ext/QueryErrorState";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useReserveCalculationMutation } from "@/hooks/queries/use-reserve";
import { useClientsQuery } from "@/hooks/queries/use-clients";
import { useSkusQuery } from "@/hooks/queries/use-sku";
import { useReserveExportMutation } from "@/hooks/mutations/use-exports";
import { useHasCapability } from "@/hooks/queries/use-auth";
import type { ReserveRow, ReserveRunSummary, ReserveStatus } from "@/types";
import { fmtCompact, fmtDate, fmtInt, fmtMonths, fmtRelative } from "@/lib/formatters";
import { Calculator, Download } from "lucide-react";
import {
  basisWindowLabel,
  fallbackLevelLabel,
  reserveStrategyLabel,
  scopeTypeLabel,
} from "@/lib/reserve-labels";

const STATUS_OPTIONS: { value: ReserveStatus; label: string }[] = [
  { value: "critical", label: "Критично" },
  { value: "warning", label: "Внимание" },
  { value: "healthy", label: "Норма" },
  { value: "no_history", label: "Нет истории" },
  { value: "overstocked", label: "Избыток" },
];

type DemandStrategy =
  | "weighted_recent_average"
  | "strict_recent_average"
  | "conservative_fallback";

export default function ReservePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [rows, setRows] = useState<ReserveRow[]>([]);
  const [runMeta, setRunMeta] = useState<ReserveRunSummary | null>(null);
  const [drawer, setDrawer] = useState<ReserveRow | null>(null);
  const clientsQuery = useClientsQuery();
  const skusQuery = useSkusQuery();
  const reserveMutation = useReserveCalculationMutation();
  const exportMutation = useReserveExportMutation();
  const canExport = useHasCapability("exports:generate");
  const canRunReserve = useHasCapability("reserve:run");
  const clientIds = useMemo(() => clientsQuery.data ?? [], [clientsQuery.data]);
  const skus = useMemo(() => skusQuery.data ?? [], [skusQuery.data]);
  const selectedClientId = searchParams.get("client") ?? "";
  const selectedSkuIds = searchParams.get("skus")?.split(",").filter(Boolean) ?? [];
  const horizon = Number(searchParams.get("horizon") ?? "3") as 2 | 3;
  const safety = Number(searchParams.get("safety") ?? "1.1");
  const demandStrategy = (searchParams.get("strategy") ?? "weighted_recent_average") as DemandStrategy;
  const statusFilter = (searchParams.get("status") ?? "all") as ReserveStatus | "all";

  useEffect(() => {
    if (!clientIds.length) {
      return;
    }
    const shouldSeedClient = !selectedClientId;
    const shouldSeedSkus = selectedSkuIds.length === 0 && skus.length > 0;
    if (!shouldSeedClient && !shouldSeedSkus) {
      return;
    }
    const next = new URLSearchParams(searchParams);
    if (shouldSeedClient) {
      next.set("client", clientIds[0].id);
    }
    if (shouldSeedSkus) {
      next.set("skus", skus.slice(0, 4).map((item) => item.id).join(","));
    }
    setSearchParams(next, { replace: true });
  }, [clientIds, searchParams, selectedClientId, selectedSkuIds.length, setSearchParams, skus]);

  async function run() {
    if (!selectedClientId) return;
    try {
      const result = await reserveMutation.mutateAsync({
        clientIds: [selectedClientId],
        skuIds: selectedSkuIds.length ? selectedSkuIds : undefined,
        reserveMonths: horizon,
        safetyFactor: safety,
        demandStrategy,
        horizonDays: 60,
        persistRun: true,
      });
      setRows(result.rows);
      setRunMeta(result.run);
    } catch {
      toast.error("Не удалось пересчитать резерв");
    }
  }

  useEffect(() => {
    if (!selectedClientId || !clientIds.length) {
      return;
    }
    void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedClientId, selectedSkuIds.join("|"), demandStrategy, horizon, safety]);

  const selectedClient = clientIds.find((client) => client.id === selectedClientId) ?? null;

  const filtered = useMemo(
    () => (statusFilter === "all" ? rows : rows.filter((row) => row.status === statusFilter)),
    [rows, statusFilter],
  );

  const counts = useMemo(() => {
    const next: Partial<Record<ReserveStatus, number>> = {};
    rows.forEach((row) => {
      next[row.status as ReserveStatus] = (next[row.status as ReserveStatus] ?? 0) + 1;
    });
    return next;
  }, [rows]);

  const totals = useMemo(
    () => ({
      target: rows.reduce((accumulator, row) => accumulator + row.targetReserveQty, 0),
      shortage: rows.reduce((accumulator, row) => accumulator + row.shortageQty, 0),
      inbound: rows.reduce((accumulator, row) => accumulator + row.inboundWithinHorizon, 0),
    }),
    [rows],
  );

  const setupError = clientsQuery.error ?? skusQuery.error;
  const calculationError = reserveMutation.error;

  const columns: ColumnDef<ReserveRow>[] = [
    { accessorKey: "clientName", header: "Клиент", cell: (info) => <span className="font-medium text-ink">{info.getValue() as string}</span> },
    { accessorKey: "article", header: "Артикул", cell: (info) => <span className="text-num text-ink-secondary">{info.getValue() as string}</span> },
    { accessorKey: "productName", header: "Товар", cell: (info) => <span className="truncate text-ink">{info.getValue() as string}</span> },
    { accessorKey: "avgMonthly3m", header: "Продажи 3м", meta: { align: "right", mono: true }, cell: (info) => fmtInt(info.getValue() as number) },
    { accessorKey: "avgMonthly6m", header: "Продажи 6м", meta: { align: "right", mono: true }, cell: (info) => fmtInt(info.getValue() as number) },
    { accessorKey: "demandPerMonth", header: "Спрос/мес.", meta: { align: "right", mono: true }, cell: (info) => fmtInt(info.getValue() as number) },
    { accessorKey: "targetReserveQty", header: "Цель", meta: { align: "right", mono: true }, cell: (info) => fmtInt(info.getValue() as number) },
    { accessorKey: "freeStock", header: "Свободно", meta: { align: "right", mono: true }, cell: (info) => fmtInt(info.getValue() as number) },
    { accessorKey: "inboundWithinHorizon", header: "Поставка", meta: { align: "right", mono: true }, cell: (info) => fmtInt(info.getValue() as number) },
    { accessorKey: "shortageQty", header: "Дефицит", meta: { align: "right", mono: true }, cell: (info) => {
      const value = info.getValue() as number;
      return <span className={value > 0 ? "text-danger font-medium" : "text-ink-muted"}>{value > 0 ? `−${fmtInt(value)}` : "0"}</span>;
    } },
    { accessorKey: "coverageMonths", header: "Покрытие", meta: { align: "right", mono: true }, cell: (info) => {
      const value = info.getValue() as number | null;
      return value == null ? "—" : fmtMonths(value);
    } },
    { accessorKey: "status", header: "Статус", cell: (info) => <StatusBadge value={info.getValue() as ReserveStatus} /> },
  ];

  return (
    <>
      <PageHeader
        eyebrow="Ключевой процесс"
        title="Расчёт резерва"
        description="Целевой резерв по каждому клиенту DIY и SKU с настраиваемыми горизонтом, коэффициентом безопасности и базой спроса."
        actions={
          <>
            <Button
              variant="outline"
              size="sm"
              className="h-9 border-line-subtle bg-surface-panel"
              disabled={!canExport || !runMeta?.id || exportMutation.isPending}
              onClick={async () => {
                if (!runMeta?.id) return;
                try {
                  const job = await exportMutation.mutateAsync(runMeta.id);
                  toast.success(job.canDownload ? "Экспорт расчёта готов" : "Экспорт расчёта поставлен в очередь");
                } catch {
                  toast.error("Не удалось сформировать экспорт");
                }
              }}
            >
              <Download className="mr-1.5 h-3.5 w-3.5" />
              {exportMutation.isPending ? "Экспорт…" : "Экспорт"}
            </Button>
            <Button size="sm" disabled={!canRunReserve} onClick={() => void run()} className="h-9 bg-brand text-brand-foreground hover:bg-brand-hover">
              <Calculator className="mr-1.5 h-3.5 w-3.5" />
              Пересчитать
            </Button>
          </>
        }
      />

      {setupError ? (
        <QueryErrorState
          error={setupError}
          title="Контекст расчёта пока недоступен"
          onRetry={() => {
            void clientsQuery.refetch();
            void skusQuery.refetch();
          }}
        />
      ) : null}
      {calculationError ? (
        <QueryErrorState
          error={calculationError}
          title="Расчёт резерва завершился ошибкой"
          onRetry={() => void run()}
        />
      ) : null}

      <section className="panel p-5">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-5">
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-ink-muted">DIY-клиент</label>
            <select
              value={selectedClientId}
              onChange={(event) => {
                const next = new URLSearchParams(searchParams);
                next.set("client", event.target.value);
                setSearchParams(next);
              }}
              className="h-10 w-full rounded-md border border-line-subtle bg-surface-panel px-3 text-sm focus-ring"
            >
              {clientIds.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}
            </select>
            {selectedClient ? (
              <div className="mt-2 text-xs text-ink-muted">
                {selectedClient.region} · резерв {selectedClient.reserveMonths} мес.
              </div>
            ) : null}
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-ink-muted">SKU в расчёте</label>
            <select
              multiple
              value={selectedSkuIds}
              onChange={(event) => {
                const next = new URLSearchParams(searchParams);
                const nextSkuIds = Array.from(event.target.selectedOptions).map((option) => option.value);
                if (nextSkuIds.length) next.set("skus", nextSkuIds.join(","));
                else next.delete("skus");
                setSearchParams(next);
              }}
              className="h-28 w-full rounded-md border border-line-subtle bg-surface-panel p-2 text-sm focus-ring"
            >
              {skus.map((sku) => <option key={sku.id} value={sku.id}>{sku.article} · {sku.name}</option>)}
            </select>
            <div className="mt-2 text-xs text-ink-muted">
              {selectedSkuIds.length > 0 ? `${selectedSkuIds.length} SKU выбрано` : "Если список пустой, считаем весь ассортимент клиента"}
            </div>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-ink-muted">Горизонт резерва</label>
            <div className="inline-flex rounded-md border border-line-subtle bg-surface-panel p-0.5">
              {[2, 3].map((value) => (
                <button
                  key={value}
                  onClick={() => {
                    const next = new URLSearchParams(searchParams);
                    next.set("horizon", String(value));
                    setSearchParams(next);
                  }}
                  className={`px-3 py-1.5 text-xs font-medium rounded ${horizon === value ? "bg-brand text-brand-foreground" : "text-ink-secondary hover:text-ink"}`}
                >
                  {value} мес.
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-ink-muted">Коэффициент безопасности</label>
            <input
              type="range"
              min="1"
              max="1.5"
              step="0.05"
              value={safety}
              onChange={(event) => {
                const next = new URLSearchParams(searchParams);
                next.set("safety", String(Number(event.target.value).toFixed(2)));
                setSearchParams(next);
              }}
              className="w-full accent-brand"
            />
            <div className="mt-1 text-num text-xs text-ink-secondary">×{safety.toFixed(2)}</div>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-ink-muted">База спроса</label>
            <select
              value={demandStrategy}
              onChange={(event) => {
                const next = new URLSearchParams(searchParams);
                next.set("strategy", event.target.value);
                setSearchParams(next);
              }}
              className="h-9 w-full rounded-md border border-line-subtle bg-surface-panel px-2 text-sm focus-ring"
            >
              <option value="weighted_recent_average">Смешанная (3м + 6м)</option>
              <option value="strict_recent_average">Строгая недавняя</option>
              <option value="conservative_fallback">Консервативная с подстановкой</option>
            </select>
          </div>
        </div>
      </section>

      <section className="panel p-4">
        <div className="flex flex-wrap items-center gap-2 text-xs text-ink-secondary">
          <span className="chip">Срез: {scopeTypeLabel(runMeta?.scopeType)}</span>
          <span className="chip">Стратегия: {reserveStrategyLabel(runMeta?.demandStrategy)}</span>
          <span className="chip">Расчёт: {runMeta?.id ?? "—"}</span>
          <span className="chip">Строк: {fmtInt(runMeta?.rowCount ?? 0)}</span>
          <span className="chip">
            Создан: {runMeta?.createdAt ? `${fmtDate(runMeta.createdAt)} · ${fmtRelative(runMeta.createdAt)}` : "—"}
          </span>
        </div>
      </section>

      <section className="panel grid grid-cols-3 divide-x divide-line-subtle">
        {[
          { label: "Целевой резерв", val: totals.target, tone: "" },
          { label: "Общий дефицит", val: totals.shortage, tone: "text-danger" },
          { label: "Покрытие поставкой", val: totals.inbound, tone: "text-brand" },
        ].map((item) => (
          <div key={item.label} className="p-4">
            <div className="text-[11px] uppercase tracking-wide text-ink-muted">{item.label}</div>
            <div className={`text-num text-2xl font-semibold ${item.tone || "text-ink"}`}>{fmtCompact(item.val)}</div>
          </div>
        ))}
      </section>

      <FilterChips
        value={statusFilter}
        onChange={(value) => {
          const next = new URLSearchParams(searchParams);
          if (value === "all") next.delete("status");
          else next.set("status", value);
          setSearchParams(next);
        }}
        allLabel="Все"
        options={STATUS_OPTIONS.map((option) => ({ ...option, count: counts[option.value] }))}
      />

      <DataTable<ReserveRow>
        data={filtered}
        columns={columns as any}
        loading={clientsQuery.isLoading || skusQuery.isLoading || reserveMutation.isPending}
        searchKeys={["clientName", "article", "productName"] as (keyof ReserveRow)[]}
        searchPlaceholder="Поиск по клиенту, артикулу, товару…"
        density="compact"
        initialPageSize={20}
        onRowClick={setDrawer}
        emptyTitle="Подходящих позиций нет"
      />

      <Sheet open={!!drawer} onOpenChange={(open) => !open && setDrawer(null)}>
        <SheetContent className="w-[420px] border-l border-line-subtle bg-surface-elevated">
          {drawer ? (
            <>
              <SheetHeader>
                <SheetTitle className="text-ink">{drawer.productName}</SheetTitle>
                <SheetDescription className="text-xs text-ink-muted">
                  {drawer.article} · {drawer.category} · {drawer.clientName}
                </SheetDescription>
              </SheetHeader>
              <div className="mt-6 space-y-3 text-sm">
                {[
                  ["Средние продажи 3м", fmtInt(drawer.avgMonthly3m)],
                  ["Средние продажи 6м", fmtInt(drawer.avgMonthly6m)],
                  ["Спрос/мес.", fmtInt(drawer.demandPerMonth)],
                  ["Коэф. безопасности", `×${(drawer.safetyFactor ?? 1).toFixed(2)}`],
                  ["Целевой резерв", fmtInt(drawer.targetReserveQty)],
                  ["Учтено со склада", fmtInt(drawer.freeStock)],
                  ["Учтено из поставки", fmtInt(drawer.inboundWithinHorizon)],
                  ["Общий пул склада", fmtInt(drawer.totalFreeStockQty ?? drawer.freeStock)],
                  ["Общий пул поставок", fmtInt(drawer.totalInboundWithinHorizonQty ?? drawer.inboundWithinHorizon)],
                  ["Доступно", fmtInt(drawer.availableQty)],
                  ["Дефицит", drawer.shortageQty > 0 ? `−${fmtInt(drawer.shortageQty)}` : "0"],
                  ["Покрытие", drawer.coverageMonths == null ? "—" : fmtMonths(drawer.coverageMonths)],
                  ["Уровень подстановки", fallbackLevelLabel(drawer.fallbackLevel)],
                  ["Окно расчёта", basisWindowLabel(drawer.basisWindowUsed)],
                ].map(([key, value]) => (
                  <div key={key} className="flex items-baseline justify-between border-b border-line-subtle/60 pb-2">
                    <span className="text-ink-muted">{key}</span>
                    <span className="text-num font-medium text-ink">{value}</span>
                  </div>
                ))}
                <div className="rounded-md border border-line-subtle bg-surface-muted/40 p-3 text-xs text-ink-secondary">
                  {drawer.statusReason ?? "Причина статуса не указана."}
                </div>
                <div className="pt-2"><StatusBadge value={drawer.status} /></div>
              </div>
            </>
          ) : null}
        </SheetContent>
      </Sheet>
    </>
  );
}
