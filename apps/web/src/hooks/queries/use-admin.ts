import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import {
  getAdminAuditEvents,
  getAdminHealthDetails,
  getAdminJobs,
  getAdminSystemFreshness,
  getAdminUsers,
} from "@/services/admin.service";

export function useAdminUsersQuery() {
  return useQuery({
    queryKey: queryKeys.admin.users(),
    queryFn: getAdminUsers,
  });
}

export function useAdminJobsQuery(filters: {
  status?: string;
  queueName?: string;
  jobName?: string;
} = {}) {
  return useQuery({
    queryKey: queryKeys.admin.jobs(filters),
    queryFn: () => getAdminJobs(filters),
    refetchInterval: (query) => {
      const data = query.state.data;
      return data?.items?.some((item) => item.status === "queued" || item.status === "running") ? 3000 : false;
    },
  });
}

export function useAdminAuditEventsQuery(filters: {
  action?: string;
  targetType?: string;
  page?: number;
  pageSize?: number;
}) {
  return useQuery({
    queryKey: queryKeys.admin.audit(filters),
    queryFn: () => getAdminAuditEvents(filters),
  });
}

export function useAdminSystemFreshnessQuery() {
  return useQuery({
    queryKey: queryKeys.admin.freshness(),
    queryFn: getAdminSystemFreshness,
    refetchInterval: (query) => {
      const data = query.state.data;
      return data && (data.pendingJobsCount > 0 || data.exportBacklogCount > 0) ? 5000 : false;
    },
  });
}

export function useAdminHealthDetailsQuery() {
  return useQuery({
    queryKey: queryKeys.admin.health(),
    queryFn: getAdminHealthDetails,
  });
}
