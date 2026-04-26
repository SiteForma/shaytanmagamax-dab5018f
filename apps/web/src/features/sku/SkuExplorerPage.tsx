import { useSearchParams } from "react-router-dom";
import type { ColumnDef } from "@tanstack/react-table";
import { PageHeader } from "@/components/ui-ext/PageHeader";
import { DataTable } from "@/components/ui-ext/DataTable";
import { EmptyState } from "@/components/ui-ext/EmptyState";
import { QueryErrorState } from "@/components/ui-ext/QueryErrorState";
import { Skeleton } from "@/components/ui-ext/Skeleton";
import { useSkuDetailQuery, useSkusQuery } from "@/hooks/queries/use-sku";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { StatusBadge } from "@/components/ui-ext/StatusBadge";
import { fmtInt, fmtMonths } from "@/lib/formatters";
import { Boxes } from "lucide-react";

export default function SkuExplorerPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedSkuId = searchParams.get("sku");
  const skusQuery = useSkusQuery();
  const detailQuery = useSkuDetailQuery(selectedSkuId);
  const skus = skusQuery.data ?? [];
  const detail = detailQuery.data ?? null;

  function openSku(skuId: string) {
    setSearchParams({ sku: skuId });
  }

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
      {skusQuery.error ? (
        <QueryErrorState
          error={skusQuery.error}
          title="Каталог SKU пока недоступен"
          onRetry={() => void skusQuery.refetch()}
        />
      ) : null}
      <DataTable
        data={skus}
        columns={columns}
        loading={skusQuery.isLoading}
        searchKeys={["article", "name", "category", "brand"] as any}
        searchPlaceholder="Поиск по артикулу, наименованию, категории…"
        density="compact"
        initialPageSize={20}
        onRowClick={(row) => openSku(row.id)}
      />

      <Sheet open={Boolean(selectedSkuId)} onOpenChange={(open) => !open && setSearchParams({})}>
        <SheetContent className="w-[560px] border-l border-line-subtle bg-surface-elevated">
          {detailQuery.isLoading ? (
            <div className="mt-6 space-y-3">
              <Skeleton className="h-8 w-2/3" />
              <Skeleton className="h-24" />
              <Skeleton className="h-28" />
              <Skeleton className="h-40" />
            </div>
          ) : detailQuery.error ? (
            <QueryErrorState
              error={detailQuery.error}
              title="Карточка SKU пока недоступна"
              onRetry={() => void detailQuery.refetch()}
              className="mt-6"
            />
          ) : detail ? (
            <>
              <SheetHeader>
                <SheetTitle className="text-ink">{detail.sku.name}</SheetTitle>
                <SheetDescription className="text-xs text-ink-muted">
                  {detail.sku.article} · {detail.sku.category ?? "Без категории"}
                </SheetDescription>
              </SheetHeader>
              <div className="mt-6 space-y-5 text-sm">
                {detail.reserveSummary && (
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-md border border-line-subtle bg-surface-muted/30 p-3">
                      <div className="text-[11px] uppercase tracking-wide text-ink-muted">Общий дефицит</div>
                      <div className="mt-1 text-num text-lg font-semibold text-danger">{fmtInt(detail.reserveSummary.shortageQtyTotal)}</div>
                    </div>
                    <div className="rounded-md border border-line-subtle bg-surface-muted/30 p-3">
                      <div className="text-[11px] uppercase tracking-wide text-ink-muted">Худший статус</div>
                      <div className="mt-2"><StatusBadge value={detail.reserveSummary.worstStatus as any} /></div>
                    </div>
                  </div>
                )}

                {detail.stock && (
                  <div className="rounded-md border border-line-subtle bg-surface-muted/30 p-3">
                    <div className="mb-2 text-[11px] uppercase tracking-wide text-ink-muted">Текущий склад</div>
                    <div className="grid grid-cols-3 gap-3 text-xs">
                      <div><div className="text-ink-muted">Свободно</div><div className="text-num font-medium">{fmtInt(detail.stock.freeStock)}</div></div>
                      <div><div className="text-ink-muted">Резерв-подобно</div><div className="text-num font-medium">{fmtInt(detail.stock.reservedLike)}</div></div>
                      <div><div className="text-ink-muted">Склад</div><div className="font-medium text-ink">{detail.stock.warehouse}</div></div>
                    </div>
                  </div>
                )}

                <div>
                  <div className="mb-2 text-[11px] uppercase tracking-wide text-ink-muted">Распределение по клиентам DIY</div>
                  <div className="space-y-2">
                    {detail.clientSplit.slice(0, 6).map((item) => (
                      <div key={item.client.id} className="rounded-md border border-line-subtle bg-surface-muted/30 p-3">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <div className="text-sm font-medium text-ink">{item.client.name}</div>
                            <div className="text-xs text-ink-muted">доля {item.share.toFixed(1)}%</div>
                          </div>
                          <StatusBadge value={item.status as any} />
                        </div>
                        <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
                          <div><div className="text-ink-muted">Резерв</div><div className="text-num font-medium">{fmtInt(item.reservePosition)}</div></div>
                          <div><div className="text-ink-muted">Дефицит</div><div className="text-num font-medium">{fmtInt(item.shortageQty)}</div></div>
                          <div><div className="text-ink-muted">Покрытие</div><div className="text-num font-medium">{item.coverageMonths == null ? "—" : fmtMonths(item.coverageMonths)}</div></div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </>
          ) : (
            <EmptyState
              icon={Boxes}
              title="SKU не найден"
              description="Проверь выбранный идентификатор или открой позицию из текущего списка."
              className="mt-6"
            />
          )}
        </SheetContent>
      </Sheet>
    </>
  );
}
