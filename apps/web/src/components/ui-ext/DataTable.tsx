import { useState } from "react";
import {
  ColumnDef,
  ColumnFiltersState,
  PaginationState,
  SortingState,
  Updater,
  VisibilityState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { ArrowUpDown, ChevronDown, ChevronLeft, ChevronRight, Search, SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { TableSkeleton } from "./Skeleton";
import { EmptyState } from "./EmptyState";
import { Inbox } from "lucide-react";

export type Density = "compact" | "default" | "comfortable";

interface DataTableProps<T> {
  data: T[];
  columns: ColumnDef<any, any>[];
  loading?: boolean;
  searchKeys?: (keyof T)[];
  searchPlaceholder?: string;
  initialPageSize?: number;
  density?: Density;
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  manualFiltering?: boolean;
  manualSorting?: boolean;
  sortingState?: SortingState;
  onSortingChange?: (value: SortingState) => void;
  manualPagination?: boolean;
  page?: number;
  pageSize?: number;
  totalRows?: number;
  onPageChange?: (page: number) => void;
  onPageSizeChange?: (pageSize: number) => void;
  onRowClick?: (row: T) => void;
  emptyTitle?: string;
  emptyDescription?: string;
  rightToolbar?: React.ReactNode;
  className?: string;
}

const DENSITY_PADDING: Record<Density, string> = {
  compact: "py-1.5",
  default: "py-2.5",
  comfortable: "py-3.5",
};

export function DataTable<T>({
  data,
  columns,
  loading,
  searchKeys,
  searchPlaceholder = "Поиск…",
  initialPageSize = 10,
  density = "default",
  searchValue,
  onSearchChange,
  manualFiltering = false,
  manualSorting = false,
  sortingState,
  onSortingChange,
  manualPagination = false,
  page = 1,
  pageSize: controlledPageSize,
  totalRows,
  onPageChange,
  onPageSizeChange,
  onRowClick,
  emptyTitle = "Нет данных",
  emptyDescription,
  rightToolbar,
  className,
}: DataTableProps<T>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({});
  const [globalFilter, setGlobalFilter] = useState("");
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: initialPageSize,
  });
  const resolvedSorting = sortingState ?? sorting;
  const resolvedGlobalFilter = searchValue ?? globalFilter;
  const resolvedPageSize = controlledPageSize ?? pagination.pageSize;
  const resolvedPagination = manualPagination
    ? { pageIndex: Math.max(page - 1, 0), pageSize: resolvedPageSize }
    : { pageIndex: pagination.pageIndex, pageSize: resolvedPageSize };

  function applySortingChange(updater: Updater<SortingState>) {
    const next = typeof updater === "function" ? updater(resolvedSorting) : updater;
    if (onSortingChange) {
      onSortingChange(next);
      return;
    }
    if (!manualPagination) {
      setPagination((current) => ({ ...current, pageIndex: 0 }));
    }
    setSorting(next);
  }

  function applySearchChange(value: string) {
    if (manualPagination) {
      onPageChange?.(1);
    } else {
      setPagination((current) => ({ ...current, pageIndex: 0 }));
    }
    if (onSearchChange) {
      onSearchChange(value);
      return;
    }
    setGlobalFilter(value);
  }

  const table = useReactTable({
    data: data as any[],
    columns: columns as ColumnDef<any, any>[],
    state: {
      sorting: resolvedSorting,
      columnFilters,
      columnVisibility,
      globalFilter: resolvedGlobalFilter,
      pagination: resolvedPagination,
    },
    onSortingChange: applySortingChange,
    onPaginationChange: (updater) => {
      if (manualPagination) {
        return;
      }
      const next = typeof updater === "function" ? updater(resolvedPagination) : updater;
      setPagination(next);
    },
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    onGlobalFilterChange: applySearchChange,
    manualFiltering,
    manualSorting,
    manualPagination,
    pageCount:
      manualPagination && totalRows != null
        ? Math.max(Math.ceil(totalRows / resolvedPageSize), 1)
        : undefined,
    globalFilterFn: ((row: any, _columnId: string, filterValue: string) => {
      if (!filterValue) return true;
      const v = filterValue.toLowerCase();
      if (searchKeys && searchKeys.length) {
        return searchKeys.some((k) => String((row.original as any)[k] ?? "").toLowerCase().includes(v));
      }
      return Object.values(row.original as any).some((cell) =>
        String(cell ?? "").toLowerCase().includes(v),
      );
    }) as any,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: manualFiltering ? undefined : getFilteredRowModel(),
    getPaginationRowModel: manualPagination ? undefined : getPaginationRowModel(),
    initialState: { pagination: { pageSize: initialPageSize } },
  });

  const rows = table.getRowModel().rows;
  const totalCount = manualPagination ? totalRows ?? data.length : table.getFilteredRowModel().rows.length;
  const currentPage = manualPagination ? page : table.getState().pagination.pageIndex + 1;
  const canPreviousPage = manualPagination ? currentPage > 1 : table.getCanPreviousPage();
  const canNextPage = manualPagination
    ? currentPage * resolvedPageSize < totalCount
    : table.getCanNextPage();
  const rangeStart = totalCount === 0 ? 0 : (currentPage - 1) * resolvedPageSize + 1;
  const rangeEnd = totalCount === 0 ? 0 : Math.min(rangeStart + rows.length - 1, totalCount);

  return (
    <div className={cn("panel overflow-hidden", className)}>
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2 border-b border-line-subtle bg-surface-elevated/40 px-3 py-2.5">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-muted" />
          <Input
            value={resolvedGlobalFilter}
            onChange={(e) => applySearchChange(e.target.value)}
            placeholder={searchPlaceholder}
            className="h-8 border-line-subtle bg-surface-panel pl-8 text-sm placeholder:text-ink-muted"
          />
        </div>

        {rightToolbar}

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className="h-8 gap-1.5 border-line-subtle bg-surface-panel">
              <SlidersHorizontal className="h-3.5 w-3.5" />
              Колонки
              <ChevronDown className="h-3 w-3 opacity-60" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-52">
            <DropdownMenuLabel className="text-xs">Видимые колонки</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {table
              .getAllLeafColumns()
              .filter((c) => c.getCanHide())
              .map((c) => (
                <DropdownMenuCheckboxItem
                  key={c.id}
                  checked={c.getIsVisible()}
                  onCheckedChange={(v) => c.toggleVisibility(!!v)}
                  className="capitalize"
                >
                  {String(c.columnDef.header ?? c.id)}
                </DropdownMenuCheckboxItem>
              ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Table */}
      <div className="relative overflow-auto">
        {loading ? (
          <div className="p-4">
            <TableSkeleton cols={columns.length} />
          </div>
        ) : rows.length === 0 ? (
          <div className="p-6">
            <EmptyState icon={Inbox} title={emptyTitle} description={emptyDescription} />
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="sticky top-0 z-10 bg-surface-elevated/95 backdrop-blur supports-[backdrop-filter]:bg-surface-elevated/80">
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id} className="border-b border-line-subtle">
                  {hg.headers.map((h) => {
                    const meta = (h.column.columnDef.meta ?? {}) as { align?: "left" | "right" | "center" };
                    const align = meta.align ?? "left";
                    return (
                      <th
                        key={h.id}
                        className={cn(
                          "px-3 py-2.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-muted",
                          align === "right" && "text-right",
                          align === "center" && "text-center",
                          align === "left" && "text-left",
                        )}
                        style={{ width: h.getSize() === 150 ? undefined : h.getSize() }}
                      >
                        {h.isPlaceholder ? null : h.column.getCanSort() ? (
                          <button
                            onClick={h.column.getToggleSortingHandler()}
                            className="inline-flex items-center gap-1 hover:text-ink"
                          >
                            {flexRender(h.column.columnDef.header, h.getContext())}
                            <ArrowUpDown className="h-3 w-3 opacity-50" />
                          </button>
                        ) : (
                          flexRender(h.column.columnDef.header, h.getContext())
                        )}
                      </th>
                    );
                  })}
                </tr>
              ))}
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.id}
                  onClick={() => onRowClick?.(row.original as T)}
                  className={cn(
                    "border-b border-line-subtle/60 transition-colors",
                    "hover:bg-surface-hover/60",
                    onRowClick && "cursor-pointer",
                  )}
                >
                  {row.getVisibleCells().map((cell) => {
                    const meta = (cell.column.columnDef.meta ?? {}) as { align?: "left" | "right" | "center"; mono?: boolean };
                    return (
                      <td
                        key={cell.id}
                        className={cn(
                          "px-3 text-ink",
                          DENSITY_PADDING[density],
                          meta.align === "right" && "text-right tabular-nums",
                          meta.align === "center" && "text-center",
                          meta.mono && "tabular-nums",
                        )}
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Footer / pagination */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line-subtle bg-surface-elevated/40 px-3 py-2 text-xs text-ink-muted">
        <div>
          {rows.length > 0
            ? `${rangeStart}–${rangeEnd} из ${totalCount}`
            : "0 результатов"}
        </div>
        <div className="flex items-center gap-2">
          <select
            value={resolvedPageSize}
            onChange={(e) => {
              const n = Number(e.target.value);
              if (onPageSizeChange) {
                onPageSizeChange(n);
                onPageChange?.(1);
                return;
              }
              setPagination({ pageIndex: 0, pageSize: n });
            }}
            className="h-7 rounded-md border border-line-subtle bg-surface-panel px-2 text-xs text-ink focus-ring"
          >
            {[10, 20, 50, 100].map((s) => (
              <option key={s} value={s}>{s} / стр.</option>
            ))}
          </select>
          <Button
            variant="outline"
            size="icon"
            className="h-7 w-7 border-line-subtle bg-surface-panel"
            onClick={() => {
              if (manualPagination) {
                onPageChange?.(Math.max(currentPage - 1, 1));
                return;
              }
              table.previousPage();
            }}
            disabled={!canPreviousPage}
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            className="h-7 w-7 border-line-subtle bg-surface-panel"
            onClick={() => {
              if (manualPagination) {
                onPageChange?.(currentPage + 1);
                return;
              }
              table.nextPage();
            }}
            disabled={!canNextPage}
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}
