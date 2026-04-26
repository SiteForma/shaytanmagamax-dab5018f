import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import type { ColumnDef } from "@tanstack/react-table";
import { PageHeader } from "@/components/ui-ext/PageHeader";
import { DataTable } from "@/components/ui-ext/DataTable";
import { FilterChips } from "@/components/ui-ext/FilterChips";
import { QueryErrorState } from "@/components/ui-ext/QueryErrorState";
import { StatusBadge } from "@/components/ui-ext/StatusBadge";
import { useInboundSyncMutation, useInboundTimelineQuery } from "@/hooks/queries/use-inbound";
import { useHasCapability } from "@/hooks/queries/use-auth";
import { fmtDate, fmtInt } from "@/lib/formatters";
import { Button } from "@/components/ui/button";
import { RefreshCw } from "lucide-react";
import { toast } from "sonner";

export default function InboundPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const status = searchParams.get("status") ?? "all";
  const inboundQuery = useInboundTimelineQuery();
  const syncMutation = useInboundSyncMutation();
  const canSync = useHasCapability("inbound:sync");
  const filteredRows = useMemo(
    () => {
      const rows = inboundQuery.data ?? [];
      return status === "all" ? rows : rows.filter((row) => row.status === status);
    },
    [inboundQuery.data, status],
  );

  const columns: ColumnDef<any>[] = [
    { accessorKey: "containerRef", header: "Контейнер", cell: (i) => i.getValue() || "—" },
    { accessorKey: "sku.article", header: "Артикул", cell: (i) => <span className="text-num font-medium text-ink">{i.row.original.sku.article}</span> },
    { accessorKey: "sku.name", header: "Товар", cell: (i) => i.row.original.sku.name },
    { accessorKey: "qty", header: "В пути", meta: { align: "right", mono: true }, cell: (i) => fmtInt(i.getValue() as number) },
    { accessorKey: "clientOrderQty", header: "Заказы клиентов", meta: { align: "right", mono: true }, cell: (i) => fmtInt(i.getValue() as number) },
    { accessorKey: "freeStockAfterAllocation", header: "Свободный остаток", meta: { align: "right", mono: true }, cell: (i) => <span className="text-success">{fmtInt(i.getValue() as number)}</span> },
    { accessorKey: "eta", header: "Прибытие", cell: (i) => fmtDate(i.getValue() as string) },
    { accessorKey: "clients", header: "Распределение", cell: (i) => {
      const allocations = i.row.original.clientAllocations as Record<string, number>;
      const parts = Object.entries(allocations ?? {}).slice(0, 4).map(([name, qty]) => `${name}: ${fmtInt(qty)}`);
      const extra = Object.keys(allocations ?? {}).length - parts.length;
      return parts.length ? `${parts.join(", ")}${extra > 0 ? ` +${extra}` : ""}` : "—";
    } },
    { accessorKey: "status", header: "Статус", cell: (i) => <StatusBadge value={i.getValue() as any} /> },
  ];

  return (
    <>
      <PageHeader
        eyebrow="Поставки"
        title="Товары в пути"
        description="Данные из Google Sheet: «В пути» — количество в контейнере, «Свободный остаток» — остаток после распределения по клиентам."
        actions={
          <Button
            variant="outline"
            size="sm"
            className="h-9 border-line-subtle bg-surface-panel"
            disabled={!canSync || syncMutation.isPending}
            onClick={async () => {
              try {
                const result = await syncMutation.mutateAsync();
                toast.success(`Синхронизировано: ${fmtInt(result.rowsImported)} строк, в пути ${fmtInt(result.totalInTransitQty)} шт.`);
              } catch {
                toast.error("Не удалось синхронизировать Google Sheet");
              }
            }}
          >
            <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${syncMutation.isPending ? "animate-spin" : ""}`} />
            {syncMutation.isPending ? "Синхронизация…" : "Синхронизировать"}
          </Button>
        }
      />
      {inboundQuery.error ? (
        <QueryErrorState
          error={inboundQuery.error}
          title="Лента поставок пока недоступна"
          onRetry={() => void inboundQuery.refetch()}
        />
      ) : null}
      <FilterChips
        value={status}
        onChange={(value) => {
          const next = new URLSearchParams(searchParams);
          if (value === "all") next.delete("status");
          else next.set("status", value);
          setSearchParams(next);
        }}
        allLabel="Все"
        options={[
          { value: "confirmed", label: "Подтверждены" },
          { value: "in_transit", label: "В пути" },
          { value: "delayed", label: "Задержка" },
          { value: "uncertain", label: "Неопределённо" },
        ]}
      />
      <DataTable
        data={filteredRows}
        columns={columns}
        loading={inboundQuery.isLoading}
        searchPlaceholder="Поиск поставок…"
        density="compact"
        initialPageSize={20}
      />
    </>
  );
}
