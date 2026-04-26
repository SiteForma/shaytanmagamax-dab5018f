import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import { getDashboardOverview } from "@/services/dashboard.service";

export function useDashboardOverviewQuery() {
  return useQuery({
    queryKey: queryKeys.dashboard.overview(),
    queryFn: getDashboardOverview,
  });
}
