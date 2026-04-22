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
        eyebrow="Executive summary"
        title="Reserve & supply intelligence"
        description="Live operational view across SKUs, DIY networks, stock coverage and inbound deliveries."
        actions={
          <>
            <Button variant="outline" size="sm" className="h-9 border-line-subtle bg-surface-panel"><Upload className="mr-1.5 h-3.5 w-3.5" />Upload</Button>
            <Button variant="outline" size="sm" className="h-9 border-line-subtle bg-surface-panel"><ShieldAlert className="mr-1.5 h-3.5 w-3.5" />Issues</Button>
            <Button size="sm" className="h-9 bg-brand text-brand-foreground hover:bg-brand-hover"><Calculator className="mr-1.5 h-3.5 w-3.5" />Calculate reserve</Button>
          </>
        }
      />

      <section className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {data ? (
          <>
            <KpiCard label="SKUs tracked" value={data.summary.totalSkusTracked} format="int" icon={Boxes} hint="Active master" />
            <KpiCard label="DIY clients" value={data.summary.diyClientsUnderReserve} format="int" icon={Building2} hint="Under reserve" />
            <KpiCard label="At risk" value={data.summary.positionsAtRisk} format="int" icon={AlertTriangle} emphasis="warning" hint="Below target" />
            <KpiCard label="Reserve shortage" value={data.summary.totalReserveShortage} unit="units" icon={PackageMinus} emphasis="danger" />
            <KpiCard label="Inbound (60d)" value={data.summary.inboundWithinHorizon} unit="units" icon={Truck} emphasis="brand" />
            <KpiCard label="Coverage" value={fmtMonths(data.summary.avgCoverageMonths)} format="raw" icon={Activity} hint="Weighted avg" />
          </>
        ) : (
          Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-[120px]" />)
        )}
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="panel p-5 lg:col-span-2">
          <div className="mb-4 flex items-center justify-between">
            <SectionTitle>Coverage trend</SectionTitle>
            <span className="chip">target 2.0 mo</span>
          </div>
          {data ? <CoverageAreaChart data={data.coverageSeries} /> : <Skeleton className="h-[220px]" />}
        </div>
        <div className="panel p-5">
          <div className="mb-4 flex items-center justify-between">
            <SectionTitle>Data freshness</SectionTitle>
            <StatusBadge value={data && data.summary.freshnessHours < 6 ? "enough" : "warning"} />
          </div>
          {data ? (
            <div className="space-y-3 text-sm">
              <div className="flex items-baseline justify-between">
                <span className="text-ink-muted">Last update</span>
                <span className="text-num font-medium">{fmtRelative(data.summary.lastUpdate)}</span>
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-ink-muted">Sources synced</span>
                <span className="text-num font-medium">5 / 6</span>
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-ink-muted">Quality issues</span>
                <span className="text-num font-medium">28</span>
              </div>
              <div className="mt-4 rounded-md border border-line-subtle bg-surface-muted/50 p-3 text-xs text-ink-secondary">
                Reserve calculations use the most recent verified snapshot. Stale sources are excluded from KPIs.
              </div>
            </div>
          ) : <Skeleton className="h-[180px]" />}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="panel p-5">
          <div className="mb-4 flex items-center justify-between">
            <SectionTitle>Inbound vs shortage</SectionTitle>
            <span className="chip">last 8 months</span>
          </div>
          {data ? <InboundShortageBarChart data={data.inboundVsShortage} /> : <Skeleton className="h-[220px]" />}
        </div>
        <div className="panel p-5">
          <div className="mb-4 flex items-center justify-between">
            <SectionTitle>Top risk SKUs</SectionTitle>
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
                  <div className="text-[11px] text-ink-muted">{fmtMonths(r.coverageMonths)} cov.</div>
                </div>
              </li>
            ))}
            {!data && Array.from({ length: 6 }).map((_, i) => <li key={i} className="py-2"><Skeleton className="h-8" /></li>)}
          </ul>
        </div>
      </section>

      <section className="panel p-5">
        <div className="mb-4 flex items-center justify-between">
          <SectionTitle>Most exposed DIY clients</SectionTitle>
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
          {(data?.mostExposedClients ?? []).map((c) => (
            <div key={c.id} className="rounded-lg border border-line-subtle bg-surface-muted/40 p-4">
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold text-ink">{c.name}</div>
                <StatusBadge value={c.coverageMonths < 1 ? "critical" : c.coverageMonths < 1.5 ? "warning" : "enough"} />
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                <div><div className="text-ink-muted">Shortage</div><div className="text-num font-medium text-ink">{fmtInt(c.shortageQty)}</div></div>
                <div><div className="text-ink-muted">Critical</div><div className="text-num font-medium text-ink">{c.criticalPositions}</div></div>
                <div><div className="text-ink-muted">Coverage</div><div className="text-num font-medium text-ink">{fmtMonths(c.coverageMonths)}</div></div>
                <div><div className="text-ink-muted">Inbound</div><div className="text-num font-medium text-ink">{fmtInt(c.expectedInboundRelief)}</div></div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
