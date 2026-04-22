import { cn } from "@/lib/utils";
import type { ReserveStatus, DeliveryStatus, QualitySeverity } from "@/types";

const STYLES: Record<string, string> = {
  // Reserve
  critical:      "bg-danger/15 text-danger border-danger/30",
  warning:       "bg-warning/15 text-warning border-warning/30",
  enough:        "bg-success/15 text-success border-success/30",
  no_history:    "bg-surface-muted text-ink-muted border-line-subtle",
  inbound_helps: "bg-info/15 text-info border-info/30",

  // Delivery
  confirmed:  "bg-success/15 text-success border-success/30",
  in_transit: "bg-info/15 text-info border-info/30",
  delayed:    "bg-warning/15 text-warning border-warning/30",
  uncertain:  "bg-danger/15 text-danger border-danger/30",

  // Severity
  low:      "bg-surface-muted text-ink-secondary border-line-subtle",
  medium:   "bg-info/15 text-info border-info/30",
  high:     "bg-warning/15 text-warning border-warning/30",
};

const LABELS: Record<string, string> = {
  critical: "Critical",
  warning: "Warning",
  enough: "Enough",
  no_history: "No history",
  inbound_helps: "Inbound helps",
  confirmed: "Confirmed",
  in_transit: "In transit",
  delayed: "Delayed",
  uncertain: "Uncertain",
  low: "Low",
  medium: "Medium",
  high: "High",
};

export type StatusValue = ReserveStatus | DeliveryStatus | QualitySeverity;

export function StatusBadge({ value, className }: { value: StatusValue; className?: string }) {
  const style = STYLES[value] ?? "bg-surface-muted text-ink-muted border-line-subtle";
  const label = LABELS[value] ?? value;
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide",
        style,
        className,
      )}
    >
      <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-current opacity-80" />
      {label}
    </span>
  );
}
