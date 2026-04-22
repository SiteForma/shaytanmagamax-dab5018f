import { useEffect, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { PageHeader } from "@/components/ui-ext/PageHeader";
import { DataTable } from "@/components/ui-ext/DataTable";
import { StatusBadge } from "@/components/ui-ext/StatusBadge";
import { getInboundTimeline, type InboundWithRefs } from "@/services/inbound.service";
import { fmtDate, fmtInt } from "@/lib/formatters";

export default function InboundPage() {
  const [rows, setRows] = useState<InboundWithRefs[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { getInboundTimeline().then((r) => { setRows(r); setLoading(false); }); }, []);

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
      <DataTable data={rows} columns={columns} loading={loading} searchPlaceholder="Поиск поставок…" density="compact" initialPageSize={20} />
    </>
  );
}
