import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, MoreHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type PageToken = number | "ellipsis-left" | "ellipsis-right";

interface PaginationBarProps {
  page: number;
  pageSize: number;
  totalRows: number;
  rangeStart: number;
  rangeEnd: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  pageSizeOptions?: number[];
  itemLabel?: string;
  className?: string;
}

const numberFormatter = new Intl.NumberFormat("ru-RU");

function clampPage(page: number, pageCount: number): number {
  return Math.min(Math.max(page, 1), Math.max(pageCount, 1));
}

function buildPageTokens(currentPage: number, pageCount: number): PageToken[] {
  if (pageCount <= 7) {
    return Array.from({ length: pageCount }, (_, index) => index + 1);
  }

  const pages = new Set<number>([1, pageCount]);
  for (let page = currentPage - 1; page <= currentPage + 1; page += 1) {
    if (page > 1 && page < pageCount) {
      pages.add(page);
    }
  }
  if (currentPage <= 3) {
    pages.add(2);
    pages.add(3);
    pages.add(4);
  }
  if (currentPage >= pageCount - 2) {
    pages.add(pageCount - 3);
    pages.add(pageCount - 2);
    pages.add(pageCount - 1);
  }

  const sortedPages = Array.from(pages).sort((a, b) => a - b);
  const tokens: PageToken[] = [];
  sortedPages.forEach((page, index) => {
    const previous = sortedPages[index - 1];
    if (previous && page - previous > 1) {
      tokens.push(previous === 1 ? "ellipsis-left" : "ellipsis-right");
    }
    tokens.push(page);
  });
  return tokens;
}

export function PaginationBar({
  page,
  pageSize,
  totalRows,
  rangeStart,
  rangeEnd,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 20, 50, 100],
  itemLabel = "строк",
  className,
}: PaginationBarProps) {
  const pageCount = Math.max(Math.ceil(totalRows / pageSize), 1);
  const currentPage = clampPage(page, pageCount);
  const [quickPage, setQuickPage] = useState(String(currentPage));
  const pageTokens = useMemo(
    () => buildPageTokens(currentPage, pageCount),
    [currentPage, pageCount],
  );

  useEffect(() => {
    setQuickPage(String(currentPage));
  }, [currentPage]);

  function goToPage(nextPage: number) {
    const normalized = clampPage(nextPage, pageCount);
    if (normalized !== currentPage) {
      onPageChange(normalized);
    }
  }

  function submitQuickPage() {
    const parsed = Number(quickPage);
    if (Number.isFinite(parsed)) {
      goToPage(parsed);
    } else {
      setQuickPage(String(currentPage));
    }
  }

  const hasRows = totalRows > 0;
  const canPrevious = currentPage > 1;
  const canNext = currentPage < pageCount;

  return (
    <div
      className={cn(
        "flex flex-col gap-3 border-t border-line-subtle bg-surface-elevated/50 px-3 py-3 text-xs text-ink-muted",
        "supports-[backdrop-filter]:bg-surface-elevated/35",
        className,
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-[180px] items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-brand shadow-[0_0_18px_rgba(255,91,31,0.45)]" />
          <span>
            {hasRows
              ? `${numberFormatter.format(rangeStart)}–${numberFormatter.format(rangeEnd)} из ${numberFormatter.format(totalRows)}`
              : `0 ${itemLabel}`}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label className="hidden items-center gap-2 sm:flex">
            <span>На странице</span>
            <select
              value={pageSize}
              onChange={(event) => onPageSizeChange(Number(event.target.value))}
              className="h-8 rounded-full border border-line-subtle bg-surface-panel px-3 text-xs text-ink outline-none transition-colors hover:border-line-strong focus-ring"
              aria-label="Количество строк на странице"
            >
              {pageSizeOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>

          <div className="flex items-center rounded-full border border-line-subtle bg-surface-panel/80 p-1 shadow-sm">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7 rounded-full text-ink-muted hover:bg-surface-hover hover:text-ink"
              onClick={() => goToPage(1)}
              disabled={!canPrevious}
              aria-label="Первая страница"
            >
              <ChevronsLeft className="h-3.5 w-3.5" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7 rounded-full text-ink-muted hover:bg-surface-hover hover:text-ink"
              onClick={() => goToPage(currentPage - 1)}
              disabled={!canPrevious}
              aria-label="Предыдущая страница"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </Button>

            <div className="hidden items-center gap-1 px-1 md:flex">
              {pageTokens.map((token) =>
                typeof token === "number" ? (
                  <Button
                    key={token}
                    type="button"
                    variant="ghost"
                    size="icon"
                    className={cn(
                      "h-7 min-w-7 rounded-full px-2 text-xs tabular-nums",
                      token === currentPage
                        ? "bg-brand text-brand-foreground shadow-[0_0_22px_rgba(255,91,31,0.22)] hover:bg-brand"
                        : "text-ink-muted hover:bg-surface-hover hover:text-ink",
                    )}
                    onClick={() => goToPage(token)}
                    aria-label={`Страница ${token}`}
                    aria-current={token === currentPage ? "page" : undefined}
                  >
                    {token}
                  </Button>
                ) : (
                  <span key={token} className="flex h-7 w-7 items-center justify-center text-ink-faint">
                    <MoreHorizontal className="h-3.5 w-3.5" />
                  </span>
                ),
              )}
            </div>

            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7 rounded-full text-ink-muted hover:bg-surface-hover hover:text-ink"
              onClick={() => goToPage(currentPage + 1)}
              disabled={!canNext}
              aria-label="Следующая страница"
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7 rounded-full text-ink-muted hover:bg-surface-hover hover:text-ink"
              onClick={() => goToPage(pageCount)}
              disabled={!canNext}
              aria-label="Последняя страница"
            >
              <ChevronsRight className="h-3.5 w-3.5" />
            </Button>
          </div>

          <label className="hidden items-center gap-2 lg:flex">
            <span>К странице</span>
            <input
              value={quickPage}
              onChange={(event) => setQuickPage(event.target.value)}
              onBlur={submitQuickPage}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  submitQuickPage();
                  event.currentTarget.blur();
                }
              }}
              className="h-8 w-14 rounded-full border border-line-subtle bg-surface-panel px-2 text-center text-xs tabular-nums text-ink outline-none transition-colors hover:border-line-strong focus-ring"
              inputMode="numeric"
              aria-label="Перейти к странице"
            />
            <span>из {numberFormatter.format(pageCount)}</span>
          </label>

          <span className="rounded-full border border-line-subtle bg-surface-panel px-3 py-1.5 text-xs tabular-nums text-ink-muted md:hidden">
            {currentPage} / {pageCount}
          </span>
        </div>
      </div>
    </div>
  );
}
