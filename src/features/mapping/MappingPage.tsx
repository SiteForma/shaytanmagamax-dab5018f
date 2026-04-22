import { useEffect, useState } from "react";
import { PageHeader } from "@/components/ui-ext/PageHeader";
import { getMappingFields } from "@/services/upload.service";
import type { MappingField } from "@/types";
import { ArrowRight, Check, AlertCircle, MinusCircle } from "lucide-react";
import { cn } from "@/lib/utils";

export default function MappingPage() {
  const [fields, setFields] = useState<MappingField[]>([]);
  useEffect(() => { getMappingFields().then(setFields); }, []);

  return (
    <>
      <PageHeader eyebrow="Normalization" title="Data mapping" description="Source fields aligned to the canonical schema, with confidence indicators and review queue." />
      <section className="panel overflow-hidden">
        <div className="grid grid-cols-12 border-b border-line-subtle bg-surface-elevated/40 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-muted">
          <div className="col-span-4">Source field</div>
          <div className="col-span-1" />
          <div className="col-span-4">Canonical</div>
          <div className="col-span-2">Sample</div>
          <div className="col-span-1 text-right">Confidence</div>
        </div>
        <ul>
          {fields.map((f, i) => (
            <li key={i} className="grid grid-cols-12 items-center border-b border-line-subtle/60 px-4 py-2.5 text-sm hover:bg-surface-hover/50">
              <div className="col-span-4 truncate text-ink">{f.source}</div>
              <div className="col-span-1 text-ink-muted"><ArrowRight className="h-3.5 w-3.5" /></div>
              <div className="col-span-4 truncate text-num text-ink-secondary">{f.canonical}</div>
              <div className="col-span-2 truncate text-xs text-ink-muted">{f.sample ?? "—"}</div>
              <div className="col-span-1 flex items-center justify-end gap-1.5">
                {f.status === "ok" && <Check className="h-3.5 w-3.5 text-success" />}
                {f.status === "review" && <AlertCircle className="h-3.5 w-3.5 text-warning" />}
                {f.status === "missing" && <MinusCircle className="h-3.5 w-3.5 text-danger" />}
                <span className={cn("text-num text-xs", f.status === "missing" ? "text-danger" : "text-ink")}>{Math.round(f.confidence * 100)}%</span>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
