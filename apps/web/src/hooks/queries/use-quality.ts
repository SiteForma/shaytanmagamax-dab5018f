import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import { getQualityIssues, type QualityFilters } from "@/services/quality.service";

export function useQualityIssuesQuery(filters: QualityFilters) {
  return useQuery({
    queryKey: queryKeys.quality.issues(filters),
    queryFn: () => getQualityIssues(filters),
  });
}
