import { useEffect, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { PageHeader } from "@/components/ui-ext/PageHeader";
import { DataTable } from "@/components/ui-ext/DataTable";
import { listSkus } from "@/services/sku.service";
import type { Sku } from "@/types";

export default function SkuExplorerPage() {
  const [skus, setSkus] = useState<Sku[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { listSkus().then((s) => { setSkus(s); setLoading(false); }); }, []);

  const columns: ColumnDef<any>[] = [
    { accessorKey: "article", header: "Article", cell: (i) => <span className="text-num font-medium text-ink">{i.getValue() as string}</span> },
    { accessorKey: "name", header: "Product" },
    { accessorKey: "category", header: "Category", cell: (i) => <span className="chip">{i.getValue() as string}</span> },
    { accessorKey: "brand", header: "Brand" },
    { accessorKey: "unit", header: "Unit", meta: { align: "center" } },
    { accessorKey: "active", header: "Status", cell: (i) => (i.getValue() ? <span className="text-success text-xs">Active</span> : <span className="text-ink-muted text-xs">Inactive</span>) },
  ];

  return (
    <>
      <PageHeader eyebrow="Catalog" title="SKU explorer" description="Drill into individual SKUs across the master catalog with stock, sales and reserve context." />
      <DataTable data={skus} columns={columns} loading={loading} searchKeys={["article", "name", "category", "brand"] as any} searchPlaceholder="Search SKUs by article, name, category…" density="compact" initialPageSize={20} />
    </>
  );
}
