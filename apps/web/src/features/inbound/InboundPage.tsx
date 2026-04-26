import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import type { ColumnDef } from "@tanstack/react-table";
import { PageHeader } from "@/components/ui-ext/PageHeader";
import { DataTable } from "@/components/ui-ext/DataTable";
import { FilterChips } from "@/components/ui-ext/FilterChips";
import { QueryErrorState } from "@/components/ui-ext/QueryErrorState";
import { StatusBadge } from "@/components/ui-ext/StatusBadge";
import { useInboundTimelineQuery } from "@/hooks/queries/use-inbound";
import type { InboundWithRefs } from "@/services/inbound.service";
import { fmtDate, fmtInt } from "@/lib/formatters";

export default function InboundPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const status = searchParams.get("status") ?? "all";
  const inboundQuery = useInboundTimelineQuery();
  const filteredRows = useMemo(
    () => {
      const rows = inboundQuery.data ?? [];
      return status === "all" ? rows : rows.filter((row) => row.status === status);
    },
    [inboundQuery.data, status],
  );

  const columns: ColumnDef<any>[] = [
    { accessorKey: "sku.article", header: "Артикул", cell: (i) => <span className="text-num font-medium text-ink">{i.row.original.sku.article}</span> },
    { accessorKey: "sku.name", header: "Товар", cell: (i) => i.row.original.sku.name },
    { accessorKey: "qty", header: "Кол-во", meta: { align: "right", mono: true }, cell: (i) => fmtInt(i.getValue() as number) },
    { accessorKey: "eta", header: "Прибытие", cell: (i) => fmtDate(i.getValue() as string) },
    { accessorKey: "reserveImpact", header: "Закрывает дефицит", meta: { align: "right", mono: true }, cell: (i) => <span className="text-brand">{fmtInt(i.getValue() as number)}</span> },
    { accessorKey: "clients", header: "Клиенты", cell: (i) => (i.row.original.clients as any[]).map((c) => c.name).join(", ") },
    { accessorKey: "status", header: "Статус", cell: (i) => <StatusBadge value={i.getValue() as any} /> },
  ];

  return (
    <>
      <PageHeader eyebrow="Поставки" title="Входящие поставки" description="Ближайшие поступления по SKU и их прогнозируемое влияние на текущий дефицит." />
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
