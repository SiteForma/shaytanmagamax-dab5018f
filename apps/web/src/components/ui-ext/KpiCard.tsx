import { cn } from "@/lib/utils";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { fmtCompact, fmtInt } from "@/lib/formatters";

interface KpiCardProps {
  label: string;
  value: number | string;
  unit?: string;
  delta?: number;          // 0.12 = +12%
  hint?: string;
  icon?: LucideIcon;
  emphasis?: "default" | "brand" | "danger" | "warning";
  format?: "int" | "compact" | "raw";
  className?: string;
}

export function KpiCard({
  label,
  value,
  unit,
  delta,
  hint,
  icon: Icon,
  emphasis = "default",
  format = "compact",
  className,
}: KpiCardProps) {
  const display =
    typeof value === "string"
      ? value
      : format === "int"
      ? fmtInt(value)
      : format === "compact"
      ? fmtCompact(value)
      : String(value);

  const ringTone =
    emphasis === "brand" ? "ring-brand/30 bg-brand/5"
    : emphasis === "danger" ? "ring-danger/25 bg-danger/5"
    : emphasis === "warning" ? "ring-warning/25 bg-warning/5"
    : "ring-line-subtle/60";

  const iconTone =
    emphasis === "brand" ? "text-brand"
    : emphasis === "danger" ? "text-danger"
    : emphasis === "warning" ? "text-warning"
    : "text-ink-muted";

  return (
    <div
      className={cn(
        "panel relative overflow-hidden p-5 ring-1 transition-colors",
        "hover:bg-[hsl(var(--bg-elevated))]",
        ringTone,
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <span className="text-[11px] font-medium uppercase tracking-[0.12em] text-ink-muted">
          {label}
        </span>
        {Icon ? <Icon className={cn("h-4 w-4 shrink-0", iconTone)} /> : null}
      </div>

      <div className="mt-4 flex items-baseline gap-2">
        <span className="text-num text-3xl font-semibold text-ink">{display}</span>
        {unit ? <span className="text-sm text-ink-muted">{unit}</span> : null}
      </div>

      <div className="mt-3 flex items-center justify-between text-xs text-ink-muted">
        <span>{hint ?? "\u00A0"}</span>
        {typeof delta === "number" ? (
          <span
            className={cn(
              "inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 text-[11px] font-medium",
              delta >= 0 ? "bg-success/10 text-success" : "bg-danger/10 text-danger",
            )}
          >
            {delta >= 0 ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
            {Math.abs(delta * 100).toFixed(1)}%
          </span>
        ) : null}
      </div>
    </div>
  );
}
