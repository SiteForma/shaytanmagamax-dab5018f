import type { ReactNode } from "react";
import { ShieldAlert } from "lucide-react";
import { EmptyState } from "@/components/ui-ext/EmptyState";
import { Skeleton } from "@/components/ui-ext/Skeleton";
import { useCurrentUserQuery } from "@/hooks/queries/use-auth";
import { hasCapability, type Capability } from "@/lib/access";

export function CapabilityGuard({
  capability,
  title = "Доступ ограничен",
  description = "Для этого раздела у текущей роли недостаточно прав.",
  children,
}: {
  capability: Capability;
  title?: string;
  description?: string;
  children: ReactNode;
}) {
  const currentUserQuery = useCurrentUserQuery();

  if (currentUserQuery.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24" />
        <Skeleton className="h-[420px]" />
      </div>
    );
  }

  if (!hasCapability(currentUserQuery.data, capability)) {
    return (
      <div className="panel p-8">
        <EmptyState
          icon={ShieldAlert}
          title={title}
          description={description}
        />
      </div>
    );
  }

  return <>{children}</>;
}
