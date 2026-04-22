import { useEffect, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { PageHeader } from "@/components/ui-ext/PageHeader";
import { DataTable } from "@/components/ui-ext/DataTable";
import { FilterChips } from "@/components/ui-ext/FilterChips";
import { getStockCoverage, type StockCoverageRow } from "@/services/stock.service";
import { fmtInt, fmtMonths } from "@/lib/formatters";

export default function StockPage() {
  const [rows, setRows] = useState<StockCoverageRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [risk, setRisk] = useState<string>("all");

  useEffect(() => {
    setLoading(true);
    getStockCoverage({ risk: risk === "all" ? "all" : (risk as any) }).then((r) => { setRows(r); setLoading(false); });
  }, [risk]);

  const columns: ColumnDef<any>[] = [
    { accessorKey: "sku.article", header: "Article", cell: (i) => <span className="text-num font-medium text-ink">{i.row.original.sku.article}</span> },
    { accessorKey: "sku.name", header: "Product", cell: (i) => i.row.original.sku.name },
    { accessorKey: "sku.category", header: "Category", cell: (i) => <span className="chip">{i.row.original.sku.category}</span> },
    { accessorKey: "warehouse", header: "Warehouse" },
    { accessorKey: "free", header: "Free", meta: { align: "right", mono: true }, cell: (i) => fmtInt(i.getValue() as number) },
    { accessorKey: "reservedLike", header: "Reserved-like", meta: { align: "right", mono: true }, cell: (i) => fmtInt(i.getValue() as number) },
    { accessorKey: "demandPerMonth", header: "Demand/mo", meta: { align: "right", mono: true }, cell: (i) => fmtInt(i.getValue() as number) },
    { accessorKey: "coverageMonths", header: "Coverage", meta: { align: "right", mono: true }, cell: (i) => {
      const v = i.getValue() as number;
      const tone = v < 1 ? "text-danger" : v < 2 ? "text-warning" : "text-ink";
      return <span className={tone}>{fmtMonths(v)}</span>;
    } },
  ];

  return (
    <>
      <PageHeader eyebrow="Operations" title="Stock & coverage" description="Free stock, reserved-like volume and projected coverage in months across the catalog." />
      <FilterChips value={risk} onChange={setRisk} options={[{ value: "low_stock", label: "Low stock" }, { value: "overstock", label: "Overstocked" }]} />
      <DataTable data={rows} columns={columns} loading={loading} searchPlaceholder="Search by article or name…" density="compact" initialPageSize={20} />
    </>
  );
}
