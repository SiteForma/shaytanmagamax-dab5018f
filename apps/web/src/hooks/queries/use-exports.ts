import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import { getExportJob, getExportJobs } from "@/services/export.service";
import type { PaginatedResult, ExportJob } from "@/types";

function hasPendingJobs(result: PaginatedResult<ExportJob> | undefined) {
  return Boolean(result?.items.some((item) => item.status === "queued" || item.status === "running"));
}

export function useExportJobsQuery(status?: string) {
  return useQuery({
    queryKey: queryKeys.exports.jobs(status),
    queryFn: () => getExportJobs(status),
    refetchInterval: (query) => (hasPendingJobs(query.state.data as PaginatedResult<ExportJob> | undefined) ? 3000 : false),
  });
}

export function useExportJobQuery(jobId: string | null) {
  return useQuery({
    queryKey: queryKeys.exports.job(jobId),
    queryFn: () => getExportJob(jobId as string),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const job = query.state.data as ExportJob | undefined;
      return job && ["queued", "running"].includes(job.status) ? 2500 : false;
    },
  });
}
