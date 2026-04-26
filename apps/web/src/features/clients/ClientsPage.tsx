import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { PageHeader } from "@/components/ui-ext/PageHeader";
import { StatusBadge } from "@/components/ui-ext/StatusBadge";
import {
  useClientCategoryExposureQuery,
  useClientDetailQuery,
  useClientTopSkusQuery,
  useClientsQuery,
} from "@/hooks/queries/use-clients";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { fmtInt, fmtMonths } from "@/lib/formatters";
import { QueryErrorState } from "@/components/ui-ext/QueryErrorState";
import { Skeleton } from "@/components/ui-ext/Skeleton";
import { Button } from "@/components/ui/button";
import {
  useClientExposureExportMutation,
  useDiyExposureReportPackExportMutation,
} from "@/hooks/mutations/use-exports";
import { useHasCapability } from "@/hooks/queries/use-auth";
import { Download } from "lucide-react";

export default function ClientsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedClientId = searchParams.get("client");
  const clientsQuery = useClientsQuery();
  const detailQuery = useClientDetailQuery(selectedClientId);
  const topSkusQuery = useClientTopSkusQuery(selectedClientId);
  const categoryExposureQuery = useClientCategoryExposureQuery(selectedClientId);

  const clients = clientsQuery.data ?? [];
  const selectedClient = detailQuery.data ?? null;
  const topSkus = topSkusQuery.data ?? [];
  const categoryExposure = categoryExposureQuery.data ?? [];
  const drawerLoading = detailQuery.isLoading || topSkusQuery.isLoading || categoryExposureQuery.isLoading;
  const drawerError = detailQuery.error ?? topSkusQuery.error ?? categoryExposureQuery.error;
  const clientExposureExportMutation = useClientExposureExportMutation();
  const reportPackExportMutation = useDiyExposureReportPackExportMutation();
  const canExport = useHasCapability("exports:generate");

  function openClient(clientId: string) {
    setSearchParams({ client: clientId });
  }

  return (
    <>
      <PageHeader
        eyebrow="Клиенты"
        title="Сети DIY"
        description="Обязательства по резерву и риски по ключевым DIY-сетям."
        actions={
          <>
            <Button
              variant="outline"
              size="sm"
              className="h-9 border-line-subtle bg-surface-panel"
              disabled={!canExport || clientExposureExportMutation.isPending}
              onClick={async () => {
                try {
                  const job = await clientExposureExportMutation.mutateAsync("xlsx");
                  toast.success(job.canDownload ? "Экспорт экспозиции готов" : "Экспорт экспозиции поставлен в очередь");
                } catch {
                  toast.error("Не удалось сформировать экспорт экспозиции");
                }
              }}
            >
              <Download className="mr-1.5 h-3.5 w-3.5" />
              {clientExposureExportMutation.isPending ? "Экспорт…" : "Экспорт экспозиции"}
            </Button>
            <Button
              size="sm"
              className="h-9 bg-brand text-brand-foreground hover:bg-brand-hover"
              disabled={!canExport || reportPackExportMutation.isPending}
              onClick={async () => {
                try {
                  const job = await reportPackExportMutation.mutateAsync();
                  toast.success(job.canDownload ? "Отчётный пакет DIY готов" : "Отчётный пакет DIY поставлен в очередь");
                } catch {
                  toast.error("Не удалось собрать отчётный пакет DIY");
                }
              }}
            >
              <Download className="mr-1.5 h-3.5 w-3.5" />
              {reportPackExportMutation.isPending ? "Сборка…" : "Отчётный пакет DIY"}
            </Button>
          </>
        }
      />
      {clientsQuery.error ? (
        <QueryErrorState
          error={clientsQuery.error}
          title="Список сетей пока недоступен"
          onRetry={() => void clientsQuery.refetch()}
        />
      ) : null}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {clientsQuery.isLoading
          ? Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-[188px]" />)
          : clients.map((c) => (
          <button
            key={c.id}
            onClick={() => openClient(c.id)}
            className="panel p-5 text-left transition-colors hover:bg-surface-elevated"
          >
            <div className="flex items-start justify-between">
              <div>
                <div className="text-sm font-semibold text-ink">{c.name}</div>
                <div className="text-xs text-ink-muted">{c.region} · резерв на {c.reserveMonths} мес.</div>
              </div>
              <StatusBadge value={c.coverageMonths < 1 ? "critical" : c.coverageMonths < 1.5 ? "warning" : "healthy"} />
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
              <div><div className="text-ink-muted">Позиций</div><div className="text-num font-medium text-ink">{fmtInt(c.positionsTracked)}</div></div>
              <div><div className="text-ink-muted">Критичных</div><div className="text-num font-medium text-danger">{c.criticalPositions}</div></div>
              <div><div className="text-ink-muted">Дефицит</div><div className="text-num font-medium text-ink">{fmtInt(c.shortageQty)}</div></div>
              <div><div className="text-ink-muted">Покрытие</div><div className="text-num font-medium text-ink">{fmtMonths(c.coverageMonths)}</div></div>
              <div className="col-span-2"><div className="text-ink-muted">Ожидаемая поставка</div><div className="text-num font-medium text-brand">{fmtInt(c.expectedInboundRelief)}</div></div>
            </div>
          </button>
        ))}
      </div>

      <Sheet open={Boolean(selectedClientId)} onOpenChange={(open) => !open && setSearchParams({})}>
        <SheetContent className="w-[520px] border-l border-line-subtle bg-surface-elevated">
          {drawerLoading ? (
            <div className="mt-6 space-y-3">
              <Skeleton className="h-8 w-2/3" />
              <Skeleton className="h-24" />
              <Skeleton className="h-32" />
              <Skeleton className="h-32" />
            </div>
          ) : drawerError ? (
            <QueryErrorState
              error={drawerError}
              title="Детали сети пока недоступны"
              onRetry={() => {
                void detailQuery.refetch();
                void topSkusQuery.refetch();
                void categoryExposureQuery.refetch();
              }}
              className="mt-6"
            />
          ) : selectedClient ? (
            <>
              <SheetHeader>
                <SheetTitle className="text-ink">{selectedClient.name}</SheetTitle>
                <SheetDescription className="text-xs text-ink-muted">
                  {selectedClient.region} · политика {selectedClient.code} · приоритет {selectedClient.priorityLevel}
                </SheetDescription>
              </SheetHeader>
              <div className="mt-6 space-y-5 text-sm">
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-md border border-line-subtle bg-surface-muted/40 p-3">
                    <div className="text-[11px] uppercase tracking-wide text-ink-muted">Покрытие</div>
                    <div className="mt-1 text-num text-lg font-semibold text-ink">{fmtMonths(selectedClient.coverageMonths)}</div>
                  </div>
                  <div className="rounded-md border border-line-subtle bg-surface-muted/40 p-3">
                    <div className="text-[11px] uppercase tracking-wide text-ink-muted">Дефицит</div>
                    <div className="mt-1 text-num text-lg font-semibold text-danger">{fmtInt(selectedClient.shortageQty)}</div>
                  </div>
                </div>

                <div>
                  <div className="mb-2 text-[11px] uppercase tracking-wide text-ink-muted">Главные SKU под риском</div>
                  <div className="space-y-2">
                    {topSkus.slice(0, 5).map((item) => (
                      <div key={item.skuId} className="rounded-md border border-line-subtle bg-surface-muted/30 p-3">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <div className="text-sm font-medium text-ink">{item.productName}</div>
                            <div className="text-xs text-ink-muted">{item.skuCode} · {item.categoryName ?? "Без категории"}</div>
                          </div>
                          <StatusBadge value={item.status as any} />
                        </div>
                        <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
                          <div><div className="text-ink-muted">Дефицит</div><div className="text-num font-medium">{fmtInt(item.shortageQty)}</div></div>
                          <div><div className="text-ink-muted">Цель</div><div className="text-num font-medium">{fmtInt(item.targetReserveQty)}</div></div>
                          <div><div className="text-ink-muted">Покрытие</div><div className="text-num font-medium">{item.coverageMonths == null ? "—" : fmtMonths(item.coverageMonths)}</div></div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <div className="mb-2 text-[11px] uppercase tracking-wide text-ink-muted">Экспозиция по категориям</div>
                  <div className="space-y-2">
                    {categoryExposure.slice(0, 5).map((item) => (
                      <div key={item.categoryName} className="flex items-center justify-between rounded-md border border-line-subtle bg-surface-muted/30 px-3 py-2">
                        <div>
                          <div className="text-sm font-medium text-ink">{item.categoryName}</div>
                          <div className="text-xs text-ink-muted">{fmtInt(item.positions)} позиций</div>
                        </div>
                        <div className="text-num text-sm font-semibold text-danger">{fmtInt(item.shortageQtyTotal)}</div>
                      </div>
                    ))}
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
