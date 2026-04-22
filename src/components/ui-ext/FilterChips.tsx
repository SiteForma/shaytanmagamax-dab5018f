import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface FilterChipsProps<T extends string> {
  options: { value: T; label: string; count?: number }[];
  value: T | "all";
  onChange: (v: T | "all") => void;
  allLabel?: string;
  className?: string;
  renderExtra?: (v: T) => ReactNode;
}

export function FilterChips<T extends string>({
  options,
  value,
  onChange,
  allLabel = "All",
  className,
}: FilterChipsProps<T>) {
  const items = [{ value: "all" as const, label: allLabel }, ...options];
  return (
    <div className={cn("flex flex-wrap items-center gap-1.5", className)}>
      {items.map((opt) => {
        const active = value === opt.value;
        return (
          <button
            key={opt.value}
            onClick={() => onChange(opt.value as T | "all")}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium transition-colors focus-ring",
              active
                ? "border-brand/40 bg-brand/10 text-brand"
                : "border-line-subtle bg-surface-panel text-ink-secondary hover:bg-surface-hover hover:text-ink",
            )}
          >
            {opt.label}
            {"count" in opt && typeof opt.count === "number" ? (
              <span className={cn("rounded px-1 text-[10px]", active ? "bg-brand/20" : "bg-surface-muted text-ink-muted")}>
                {opt.count}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
