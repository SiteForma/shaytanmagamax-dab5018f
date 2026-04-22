import { useEffect, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { PageHeader } from "@/components/ui-ext/PageHeader";
import { DataTable } from "@/components/ui-ext/DataTable";
import { FilterChips } from "@/components/ui-ext/FilterChips";
import { getStockCoverage, type StockCoverageRow } from "@/services/stock.service";
import { fmtInt, fmtMonths } from "@/lib/formatters";

const WAREHOUSE_LABEL: Record<string, string> = {
  Shchelkovo: "Щёлково",
  Krasnodar: "Краснодар",
  Simferopol: "Симферополь",
};

export default function StockPage() {
  const [rows, setRows] = useState<StockCoverageRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [risk, setRisk] = useState<string>("all");

  useEffect(() => {
    setLoading(true);
    getStockCoverage({ risk: risk === "all" ? "all" : (risk as any) }).then((r) => { setRows(r); setLoading(false); });
  }, [risk]);

  const columns: ColumnDef<any>[] = [
    { accessorKey: "sku.article", header: "Артикул", cell: (i) => <span className="text-num font-medium text-ink">{i.row.original.sku.article}</span> },
    { accessorKey: "sku.name", header: "Товар", cell: (i) => i.row.original.sku.name },
    { accessorKey: "sku.category", header: "Категория", cell: (i) => <span className="chip">{i.row.original.sku.category}</span> },
    { accessorKey: "warehouse", header: "Склад", cell: (i) => WAREHOUSE_LABEL[i.getValue() as string] ?? (i.getValue() as string) },
    { accessorKey: "free", header: "Свободно", meta: { align: "right", mono: true }, cell: (i) => fmtInt(i.getValue() as number) },
    { accessorKey: "reservedLike", header: "Резерв-подобно", meta: { align: "right", mono: true }, cell: (i) => fmtInt(i.getValue() as number) },
    { accessorKey: "demandPerMonth", header: "Спрос/мес.", meta: { align: "right", mono: true }, cell: (i) => fmtInt(i.getValue() as number) },
    { accessorKey: "coverageMonths", header: "Покрытие", meta: { align: "right", mono: true }, cell: (i) => {
      const v = i.getValue() as number;
      const tone = v < 1 ? "text-danger" : v < 2 ? "text-warning" : "text-ink";
      return <span className={tone}>{fmtMonths(v)}</span>;
    } },
  ];

  return (
    <>
      <PageHeader eyebrow="Операции" title="Склад и покрытие" description="Свободный остаток, резерв-подобный объём и прогноз покрытия в месяцах по каталогу." />
      <FilterChips value={risk} onChange={setRisk} allLabel="Все" options={[{ value: "low_stock", label: "Низкий остаток" }, { value: "overstock", label: "Излишки" }]} />
      <DataTable data={rows} columns={columns} loading={loading} searchPlaceholder="Поиск по артикулу или наименованию…" density="compact" initialPageSize={20} />
    </>
  );
}
