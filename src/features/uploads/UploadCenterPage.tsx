import { useEffect, useState } from "react";
import { PageHeader } from "@/components/ui-ext/PageHeader";
import { getUploadJobs } from "@/services/upload.service";
import type { UploadJob } from "@/types";
import { fmtBytes, fmtInt, fmtRelative } from "@/lib/formatters";
import { Upload, FileSpreadsheet } from "lucide-react";
import { cn } from "@/lib/utils";

const STATE_TONE: Record<UploadJob["state"], string> = {
  uploaded: "text-ink-muted",
  validating: "text-info",
  mapped: "text-info",
  issues_found: "text-warning",
  ready: "text-success",
};

export default function UploadCenterPage() {
  const [jobs, setJobs] = useState<UploadJob[]>([]);
  useEffect(() => { getUploadJobs().then(setJobs); }, []);

  return (
    <>
      <PageHeader eyebrow="Ingestion" title="Upload center" description="Bring sales, stock, DIY clients, category structure and inbound files into the workspace." />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="panel flex h-48 flex-col items-center justify-center gap-3 border-dashed text-center">
            <div className="grid h-10 w-10 place-items-center rounded-lg border border-line-subtle bg-surface-muted text-brand">
              <Upload className="h-5 w-5" />
            </div>
            <div>
              <div className="text-sm font-medium text-ink">Drop files to upload</div>
              <div className="text-xs text-ink-muted">XLSX, CSV — up to 50 MB. Mock pipeline only.</div>
            </div>
          </div>
        </div>
        <div className="panel p-5">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">Source type</div>
          <ul className="mt-3 space-y-1.5 text-sm">
            {["Sales", "Stock", "DIY clients", "Category structure", "Inbound", "Raw report"].map((s) => (
              <li key={s} className="flex items-center justify-between rounded-md border border-line-subtle bg-surface-muted/40 px-3 py-2 text-ink-secondary">
                <span>{s}</span>
                <span className="chip">canonical</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <section className="panel">
        <div className="border-b border-line-subtle px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">Upload history</div>
        <ul className="divide-y divide-line-subtle">
          {jobs.map((j) => (
            <li key={j.id} className="flex items-center gap-3 px-4 py-3 text-sm">
              <FileSpreadsheet className="h-4 w-4 text-ink-muted" />
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium text-ink">{j.fileName}</div>
                <div className="text-xs text-ink-muted">{j.sourceType} · {fmtBytes(j.sizeBytes)} · {fmtInt(j.rows)} rows · {fmtRelative(j.uploadedAt)}</div>
              </div>
              <span className={cn("text-xs font-medium uppercase tracking-wide", STATE_TONE[j.state])}>{j.state.replace("_", " ")}</span>
              {j.issues > 0 ? <span className="chip text-warning">{j.issues} issues</span> : null}
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
