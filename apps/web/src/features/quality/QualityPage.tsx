import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { ColumnDef, SortingState } from "@tanstack/react-table";
import { PageHeader } from "@/components/ui-ext/PageHeader";
import { DataTable } from "@/components/ui-ext/DataTable";
import { StatusBadge } from "@/components/ui-ext/StatusBadge";
import { FilterChips } from "@/components/ui-ext/FilterChips";
import { QueryErrorState } from "@/components/ui-ext/QueryErrorState";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useQualityIssuesQuery } from "@/hooks/queries/use-quality";
import { useQualityExportMutation } from "@/hooks/mutations/use-exports";
import { useHasCapability } from "@/hooks/queries/use-auth";
import type { QualityIssue } from "@/types";
import { fmtRelative } from "@/lib/formatters";
import { translateUploadIssueMessage, uploadIssueCodeLabel } from "@/lib/upload-labels";
import { Download } from "lucide-react";
import { toast } from "sonner";

export default function QualityPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedIssue, setSelectedIssue] = useState<QualityIssue | null>(null);
  const sev = searchParams.get("severity") ?? "all";
  const type = searchParams.get("type") ?? "all";
  const search = searchParams.get("query") ?? "";
  const page = Number(searchParams.get("page") ?? "1");
  const pageSize = Number(searchParams.get("pageSize") ?? "20");
  const sortBy = searchParams.get("sort") ?? "detected_at";
  const sortDir = (searchParams.get("dir") ?? "desc") as "asc" | "desc";
  const filters = useMemo(
    () => ({
      severity: sev === "all" ? undefined : (sev as any),
      type: type === "all" ? undefined : (type as any),
      search: search || undefined,
      page,
      pageSize,
      sortBy: sortBy as any,
      sortDir,
    }),
    [page, pageSize, search, sev, sortBy, sortDir, type],
  );
  const qualityQuery = useQualityIssuesQuery(filters);
  const exportMutation = useQualityExportMutation();
  const canExport = useHasCapability("exports:generate");
  const rows = qualityQuery.data?.items ?? [];
  const qualityMeta = qualityQuery.data?.meta;
  const sortingState: SortingState = useMemo(
    () => [{ id: sortBy, desc: sortDir === "desc" }],
    [sortBy, sortDir],
  );

  const columns: ColumnDef<any>[] = [
    { id: "type", accessorKey: "type", header: "Тип", cell: (i) => <span className="chip">{uploadIssueCodeLabel(i.getValue() as QualityIssue["type"])}</span> },
    { id: "entity", accessorKey: "entity", header: "Сущность", cell: (i) => <span className="text-num font-medium text-ink">{i.getValue() as string}</span> },
    { accessorKey: "description", header: "Описание", enableSorting: false, cell: (i) => translateDescription(i.getValue() as string) },
    { id: "source", accessorKey: "source", header: "Источник", cell: (i) => <span className="text-xs text-ink-muted">{i.getValue() as string}</span> },
    { id: "detected_at", accessorKey: "detectedAt", header: "Обнаружено", cell: (i) => <span className="text-xs text-ink-muted">{fmtRelative(i.getValue() as string)}</span> },
    { id: "severity", accessorKey: "severity", header: "Важность", cell: (i) => <StatusBadge value={i.getValue() as any} /> },
  ];

  return (
    <>
      <PageHeader
        eyebrow="Доверие"
        title="Качество данных"
        description="Дубликаты, отсутствующие ссылки, отрицательные остатки, подозрительные всплески и расхождения категорий по всем источникам."
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
                  severity: sev === "all" ? undefined : sev,
                  type: type === "all" ? undefined : type,
                  search: search || undefined,
                  sortBy,
                  sortDir,
                });
                toast.success(job.canDownload ? "Экспорт проблем качества сформирован" : "Экспорт проблем качества поставлен в очередь");
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
      {qualityQuery.error ? (
        <QueryErrorState
          error={qualityQuery.error}
          title="Список quality issues пока недоступен"
          onRetry={() => void qualityQuery.refetch()}
        />
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <FilterChips value={sev} onChange={(value) => {
          const next = new URLSearchParams(searchParams);
          if (value === "all") next.delete("severity");
          else next.set("severity", value);
          setSearchParams(next);
        }} allLabel="Все" options={[
          { value: "info", label: "Инфо" },
          { value: "warning", label: "Предупреждение" },
          { value: "error", label: "Ошибка" },
          { value: "critical", label: "Критичная" },
        ]} />
        <select
          value={type}
          onChange={(event) => {
            const next = new URLSearchParams(searchParams);
            if (event.target.value === "all") next.delete("type");
            else next.set("type", event.target.value);
            setSearchParams(next);
          }}
          className="h-8 rounded-md border border-line-subtle bg-surface-panel px-2 text-xs text-ink"
        >
          <option value="all">Все типы</option>
          <option value="duplicate">Дубликаты</option>
          <option value="missing_sku">Нет SKU</option>
          <option value="unmatched_client">Нет клиента</option>
          <option value="negative_stock">Отрицательный остаток</option>
          <option value="suspicious_spike">Подозрительный всплеск</option>
          <option value="missing_month">Пропущенный месяц</option>
          <option value="category_mismatch">Расхождение категории</option>
          <option value="mapping_required">Нужно сопоставление</option>
        </select>
      </div>
      <DataTable
        data={rows}
        columns={columns}
        loading={qualityQuery.isLoading}
        searchPlaceholder="Поиск по сущности, описанию и источнику…"
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
        page={qualityMeta?.page ?? page}
        pageSize={qualityMeta?.pageSize ?? pageSize}
        totalRows={qualityMeta?.total ?? rows.length}
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
        onRowClick={setSelectedIssue}
      />

      <Sheet open={!!selectedIssue} onOpenChange={(open) => !open && setSelectedIssue(null)}>
        <SheetContent className="w-[440px] border-l border-line-subtle bg-surface-elevated">
          {selectedIssue ? (
            <>
              <SheetHeader>
                <SheetTitle className="text-ink">{uploadIssueCodeLabel(selectedIssue.type)}</SheetTitle>
                <SheetDescription className="text-xs text-ink-muted">
                  {selectedIssue.entity} · {selectedIssue.source}
                </SheetDescription>
              </SheetHeader>
              <div className="mt-6 space-y-4 text-sm">
                <div className="rounded-md border border-line-subtle bg-surface-muted/40 p-3">
                  <div className="text-[11px] uppercase tracking-wide text-ink-muted">Описание</div>
                  <div className="mt-2 text-ink-secondary">{translateDescription(selectedIssue.description)}</div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-md border border-line-subtle bg-surface-muted/40 p-3">
                    <div className="text-[11px] uppercase tracking-wide text-ink-muted">Важность</div>
                    <div className="mt-2"><StatusBadge value={selectedIssue.severity as any} /></div>
                  </div>
                  <div className="rounded-md border border-line-subtle bg-surface-muted/40 p-3">
                    <div className="text-[11px] uppercase tracking-wide text-ink-muted">Обнаружено</div>
                    <div className="mt-2 text-num font-medium text-ink">{fmtRelative(selectedIssue.detectedAt)}</div>
                  </div>
                </div>
              </div>
            </>
          ) : null}
        </SheetContent>
      </Sheet>
    </>
  );
}

function translateDescription(d: string) {
  const map: Record<string, string> = {
    "Duplicate row detected for SKU/month combination": "Найдена дублирующая строка по сочетанию SKU/месяц",
    "SKU referenced in sales not present in master": "SKU из продаж отсутствует в мастер-каталоге",
    "Client name does not resolve to known DIY network": "Имя клиента не связано с известной сетью DIY",
    "Negative free stock value reported": "Получен отрицательный свободный остаток",
    "Monthly sales spike >5σ vs trailing 6m": "Всплеск месячных продаж >5σ относительно 6 мес.",
    "Gap detected in monthly sales series": "Пропуск в ряду месячных продаж",
    "Category in source disagrees with canonical category tree": "Категория источника расходится с каноническим деревом категорий",
    "Required canonical field 'client_name' is not mapped": "Обязательное каноническое поле client_name не сопоставлено",
    "Required canonical field 'sku_code' is not mapped": "Обязательное каноническое поле sku_code не сопоставлено",
    "Negative free stock detected": "Обнаружен отрицательный свободный остаток",
    "Potential duplicate row detected within the uploaded file": "Внутри загрузки найден потенциальный дубликат строки",
  };
  return map[d] ?? translateUploadIssueMessage(d);
}
