import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-line-subtle bg-surface-panel/50 p-10 text-center",
        className,
      )}
    >
      {Icon ? (
        <div className="grid h-10 w-10 place-items-center rounded-lg border border-line-subtle bg-surface-muted text-ink-muted">
          <Icon className="h-5 w-5" />
        </div>
      ) : null}
      <div className="space-y-1">
        <p className="text-sm font-medium text-ink">{title}</p>
        {description ? <p className="text-xs text-ink-muted">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}
