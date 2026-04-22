import { useEffect, useState } from "react";
import { PageHeader, SectionTitle } from "@/components/ui-ext/PageHeader";
import { KpiCard } from "@/components/ui-ext/KpiCard";
import { StatusBadge } from "@/components/ui-ext/StatusBadge";
import { CoverageAreaChart, InboundShortageBarChart } from "@/components/charts/Charts";
import { Skeleton } from "@/components/ui-ext/Skeleton";
import { Button } from "@/components/ui/button";
import { getDashboardOverview, type DashboardOverview } from "@/services/dashboard.service";
import { fmtCompact, fmtInt, fmtMonths, fmtRelative } from "@/lib/formatters";
import { Boxes, Building2, AlertTriangle, PackageMinus, Truck, Activity, Calculator, Upload, Sparkles, ShieldAlert } from "lucide-react";

export default function Overview() {
  const [data, setData] = useState<DashboardOverview | null>(null);
  useEffect(() => { getDashboardOverview().then(setData); }, []);

  return (
    <>
      <PageHeader
        eyebrow="Сводка для руководства"
        title="Аналитика резерва и поставок"
        description="Оперативная картина по SKU, сетям DIY, покрытию склада и входящим поставкам в реальном времени."
        actions={
          <>
            <Button variant="outline" size="sm" className="h-9 border-line-subtle bg-surface-panel"><Upload className="mr-1.5 h-3.5 w-3.5" />Загрузить</Button>
            <Button variant="outline" size="sm" className="h-9 border-line-subtle bg-surface-panel"><ShieldAlert className="mr-1.5 h-3.5 w-3.5" />Проблемы</Button>
            <Button size="sm" className="h-9 bg-brand text-brand-foreground hover:bg-brand-hover"><Calculator className="mr-1.5 h-3.5 w-3.5" />Рассчитать резерв</Button>
          </>
        }
      />

      <section className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {data ? (
          <>
            <KpiCard label="SKU в учёте" value={data.summary.totalSkusTracked} format="int" icon={Boxes} hint="Активный мастер" />
            <KpiCard label="Клиенты DIY" value={data.summary.diyClientsUnderReserve} format="int" icon={Building2} hint="Под резервом" />
            <KpiCard label="Под риском" value={data.summary.positionsAtRisk} format="int" icon={AlertTriangle} emphasis="warning" hint="Ниже цели" />
            <KpiCard label="Дефицит резерва" value={data.summary.totalReserveShortage} unit="шт." icon={PackageMinus} emphasis="danger" />
            <KpiCard label="Поставки (60д)" value={data.summary.inboundWithinHorizon} unit="шт." icon={Truck} emphasis="brand" />
            <KpiCard label="Покрытие" value={fmtMonths(data.summary.avgCoverageMonths)} format="raw" icon={Activity} hint="Средневзвешенно" />
          </>
        ) : (
          Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-[120px]" />)
        )}
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="panel p-5 lg:col-span-2">
          <div className="mb-4 flex items-center justify-between">
            <SectionTitle>Динамика покрытия</SectionTitle>
            <span className="chip">цель 2,0 мес.</span>
          </div>
          {data ? <CoverageAreaChart data={data.coverageSeries} /> : <Skeleton className="h-[220px]" />}
        </div>
        <div className="panel p-5">
          <div className="mb-4 flex items-center justify-between">
            <SectionTitle>Свежесть данных</SectionTitle>
            <StatusBadge value={data && data.summary.freshnessHours < 6 ? "enough" : "warning"} />
          </div>
          {data ? (
            <div className="space-y-3 text-sm">
              <div className="flex items-baseline justify-between">
                <span className="text-ink-muted">Последнее обновление</span>
                <span className="text-num font-medium">{fmtRelative(data.summary.lastUpdate)}</span>
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-ink-muted">Источников синхронизировано</span>
                <span className="text-num font-medium">5 из 6</span>
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-ink-muted">Проблемы качества</span>
                <span className="text-num font-medium">28</span>
              </div>
              <div className="mt-4 rounded-md border border-line-subtle bg-surface-muted/50 p-3 text-xs text-ink-secondary">
                Расчёт резерва использует последний проверенный снимок. Устаревшие источники в KPI не учитываются.
              </div>
            </div>
          ) : <Skeleton className="h-[180px]" />}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="panel p-5">
          <div className="mb-4 flex items-center justify-between">
            <SectionTitle>Поставки и дефицит</SectionTitle>
            <span className="chip">за 8 месяцев</span>
          </div>
          {data ? <InboundShortageBarChart data={data.inboundVsShortage} /> : <Skeleton className="h-[220px]" />}
        </div>
        <div className="panel p-5">
          <div className="mb-4 flex items-center justify-between">
            <SectionTitle>SKU с наибольшим риском</SectionTitle>
            <Sparkles className="h-3.5 w-3.5 text-ink-muted" />
          </div>
          <ul className="divide-y divide-line-subtle">
            {(data?.topRiskSkus ?? []).map((r) => (
              <li key={r.sku.id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                <div className="min-w-0">
                  <div className="truncate font-medium text-ink">{r.sku.name}</div>
                  <div className="text-xs text-ink-muted">{r.sku.article} · {r.sku.category}</div>
                </div>
                <div className="text-right">
                  <div className="text-num text-sm font-semibold text-danger">−{fmtCompact(r.shortage)}</div>
                  <div className="text-[11px] text-ink-muted">покрытие {fmtMonths(r.coverageMonths)}</div>
                </div>
              </li>
            ))}
            {!data && Array.from({ length: 6 }).map((_, i) => <li key={i} className="py-2"><Skeleton className="h-8" /></li>)}
          </ul>
        </div>
      </section>

      <section className="panel p-5">
        <div className="mb-4 flex items-center justify-between">
          <SectionTitle>Наиболее уязвимые сети DIY</SectionTitle>
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
          {(data?.mostExposedClients ?? []).map((c) => (
            <div key={c.id} className="rounded-lg border border-line-subtle bg-surface-muted/40 p-4">
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold text-ink">{c.name}</div>
                <StatusBadge value={c.coverageMonths < 1 ? "critical" : c.coverageMonths < 1.5 ? "warning" : "enough"} />
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                <div><div className="text-ink-muted">Дефицит</div><div className="text-num font-medium text-ink">{fmtInt(c.shortageQty)}</div></div>
                <div><div className="text-ink-muted">Критичных</div><div className="text-num font-medium text-ink">{c.criticalPositions}</div></div>
                <div><div className="text-ink-muted">Покрытие</div><div className="text-num font-medium text-ink">{fmtMonths(c.coverageMonths)}</div></div>
                <div><div className="text-ink-muted">Поставка</div><div className="text-num font-medium text-ink">{fmtInt(c.expectedInboundRelief)}</div></div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
