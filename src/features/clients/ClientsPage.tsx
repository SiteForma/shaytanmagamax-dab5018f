import { useEffect, useState } from "react";
import { PageHeader } from "@/components/ui-ext/PageHeader";
import { StatusBadge } from "@/components/ui-ext/StatusBadge";
import { listClients } from "@/services/client.service";
import type { DiyClient } from "@/types";
import { fmtInt, fmtMonths } from "@/lib/formatters";

export default function ClientsPage() {
  const [clients, setClients] = useState<DiyClient[]>([]);
  useEffect(() => { listClients().then(setClients); }, []);

  return (
    <>
      <PageHeader eyebrow="Customers" title="DIY networks" description="Reserve obligations and exposure across the strategic DIY retail networks." />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {clients.map((c) => (
          <div key={c.id} className="panel p-5 transition-colors hover:bg-surface-elevated">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-sm font-semibold text-ink">{c.name}</div>
                <div className="text-xs text-ink-muted">{c.region} · {c.reserveMonths}-month reserve</div>
              </div>
              <StatusBadge value={c.coverageMonths < 1 ? "critical" : c.coverageMonths < 1.5 ? "warning" : "enough"} />
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
              <div><div className="text-ink-muted">Positions</div><div className="text-num font-medium text-ink">{fmtInt(c.positionsTracked)}</div></div>
              <div><div className="text-ink-muted">Critical</div><div className="text-num font-medium text-danger">{c.criticalPositions}</div></div>
              <div><div className="text-ink-muted">Shortage</div><div className="text-num font-medium text-ink">{fmtInt(c.shortageQty)}</div></div>
              <div><div className="text-ink-muted">Coverage</div><div className="text-num font-medium text-ink">{fmtMonths(c.coverageMonths)}</div></div>
              <div className="col-span-2"><div className="text-ink-muted">Inbound relief</div><div className="text-num font-medium text-brand">{fmtInt(c.expectedInboundRelief)}</div></div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
