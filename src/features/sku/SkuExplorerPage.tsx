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
    { accessorKey: "article", header: "Артикул", cell: (i) => <span className="text-num font-medium text-ink">{i.getValue() as string}</span> },
    { accessorKey: "name", header: "Товар" },
    { accessorKey: "category", header: "Категория", cell: (i) => <span className="chip">{i.getValue() as string}</span> },
    { accessorKey: "brand", header: "Бренд" },
    { accessorKey: "unit", header: "Ед.", meta: { align: "center" }, cell: (i) => ({ pcs: "шт.", set: "комп.", m: "м" } as any)[i.getValue() as string] ?? (i.getValue() as string) },
    { accessorKey: "active", header: "Статус", cell: (i) => (i.getValue() ? <span className="text-success text-xs">Активен</span> : <span className="text-ink-muted text-xs">Не активен</span>) },
  ];

  return (
    <>
      <PageHeader eyebrow="Каталог" title="Каталог SKU" description="Подробная разбивка по каждому SKU мастер-каталога с контекстом по складу, продажам и резерву." />
      <DataTable data={skus} columns={columns} loading={loading} searchKeys={["article", "name", "category", "brand"] as any} searchPlaceholder="Поиск по артикулу, наименованию, категории…" density="compact" initialPageSize={20} />
    </>
  );
}
