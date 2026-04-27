import { useMemo, type CSSProperties, type MouseEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { ColumnDef } from "@tanstack/react-table";
import type { Sku } from "@/types";
import { PageHeader } from "@/components/ui-ext/PageHeader";
import { DataTable } from "@/components/ui-ext/DataTable";
import { EmptyState } from "@/components/ui-ext/EmptyState";
import { QueryErrorState } from "@/components/ui-ext/QueryErrorState";
import { Skeleton } from "@/components/ui-ext/Skeleton";
import { useSkuDetailQuery, useSkusQuery } from "@/hooks/queries/use-sku";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui-ext/StatusBadge";
import { fmtDate, fmtInt, fmtMonths, fmtRub } from "@/lib/formatters";
import {
  ArrowUpRight,
  Barcode,
  Boxes,
  CircleDollarSign,
  Layers3,
  PackageCheck,
  ShieldCheck,
  Sparkles,
  Tag,
  Truck,
  Warehouse,
} from "lucide-react";

const UNIT_LABELS: Record<string, string> = {
  pcs: "шт.",
  set: "комп.",
  m: "м",
};

const FILTER_SELECT_CLASS =
  "h-8 rounded-xl border border-line-subtle bg-surface-panel px-3 text-xs font-medium text-ink outline-none transition hover:border-brand/35 focus:border-brand/60";

function activeFilterStyle(active: boolean): CSSProperties | undefined {
  if (!active) return undefined;
  return {
    backgroundColor: "rgba(255, 106, 31, 0.08)",
    borderColor: "rgba(255, 106, 31, 0.78)",
    boxShadow: "0 0 0 1px rgba(255, 106, 31, 0.20), 0 0 18px rgba(255, 106, 31, 0.10)",
  };
}

function displayBrand(brand?: string | null) {
  if (!brand || brand.trim().toLowerCase() === "magamax") {
    return "Не указан";
  }
  return brand;
}

function categoryPath(sku: Sku) {
  return sku.categoryPath ?? sku.category ?? null;
}

function hasMeaningfulCategory(sku: Sku) {
  const value = categoryPath(sku);
  return Boolean(value && value.trim() && !/без категории/i.test(value));
}

function primaryCategory(sku: Sku) {
  const value = categoryPath(sku);
  if (!value) return "Без категории";
  const parts = value
    .split("/")
    .map((part) => part.trim())
    .filter(Boolean);
  if (parts.length >= 3) return parts[2];
  if (parts.length >= 1) return parts[parts.length - 1];
  return value;
}

function normalizeParam(value: string | null, fallback = "all") {
  return value && value.trim() ? value : fallback;
}

function filterSkus(skus: Sku[], brand: string, category: string) {
  return skus.filter((sku) => {
    if (brand !== "all" && displayBrand(sku.brand) !== brand) return false;
    if (category !== "all" && primaryCategory(sku) !== category) return false;
    return true;
  });
}

export default function SkuExplorerPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedSkuId = searchParams.get("sku");
  const selectedBrand = normalizeParam(searchParams.get("brand"));
  const selectedCategory = normalizeParam(searchParams.get("category"));
  const skusQuery = useSkusQuery();
  const detailQuery = useSkuDetailQuery(selectedSkuId);
  const skus = useMemo(() => skusQuery.data ?? [], [skusQuery.data]);
  const detail = detailQuery.data ?? null;
  const detailCategory = detail?.sku.categoryPath ?? detail?.sku.category ?? "Категория не подтянута";

  const filteredSkus = useMemo(
    () => filterSkus(skus, selectedBrand, selectedCategory),
    [selectedBrand, selectedCategory, skus],
  );
  const categories = useMemo(
    () => {
      const meaningful = Array.from(new Set(skus.filter(hasMeaningfulCategory).map(primaryCategory))).sort((a, b) =>
        a.localeCompare(b, "ru"),
      );
      return skus.some((sku) => !hasMeaningfulCategory(sku)) ? [...meaningful, "Без категории"] : meaningful;
    },
    [skus],
  );
  const brands = useMemo(
    () =>
      Array.from(new Set(skus.map((sku) => displayBrand(sku.brand)).filter((brand) => brand !== "Не указан"))).sort(
        (a, b) => a.localeCompare(b, "ru"),
      ),
    [skus],
  );

  function setParam(key: string, value: string | null) {
    const next = new URLSearchParams(searchParams);
    if (!value || value === "all") {
      next.delete(key);
    } else {
      next.set(key, value);
    }
    setSearchParams(next);
  }

  function resetFilters() {
    const next = new URLSearchParams(searchParams);
    next.delete("brand");
    next.delete("category");
    setSearchParams(next);
  }

  function openSku(skuId: string) {
    const next = new URLSearchParams(searchParams);
    next.set("sku", skuId);
    setSearchParams(next);
  }

  function closeSku() {
    const next = new URLSearchParams(searchParams);
    next.delete("sku");
    setSearchParams(next);
  }

  const hasActiveFilters = selectedBrand !== "all" || selectedCategory !== "all";

  const tableToolbar = (
    <div className="flex flex-wrap items-center gap-2">
      <select
        aria-label="Фильтр по категории"
        value={selectedCategory}
        onChange={(event) => setParam("category", event.target.value)}
        className={`${FILTER_SELECT_CLASS} min-w-[164px] max-w-[220px]`}
        style={activeFilterStyle(selectedCategory !== "all")}
        title={selectedCategory !== "all" ? `Фильтр активен: ${selectedCategory}` : "Фильтр по категории"}
      >
        <option value="all">Все категории</option>
        {categories.map((category) => (
          <option key={category} value={category}>
            {category}
          </option>
        ))}
      </select>
      <select
        aria-label="Фильтр по бренду"
        value={selectedBrand}
        onChange={(event) => setParam("brand", event.target.value)}
        className={`${FILTER_SELECT_CLASS} min-w-[136px] max-w-[190px]`}
        style={activeFilterStyle(selectedBrand !== "all")}
        title={selectedBrand !== "all" ? `Фильтр активен: ${selectedBrand}` : "Фильтр по бренду"}
      >
        <option value="all">Все бренды</option>
        {brands.map((brand) => (
          <option key={brand} value={brand}>
            {brand}
          </option>
        ))}
      </select>
      {hasActiveFilters ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8 rounded-xl border-line-subtle bg-surface-panel px-3 text-xs"
          onClick={resetFilters}
        >
          Сбросить
        </Button>
      ) : null}
    </div>
  );

  const columns: ColumnDef<Sku>[] = [
    {
      accessorKey: "article",
      header: "Артикул",
      meta: { minWidth: 220, width: "16rem" },
      cell: ({ row }) => (
        <div className="min-w-[190px]">
          <div className="text-num font-semibold text-ink">{row.original.article}</div>
          <div className="mt-1 text-[11px] text-ink-muted">
            {displayBrand(row.original.brand)} · {UNIT_LABELS[row.original.unit] ?? row.original.unit}
          </div>
        </div>
      ),
    },
    {
      accessorKey: "name",
      header: "Товар",
      meta: { minWidth: 380, width: "34%" },
      cell: ({ row }) => (
        <div className="min-w-[300px]">
          <div className="font-medium text-ink">{row.original.name}</div>
          <div className="mt-1 line-clamp-1 text-xs text-ink-muted">{categoryPath(row.original) ?? "Категория не подтянута"}</div>
        </div>
      ),
    },
    {
      accessorKey: "category",
      header: "Категория",
      meta: { minWidth: 220, width: "16rem" },
      cell: ({ row }) => {
        const value = primaryCategory(row.original);
        const applyCategoryFilter = (event: MouseEvent<HTMLButtonElement>) => {
          event.stopPropagation();
          setParam("category", value);
        };

        return hasMeaningfulCategory(row.original) ? (
          <button
            type="button"
            title={`Фильтровать по категории: ${value}`}
            onClick={applyCategoryFilter}
            className="chip max-w-[220px] truncate transition hover:border-brand/45 hover:bg-brand/10 hover:text-brand focus-ring"
          >
            {value}
          </button>
        ) : (
          <button
            type="button"
            title="Показать товары без категории"
            onClick={applyCategoryFilter}
            className="rounded-full border border-warning/25 bg-warning/10 px-2 py-0.5 text-[11px] text-warning transition hover:border-warning/45 hover:bg-warning/15 focus-ring"
          >
            Нет категории
          </button>
        );
      },
    },
    {
      accessorKey: "costRub",
      header: "Себестоимость",
      meta: { align: "right", minWidth: 140, width: "10rem", nowrap: true },
      cell: (i) => {
        const value = i.getValue() as number | null | undefined;
        return value == null ? (
          <span className="text-ink-muted">—</span>
        ) : (
          <span className="text-num font-semibold text-ink">{fmtRub(value)}</span>
        );
      },
    },
    {
      accessorKey: "brand",
      header: "Бренд",
      meta: { minWidth: 130, width: "9rem" },
      cell: (i) => <span className="text-ink-secondary">{displayBrand(i.getValue() as string | null | undefined)}</span>,
    },
    {
      accessorKey: "active",
      header: "Статус",
      meta: { minWidth: 110, width: "8rem", nowrap: true },
      cell: (i) =>
        i.getValue() ? (
          <span className="text-success text-xs font-medium">Активен</span>
        ) : (
          <span className="text-ink-muted text-xs">Не активен</span>
        ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Каталог SKU"
        description="Сквозной мастер-каталог артикулов: категория, бренд, себестоимость, склад, поставки и резерв в одной рабочей карточке."
      />

      {skusQuery.error ? (
        <QueryErrorState
          error={skusQuery.error}
          title="Каталог SKU пока недоступен"
          onRetry={() => void skusQuery.refetch()}
        />
      ) : null}

      <DataTable
        data={filteredSkus}
        columns={columns}
        loading={skusQuery.isLoading}
        searchKeys={["article", "name", "category", "categoryPath", "brand"] as any}
        searchPlaceholder="Поиск по артикулу, товару, категории, бренду…"
        rightToolbar={tableToolbar}
        density="compact"
        initialPageSize={20}
        emptyTitle="SKU не найдены"
        emptyDescription="Измени фильтры или поисковый запрос. Каталог поддерживает срезы по бренду, категории и себестоимости."
        onRowClick={(row) => openSku(row.id)}
      />

      <Sheet open={Boolean(selectedSkuId)} onOpenChange={(open) => !open && closeSku()}>
        <SheetContent className="w-[720px] max-w-[94vw] overflow-y-auto border-l border-line-subtle bg-surface-elevated sm:max-w-[720px]">
          {detailQuery.isLoading ? (
            <div className="mt-6 space-y-3">
              <Skeleton className="h-8 w-2/3" />
              <Skeleton className="h-28" />
              <Skeleton className="h-28" />
              <Skeleton className="h-44" />
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
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-brand/30 bg-brand/10 px-2.5 py-1 text-[11px] font-semibold text-brand">
                      <Barcode className="h-3.5 w-3.5" />
                      {detail.sku.article}
                    </div>
                    <SheetTitle className="text-ink">{detail.sku.name}</SheetTitle>
                    <SheetDescription className="mt-2 text-xs text-ink-muted">
                      {detail.sku.article} · {detailCategory}
                    </SheetDescription>
                  </div>
                  <StatusBadge value={detail.sku.active ? "healthy" : "inactive"} />
                </div>
              </SheetHeader>

              <div className="mt-6 space-y-5 text-sm">
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-2xl border border-line-subtle bg-surface-muted/30 p-3">
                    <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-ink-muted">
                      <Tag className="h-3.5 w-3.5" />
                      Бренд
                    </div>
                    <div className="mt-2 font-semibold text-ink">{displayBrand(detail.sku.brand)}</div>
                  </div>
                  <div className="rounded-2xl border border-line-subtle bg-surface-muted/30 p-3">
                    <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-ink-muted">
                      <Layers3 className="h-3.5 w-3.5" />
                      Категория
                    </div>
                    <div className="mt-2 line-clamp-2 font-semibold text-ink">{primaryCategory(detail.sku)}</div>
                  </div>
                  <div className="rounded-2xl border border-line-subtle bg-surface-muted/30 p-3">
                    <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-ink-muted">
                      <CircleDollarSign className="h-3.5 w-3.5" />
                      Себестоимость
                    </div>
                    <div className="mt-2 text-num font-semibold text-ink">
                      {detail.cost?.costRub != null ? fmtRub(detail.cost.costRub) : "—"}
                    </div>
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-3">
                  <Button asChild variant="outline" className="justify-between rounded-2xl border-line-subtle bg-surface-panel">
                    <Link to={`/stock?query=${encodeURIComponent(detail.sku.article)}`}>
                      Склад и покрытие
                      <ArrowUpRight className="h-4 w-4" />
                    </Link>
                  </Button>
                  <Button asChild variant="outline" className="justify-between rounded-2xl border-line-subtle bg-surface-panel">
                    <Link to={`/reserve?skus=${encodeURIComponent(detail.sku.id)}`}>
                      Резерв по SKU
                      <ArrowUpRight className="h-4 w-4" />
                    </Link>
                  </Button>
                  <Button asChild variant="outline" className="justify-between rounded-2xl border-line-subtle bg-surface-panel">
                    <Link to={`/ai?context=sku:${encodeURIComponent(detail.sku.id)}`}>
                      Спросить MAGAMAX AI
                      <Sparkles className="h-4 w-4" />
                    </Link>
                  </Button>
                </div>

                {detail.reserveSummary ? (
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-2xl border border-line-subtle bg-surface-muted/30 p-4">
                      <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-ink-muted">
                        <ShieldCheck className="h-3.5 w-3.5" />
                        Общий дефицит
                      </div>
                      <div className="mt-2 text-num text-xl font-semibold text-danger">{fmtInt(detail.reserveSummary.shortageQtyTotal)}</div>
                      <div className="mt-1 text-xs text-ink-muted">
                        Клиентов затронуто: {fmtInt(detail.reserveSummary.affectedClientsCount)}
                      </div>
                    </div>
                    <div className="rounded-2xl border border-line-subtle bg-surface-muted/30 p-4">
                      <div className="text-[11px] uppercase tracking-wide text-ink-muted">Худший статус</div>
                      <div className="mt-3">
                        <StatusBadge value={detail.reserveSummary.worstStatus as any} />
                      </div>
                      <div className="mt-2 text-xs text-ink-muted">
                        Среднее покрытие:{" "}
                        {detail.reserveSummary.avgCoverageMonths == null ? "—" : fmtMonths(detail.reserveSummary.avgCoverageMonths)}
                      </div>
                    </div>
                  </div>
                ) : null}

                {detail.stock ? (
                  <div className="rounded-2xl border border-line-subtle bg-surface-muted/30 p-4">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                        <Warehouse className="h-4 w-4" />
                        Текущий склад
                      </div>
                      <span className="text-xs text-ink-muted">{fmtDate(detail.stock.updatedAt)}</span>
                    </div>
                    <div className="grid grid-cols-3 gap-3 text-xs">
                      <div>
                        <div className="text-ink-muted">Свободный остаток</div>
                        <div className="mt-1 text-num text-lg font-semibold text-ink">{fmtInt(detail.stock.freeStock)}</div>
                      </div>
                      <div>
                        <div className="text-ink-muted">Обособка / сети DIY</div>
                        <div className="mt-1 text-num text-lg font-semibold text-ink">{fmtInt(detail.stock.reservedLike)}</div>
                      </div>
                      <div>
                        <div className="text-ink-muted">Склад</div>
                        <div className="mt-1 font-semibold text-ink">{detail.stock.warehouse}</div>
                      </div>
                    </div>
                  </div>
                ) : null}

                {detail.cost ? (
                  <div className="rounded-2xl border border-line-subtle bg-surface-muted/30 p-4">
                    <div className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                      <PackageCheck className="h-4 w-4" />
                      Себестоимость из справочника
                    </div>
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div>
                        <div className="text-ink-muted">Артикул</div>
                        <div className="text-num font-semibold text-ink">{detail.cost.article}</div>
                      </div>
                      <div>
                        <div className="text-ink-muted">Себестоимость</div>
                        <div className="text-num font-semibold text-ink">{fmtRub(detail.cost.costRub)}</div>
                      </div>
                      <div className="col-span-2">
                        <div className="text-ink-muted">Наименование из файла</div>
                        <div className="font-medium text-ink">{detail.cost.productName}</div>
                      </div>
                    </div>
                  </div>
                ) : null}

                {detail.inbound.length > 0 ? (
                  <div className="rounded-2xl border border-line-subtle bg-surface-muted/30 p-4">
                    <div className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                      <Truck className="h-4 w-4" />
                      Ближайшие поставки
                    </div>
                    <div className="space-y-2">
                      {detail.inbound.slice(0, 4).map((item) => (
                        <div key={item.id} className="flex items-center justify-between gap-3 rounded-xl border border-line-subtle bg-surface-panel/70 px-3 py-2">
                          <div>
                            <div className="text-xs text-ink-muted">{fmtDate(item.eta)}</div>
                            <div className="text-num font-semibold text-ink">{fmtInt(item.qty)} шт.</div>
                          </div>
                          <StatusBadge value={item.status as any} />
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                <div>
                  <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                    Распределение по клиентам DIY
                  </div>
                  {detail.clientSplit.length > 0 ? (
                    <div className="space-y-2">
                      {detail.clientSplit.slice(0, 6).map((item) => (
                        <div key={item.client.id} className="rounded-2xl border border-line-subtle bg-surface-muted/30 p-3">
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <div className="text-sm font-semibold text-ink">{item.client.name}</div>
                              <div className="text-xs text-ink-muted">доля {item.share.toFixed(1)}%</div>
                            </div>
                            <StatusBadge value={item.status as any} />
                          </div>
                          <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                            <div>
                              <div className="text-ink-muted">Резерв</div>
                              <div className="text-num font-semibold">{fmtInt(item.reservePosition)}</div>
                            </div>
                            <div>
                              <div className="text-ink-muted">Дефицит</div>
                              <div className="text-num font-semibold">{fmtInt(item.shortageQty)}</div>
                            </div>
                            <div>
                              <div className="text-ink-muted">Покрытие</div>
                              <div className="text-num font-semibold">
                                {item.coverageMonths == null ? "—" : fmtMonths(item.coverageMonths)}
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="rounded-2xl border border-line-subtle bg-surface-muted/30 p-4 text-sm text-ink-muted">
                      По этому SKU пока нет клиентского разреза резерва.
                    </div>
                  )}
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
