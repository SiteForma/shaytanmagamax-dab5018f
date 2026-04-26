import { useEffect, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { Skeleton } from "@/components/ui-ext/Skeleton";
import { useCurrentUserQuery, useLogoutAction } from "@/hooks/queries/use-auth";
import { ApiError } from "@/lib/api/client";
import { isStrictAuthEnabled } from "@/lib/auth/config";
import { getCurrentSession } from "@/services/auth.service";

export function AuthGuard({ children }: { children: ReactNode }) {
  const location = useLocation();
  const logout = useLogoutAction();
  const currentUserQuery = useCurrentUserQuery();
  const hasSession = Boolean(getCurrentSession());
  const strictAuth = isStrictAuthEnabled();

  useEffect(() => {
    if (!strictAuth || !currentUserQuery.error) {
      return;
    }
    if (currentUserQuery.error instanceof ApiError && currentUserQuery.error.status === 401) {
      logout();
    }
  }, [currentUserQuery.error, logout, strictAuth]);

  if (!strictAuth) {
    return <>{children}</>;
  }

  if (!hasSession) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (currentUserQuery.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24" />
        <Skeleton className="h-[420px]" />
      </div>
    );
  }

  if (currentUserQuery.error) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <>{children}</>;
}
