import { useEffect, useMemo, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { PageHeader } from "@/components/ui-ext/PageHeader";
import { DataTable } from "@/components/ui-ext/DataTable";
import { StatusBadge } from "@/components/ui-ext/StatusBadge";
import { FilterChips } from "@/components/ui-ext/FilterChips";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { calculateReserve } from "@/services/reserve.service";
import { listClients } from "@/services/client.service";
import type { DiyClient, ReserveRow, ReserveStatus } from "@/types";
import { fmtCompact, fmtInt, fmtMonths } from "@/lib/formatters";
import { Calculator, Download } from "lucide-react";

const STATUS_OPTIONS: { value: ReserveStatus; label: string }[] = [
  { value: "critical", label: "Critical" },
  { value: "warning", label: "Warning" },
  { value: "enough", label: "Enough" },
  { value: "no_history", label: "No history" },
  { value: "inbound_helps", label: "Inbound helps" },
];

export default function ReservePage() {
  const [clients, setClients] = useState<DiyClient[]>([]);
  const [selectedClients, setSelectedClients] = useState<string[]>([]);
  const [horizon, setHorizon] = useState<2 | 3>(3);
  const [safety, setSafety] = useState(1.1);
  const [rows, setRows] = useState<ReserveRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<ReserveStatus | "all">("all");
  const [drawer, setDrawer] = useState<ReserveRow | null>(null);

  useEffect(() => {
    listClients().then((c) => {
      setClients(c);
      setSelectedClients(c.slice(0, 2).map((x) => x.id));
    });
  }, []);

  async function run() {
    setLoading(true);
    const r = await calculateReserve({
      clientIds: selectedClients,
      reserveMonths: horizon,
      safetyFactor: safety,
      demandBasis: "blended",
      horizonDays: 60,
    });
    setRows(r);
    setLoading(false);
  }

  useEffect(() => { run(); /* initial */ // eslint-disable-next-line
  }, []);

  const filtered = useMemo(
    () => (statusFilter === "all" ? rows : rows.filter((r) => r.status === statusFilter)),
    [rows, statusFilter],
  );

  const counts = useMemo(() => {
    const c: Record<ReserveStatus, number> = { critical: 0, warning: 0, enough: 0, no_history: 0, inbound_helps: 0 };
    rows.forEach((r) => { c[r.status]++; });
    return c;
  }, [rows]);

  const totals = useMemo(() => ({
    target: rows.reduce((a, b) => a + b.targetReserveQty, 0),
    shortage: rows.reduce((a, b) => a + b.shortageQty, 0),
    inbound: rows.reduce((a, b) => a + b.inboundWithinHorizon, 0),
  }), [rows]);

  const columns: ColumnDef<ReserveRow>[] = [
    { accessorKey: "clientName", header: "Client", cell: (i) => <span className="font-medium text-ink">{i.getValue() as string}</span> },
    { accessorKey: "article", header: "Article", cell: (i) => <span className="text-num text-ink-secondary">{i.getValue() as string}</span> },
    { accessorKey: "productName", header: "Product", cell: (i) => <span className="truncate text-ink">{i.getValue() as string}</span> },
    { accessorKey: "avgMonthly3m", header: "Sales 3m", meta: { align: "right", mono: true }, cell: (i) => fmtInt(i.getValue() as number) },
    { accessorKey: "avgMonthly6m", header: "Sales 6m", meta: { align: "right", mono: true }, cell: (i) => fmtInt(i.getValue() as number) },
    { accessorKey: "demandPerMonth", header: "Demand/mo", meta: { align: "right", mono: true }, cell: (i) => fmtInt(i.getValue() as number) },
    { accessorKey: "targetReserveQty", header: "Target", meta: { align: "right", mono: true }, cell: (i) => fmtInt(i.getValue() as number) },
    { accessorKey: "freeStock", header: "Free", meta: { align: "right", mono: true }, cell: (i) => fmtInt(i.getValue() as number) },
    { accessorKey: "inboundWithinHorizon", header: "Inbound", meta: { align: "right", mono: true }, cell: (i) => fmtInt(i.getValue() as number) },
    { accessorKey: "shortageQty", header: "Shortage", meta: { align: "right", mono: true }, cell: (i) => {
      const v = i.getValue() as number;
      return <span className={v > 0 ? "text-danger font-medium" : "text-ink-muted"}>{v > 0 ? `−${fmtInt(v)}` : "0"}</span>;
    } },
    { accessorKey: "coverageMonths", header: "Coverage", meta: { align: "right", mono: true }, cell: (i) => fmtMonths(i.getValue() as number) },
    { accessorKey: "status", header: "Status", cell: (i) => <StatusBadge value={i.getValue() as ReserveStatus} /> },
  ];

  return (
    <>
      <PageHeader
        eyebrow="Core workflow"
        title="Reserve calculator"
        description="Compute target reserves per DIY client and SKU using configurable horizon, safety factor and demand basis."
        actions={
          <>
            <Button variant="outline" size="sm" className="h-9 border-line-subtle bg-surface-panel"><Download className="mr-1.5 h-3.5 w-3.5" />Export</Button>
            <Button size="sm" onClick={run} className="h-9 bg-brand text-brand-foreground hover:bg-brand-hover"><Calculator className="mr-1.5 h-3.5 w-3.5" />Recalculate</Button>
          </>
        }
      />

      <section className="panel p-5">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-ink-muted">Clients</label>
            <select
              multiple
              value={selectedClients}
              onChange={(e) => setSelectedClients(Array.from(e.target.selectedOptions).map((o) => o.value))}
              className="h-28 w-full rounded-md border border-line-subtle bg-surface-panel p-2 text-sm focus-ring"
            >
              {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-ink-muted">Reserve horizon</label>
            <div className="inline-flex rounded-md border border-line-subtle bg-surface-panel p-0.5">
              {[2, 3].map((h) => (
                <button key={h} onClick={() => setHorizon(h as 2 | 3)} className={`px-3 py-1.5 text-xs font-medium rounded ${horizon === h ? "bg-brand text-brand-foreground" : "text-ink-secondary hover:text-ink"}`}>
                  {h} months
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-ink-muted">Safety factor</label>
            <input type="range" min="1" max="1.5" step="0.05" value={safety} onChange={(e) => setSafety(+e.target.value)} className="w-full accent-brand" />
            <div className="text-num text-xs text-ink-secondary mt-1">×{safety.toFixed(2)}</div>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-ink-muted">Demand basis</label>
            <select className="h-9 w-full rounded-md border border-line-subtle bg-surface-panel px-2 text-sm focus-ring">
              <option>Blended (3m + 6m)</option><option>Trailing 3 months</option><option>Trailing 6 months</option>
            </select>
          </div>
        </div>
      </section>

      <section className="panel grid grid-cols-3 divide-x divide-line-subtle">
        {[
          { label: "Total target", val: totals.target, tone: "" },
          { label: "Total shortage", val: totals.shortage, tone: "text-danger" },
          { label: "Inbound coverage", val: totals.inbound, tone: "text-brand" },
        ].map((t) => (
          <div key={t.label} className="p-4">
            <div className="text-[11px] uppercase tracking-wide text-ink-muted">{t.label}</div>
            <div className={`text-num text-2xl font-semibold ${t.tone || "text-ink"}`}>{fmtCompact(t.val)}</div>
          </div>
        ))}
      </section>

      <FilterChips
        value={statusFilter}
        onChange={setStatusFilter}
        options={STATUS_OPTIONS.map((s) => ({ ...s, count: counts[s.value] }))}
      />

      <DataTable
        data={filtered}
        columns={columns}
        loading={loading}
        searchKeys={["clientName", "article", "productName"]}
        searchPlaceholder="Search by client, article, product…"
        density="compact"
        initialPageSize={20}
        onRowClick={setDrawer}
        emptyTitle="No matching positions"
      />

      <Sheet open={!!drawer} onOpenChange={(o) => !o && setDrawer(null)}>
        <SheetContent className="w-[420px] border-l border-line-subtle bg-surface-elevated">
          {drawer && (
            <>
              <SheetHeader>
                <SheetTitle className="text-ink">{drawer.productName}</SheetTitle>
                <p className="text-xs text-ink-muted">{drawer.article} · {drawer.category} · {drawer.clientName}</p>
              </SheetHeader>
              <div className="mt-6 space-y-3 text-sm">
                {[
                  ["Avg sales 3m", fmtInt(drawer.avgMonthly3m)],
                  ["Avg sales 6m", fmtInt(drawer.avgMonthly6m)],
                  ["Demand/month (×safety)", fmtInt(drawer.demandPerMonth)],
                  ["Target reserve", fmtInt(drawer.targetReserveQty)],
                  ["Free stock", fmtInt(drawer.freeStock)],
                  ["Inbound (60d)", fmtInt(drawer.inboundWithinHorizon)],
                  ["Available", fmtInt(drawer.availableQty)],
                  ["Shortage", drawer.shortageQty > 0 ? `−${fmtInt(drawer.shortageQty)}` : "0"],
                  ["Coverage", fmtMonths(drawer.coverageMonths)],
                ].map(([k, v]) => (
                  <div key={k} className="flex items-baseline justify-between border-b border-line-subtle/60 pb-2">
                    <span className="text-ink-muted">{k}</span>
                    <span className="text-num font-medium text-ink">{v}</span>
                  </div>
                ))}
                <div className="pt-2"><StatusBadge value={drawer.status} /></div>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </>
  );
}
