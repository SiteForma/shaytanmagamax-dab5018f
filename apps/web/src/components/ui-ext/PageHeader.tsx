import { cn } from "@/lib/utils";
import { resolveSidebarPageTitle, useSidebarMenuLabels } from "@/lib/navigation-preferences";
import type { ReactNode } from "react";
import { useLocation } from "react-router-dom";

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
}

export function PageHeader({ title, description, actions, className }: PageHeaderProps) {
  const location = useLocation();
  const { labels } = useSidebarMenuLabels();
  const resolvedTitle = resolveSidebarPageTitle(location.pathname, title, labels);

  return (
    <header className={cn("flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between", className)}>
      <div className="space-y-1.5">
        <h1 className="text-[22px] font-semibold leading-tight tracking-tight text-ink">{resolvedTitle}</h1>
        {description ? (
          <p className="max-w-2xl text-sm text-ink-secondary">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </header>
  );
}

export function SectionTitle({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <h2 className={cn("text-[13px] font-semibold uppercase tracking-[0.14em] text-ink-muted", className)}>
      {children}
    </h2>
  );
}
