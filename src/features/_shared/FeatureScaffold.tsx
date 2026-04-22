import { PageHeader } from "@/components/ui-ext/PageHeader";
import { EmptyState } from "@/components/ui-ext/EmptyState";
import type { LucideIcon } from "lucide-react";

interface Props {
  eyebrow: string;
  title: string;
  description: string;
  icon: LucideIcon;
  hint?: string;
}

/**
 * Shared scaffold for feature pages whose interactive content
 * will be filled in by the next iteration. Keeps shell consistent.
 */
export function FeatureScaffold({ eyebrow, title, description, icon: Icon, hint }: Props) {
  return (
    <>
      <PageHeader eyebrow={eyebrow} title={title} description={description} />
      <EmptyState
        icon={Icon}
        title="Workspace ready"
        description={hint ?? "Mock services and types are wired. Build interactive content using the existing primitives (DataTable, KpiCard, StatusBadge, Charts)."}
      />
    </>
  );
}
