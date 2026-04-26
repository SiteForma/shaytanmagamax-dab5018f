import { useDeferredValue, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import type { ColumnDef, SortingState } from "@tanstack/react-table";
import { PageHeader } from "@/components/ui-ext/PageHeader";
import { DataTable } from "@/components/ui-ext/DataTable";
import { FilterChips } from "@/components/ui-ext/FilterChips";
import { QueryErrorState } from "@/components/ui-ext/QueryErrorState";
import { Skeleton } from "@/components/ui-ext/Skeleton";
import { usePotentialStockoutQuery, useStockCoverageQuery } from "@/hooks/queries/use-stock";
import { useSkusQuery } from "@/hooks/queries/use-sku";
import { useStockCoverageExportMutation } from "@/hooks/mutations/use-exports";
import { useHasCapability } from "@/hooks/queries/use-auth";
import type { PotentialStockoutRow, StockCoverageRow } from "@/services/stock.service";
import { StatusBadge } from "@/components/ui-ext/StatusBadge";
import { fmtInt, fmtMonths } from "@/lib/formatters";
import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";
import { toast } from "sonner";

const WAREHOUSE_LABEL: Record<string, string> = {
  Shchelkovo: "Щёлково",
  Krasnodar: "Краснодар",
  Simferopol: "Симферополь",
};

export default function StockPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const risk = searchParams.get("risk") ?? "all";
  const category = searchParams.get("category") ?? "";
  const search = searchParams.get("query") ?? "";
  const page = Number(searchParams.get("page") ?? "1");
  const pageSize = Number(searchParams.get("pageSize") ?? "20");
  const sortBy = searchParams.get("sort") ?? "shortage_qty_total";
  const sortDir = (searchParams.get("dir") ?? "desc") as "asc" | "desc";
  const deferredSearch = useDeferredValue(search);
  const exportMutation = useStockCoverageExportMutation();
  const canExport = useHasCapability("exports:generate");
  const filters = useMemo(
    () => ({
      risk: risk === "all" ? "all" : (risk as any),
      category: category || undefined,
      search: deferredSearch || undefined,
      page,
      pageSize,
      sortBy: sortBy as any,
      sortDir,
    }),
    [category, deferredSearch, page, pageSize, risk, sortBy, sortDir],
  );
  const coverageQuery = useStockCoverageQuery(filters);
  const stockoutQuery = usePotentialStockoutQuery();
  const skusQuery = useSkusQuery();
  const rows = coverageQuery.data?.items ?? [];
  const coverageMeta = coverageQuery.data?.meta;
  const categories = useMemo(
    () =>
      Array.from(
        new Set((skusQuery.data ?? []).map((item) => item.category).filter(Boolean) as string[]),
      ).sort((a, b) => a.localeCompare(b, "ru")),
    [skusQuery.data],
  );
  const filteredStockouts = useMemo(
    () => {
      const stockouts = stockoutQuery.data ?? [];
      return stockouts.filter((item) => {
        const categoryMatch = category ? item.categoryName === category : true;
        const searchMatch = search
          ? `${item.article} ${item.productName} ${item.clientName}`.toLowerCase().includes(search.toLowerCase())
          : true;
        return categoryMatch && searchMatch;
      });
    },
    [category, search, stockoutQuery.data],
  );

  const sortingState: SortingState = useMemo(
    () => [{ id: sortBy, desc: sortDir === "desc" }],
    [sortBy, sortDir],
  );

  const columns: ColumnDef<any>[] = [
    { id: "article", accessorKey: "sku.article", header: "Артикул", cell: (i) => <span className="text-num font-medium text-ink">{i.row.original.sku.article}</span> },
    { id: "product_name", accessorKey: "sku.name", header: "Товар", cell: (i) => i.row.original.sku.name },
    { id: "category_name", accessorKey: "sku.category", header: "Категория", cell: (i) => <span className="chip">{i.row.original.sku.category}</span> },
    { accessorKey: "warehouse", header: "Склад", cell: (i) => WAREHOUSE_LABEL[i.getValue() as string] ?? (i.getValue() as string) },
    { id: "free", accessorKey: "free", header: "Свободно", meta: { align: "right", mono: true }, cell: (i) => fmtInt(i.getValue() as number) },
    { accessorKey: "reservedLike", header: "Резерв-подобно", meta: { align: "right", mono: true }, cell: (i) => fmtInt(i.getValue() as number) },
    { id: "demand_per_month", accessorKey: "demandPerMonth", header: "Спрос/мес.", meta: { align: "right", mono: true }, cell: (i) => fmtInt(i.getValue() as number) },
    { id: "shortage_qty_total", accessorKey: "shortageQtyTotal", header: "Дефицит", meta: { align: "right", mono: true }, cell: (i) => {
      const value = i.getValue() as number;
      return <span className={value > 0 ? "text-danger font-medium" : "text-ink-muted"}>{value > 0 ? `−${fmtInt(value)}` : "0"}</span>;
    } },
    { id: "coverage_months", accessorKey: "coverageMonths", header: "Покрытие", meta: { align: "right", mono: true }, cell: (i) => {
      const v = i.getValue() as number | null;
      if (v == null) return <span className="text-ink-muted">—</span>;
      const tone = v < 1 ? "text-danger" : v < 2 ? "text-warning" : "text-ink";
      return <span className={tone}>{fmtMonths(v)}</span>;
    } },
    { id: "worst_status", accessorKey: "worstStatus", header: "Статус", cell: (i) => <StatusBadge value={i.getValue() as any} /> },
  ];

  return (
    <>
      <PageHeader
        eyebrow="Операции"
        title="Склад и покрытие"
        description="Свободный остаток, резерв-подобный объём и прогноз покрытия в месяцах по каталогу."
        actions={
          <Button
            variant="outline"
            size="sm"
            className="h-9 border-line-subtle bg-surface-panel"
            disabled={!canExport || exportMutation.isPending}
            onClick={async () => {
              try {
                const job = await exportMutation.mutateAsync({
                  format: "xlsx",
                  category: category || undefined,
                  risk,
                  search: search || undefined,
                  sortBy,
                  sortDir,
                });
                toast.success(job.canDownload ? "Экспорт покрытия сформирован" : "Экспорт покрытия поставлен в очередь");
              } catch {
                toast.error("Не удалось сформировать экспорт");
              }
            }}
          >
            <Download className="mr-1.5 h-3.5 w-3.5" />
            {exportMutation.isPending ? "Экспорт…" : "Экспорт"}
          </Button>
        }
      />
      {coverageQuery.error ? (
        <QueryErrorState
          error={coverageQuery.error}
          title="Сводка по складу пока недоступна"
          onRetry={() => void coverageQuery.refetch()}
        />
      ) : null}
      <section className="panel p-5">
        <div className="mb-3 text-[11px] uppercase tracking-wide text-ink-muted">Потенциальный stockout</div>
        <div className="grid grid-cols-1 gap-2 xl:grid-cols-3">
          {stockoutQuery.isLoading
            ? Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-[108px]" />)
            : filteredStockouts.slice(0, 6).map((item) => (
            <div key={`${item.clientId}-${item.skuId}`} className="rounded-md border border-line-subtle bg-surface-muted/30 p-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-medium text-ink">{item.productName}</div>
                  <div className="text-xs text-ink-muted">{item.article} · {item.clientName}</div>
                </div>
                <StatusBadge value={item.status as any} />
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                <div><div className="text-ink-muted">Дефицит</div><div className="text-num font-medium text-danger">{fmtInt(item.shortageQty)}</div></div>
                <div><div className="text-ink-muted">Покрытие</div><div className="text-num font-medium">{item.coverageMonths == null ? "—" : fmtMonths(item.coverageMonths)}</div></div>
              </div>
            </div>
          ))}
          {stockoutQuery.error ? (
            <div className="xl:col-span-3">
              <QueryErrorState
                error={stockoutQuery.error}
                title="Риск скорого stockout пока недоступен"
                onRetry={() => void stockoutQuery.refetch()}
              />
            </div>
          ) : null}
        </div>
      </section>
      <FilterChips
        value={risk}
        onChange={(value) => {
          const next = new URLSearchParams(searchParams);
          if (value === "all") next.delete("risk");
          else next.set("risk", value);
          setSearchParams(next);
        }}
        allLabel="Все"
        options={[{ value: "low_stock", label: "Низкий остаток" }, { value: "overstock", label: "Излишки" }]}
      />
      <DataTable
        data={rows}
        columns={columns}
        loading={coverageQuery.isLoading}
        searchPlaceholder="Артикул, товар или категория…"
        density="compact"
        manualFiltering
        manualSorting
        manualPagination
        searchValue={search}
        onSearchChange={(value) => {
          const next = new URLSearchParams(searchParams);
          if (value.trim()) next.set("query", value);
          else next.delete("query");
          next.delete("page");
          setSearchParams(next);
        }}
        sortingState={sortingState}
        onSortingChange={(nextSorting) => {
          const next = new URLSearchParams(searchParams);
          const head = nextSorting[0];
          if (!head) {
            next.delete("sort");
            next.delete("dir");
          } else {
            next.set("sort", head.id);
            next.set("dir", head.desc ? "desc" : "asc");
          }
          next.delete("page");
          setSearchParams(next);
        }}
        page={coverageMeta?.page ?? page}
        pageSize={coverageMeta?.pageSize ?? pageSize}
        totalRows={coverageMeta?.total ?? rows.length}
        onPageChange={(nextPage) => {
          const next = new URLSearchParams(searchParams);
          next.set("page", String(nextPage));
          setSearchParams(next);
        }}
        onPageSizeChange={(nextPageSize) => {
          const next = new URLSearchParams(searchParams);
          next.set("pageSize", String(nextPageSize));
          next.delete("page");
          setSearchParams(next);
        }}
        rightToolbar={
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={category}
              onChange={(event) => {
                const next = new URLSearchParams(searchParams);
                if (event.target.value) next.set("category", event.target.value);
                else next.delete("category");
                setSearchParams(next);
              }}
              className="h-8 rounded-md border border-line-subtle bg-surface-panel px-2 text-xs text-ink"
            >
              <option value="">Все категории</option>
              {categories.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>
        }
      />
    </>
  );
}
