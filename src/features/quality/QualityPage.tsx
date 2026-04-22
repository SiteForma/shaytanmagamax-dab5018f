import { useEffect, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { PageHeader } from "@/components/ui-ext/PageHeader";
import { DataTable } from "@/components/ui-ext/DataTable";
import { StatusBadge } from "@/components/ui-ext/StatusBadge";
import { FilterChips } from "@/components/ui-ext/FilterChips";
import { getQualityIssues } from "@/services/quality.service";
import type { QualityIssue } from "@/types";
import { fmtRelative } from "@/lib/formatters";

export default function QualityPage() {
  const [rows, setRows] = useState<QualityIssue[]>([]);
  const [loading, setLoading] = useState(true);
  const [sev, setSev] = useState<string>("all");

  useEffect(() => {
    setLoading(true);
    getQualityIssues({ severity: sev === "all" ? undefined : (sev as any) }).then((r) => { setRows(r); setLoading(false); });
  }, [sev]);

  const columns: ColumnDef<any>[] = [
    { accessorKey: "type", header: "Type", cell: (i) => <span className="chip capitalize">{(i.getValue() as string).replace("_", " ")}</span> },
    { accessorKey: "entity", header: "Entity", cell: (i) => <span className="text-num font-medium text-ink">{i.getValue() as string}</span> },
    { accessorKey: "description", header: "Description" },
    { accessorKey: "source", header: "Source", cell: (i) => <span className="text-xs text-ink-muted">{i.getValue() as string}</span> },
    { accessorKey: "detectedAt", header: "Detected", cell: (i) => <span className="text-xs text-ink-muted">{fmtRelative(i.getValue() as string)}</span> },
    { accessorKey: "severity", header: "Severity", cell: (i) => <StatusBadge value={i.getValue() as any} /> },
  ];

  return (
    <>
      <PageHeader eyebrow="Trust" title="Data quality" description="Duplicates, missing references, negative stock, suspicious spikes and category mismatches across all sources." />
      <FilterChips value={sev} onChange={setSev} options={[
        { value: "low", label: "Low" }, { value: "medium", label: "Medium" }, { value: "high", label: "High" }, { value: "critical", label: "Critical" },
      ]} />
      <DataTable data={rows} columns={columns} loading={loading} searchPlaceholder="Search issues…" density="compact" initialPageSize={20} />
    </>
  );
}
