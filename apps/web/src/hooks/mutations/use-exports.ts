import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { queryKeys } from "@/lib/query/keys";
import {
  createClientExposureExport,
  createDashboardTopRiskExport,
  createDiyExposureReportPackExport,
  createQualityIssuesExport,
  createReserveRunExport,
  createStockCoverageExport,
  downloadExportJob,
  waitForExportJobCompletion,
} from "@/services/export.service";

function invalidateExports(queryClient: ReturnType<typeof useQueryClient>) {
  void queryClient.invalidateQueries({ queryKey: queryKeys.exports.all });
  void queryClient.invalidateQueries({ queryKey: queryKeys.admin.all });
}

function monitorQueuedExport(
  queryClient: ReturnType<typeof useQueryClient>,
  jobId: string,
  options: {
    label: string;
  },
) {
  void (async () => {
    try {
      const completed = await waitForExportJobCompletion(jobId);
      invalidateExports(queryClient);
      if (completed.status === "completed" && completed.canDownload) {
        await downloadExportJob(completed.id);
        toast.success(`${options.label} готов и скачан`);
        return;
      }
      if (completed.status === "failed") {
        toast.error(completed.errorMessage ?? `${options.label} завершился с ошибкой`);
      }
    } catch {
      invalidateExports(queryClient);
      toast.error(`${options.label} всё ещё обрабатывается. Проверь статус в админке.`);
    }
  })();
}

export function useReserveExportMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createReserveRunExport,
    onSuccess: async (job) => {
      invalidateExports(queryClient);
      if (job.canDownload) {
        await downloadExportJob(job.id);
      } else {
        monitorQueuedExport(queryClient, job.id, { label: "Экспорт расчёта" });
      }
    },
  });
}

export function useStockCoverageExportMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createStockCoverageExport,
    onSuccess: async (job) => {
      invalidateExports(queryClient);
      if (job.canDownload) {
        await downloadExportJob(job.id);
      } else {
        monitorQueuedExport(queryClient, job.id, { label: "Экспорт покрытия" });
      }
    },
  });
}

export function useDashboardTopRiskExportMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createDashboardTopRiskExport,
    onSuccess: async (job) => {
      invalidateExports(queryClient);
      if (job.canDownload) {
        await downloadExportJob(job.id);
      } else {
        monitorQueuedExport(queryClient, job.id, { label: "Экспорт top-risk списка" });
      }
    },
  });
}

export function useQualityExportMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createQualityIssuesExport,
    onSuccess: async (job) => {
      invalidateExports(queryClient);
      if (job.canDownload) {
        await downloadExportJob(job.id);
      } else {
        monitorQueuedExport(queryClient, job.id, { label: "Экспорт проблем качества" });
      }
    },
  });
}

export function useClientExposureExportMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createClientExposureExport,
    onSuccess: async (job) => {
      invalidateExports(queryClient);
      if (job.canDownload) {
        await downloadExportJob(job.id);
      } else {
        monitorQueuedExport(queryClient, job.id, { label: "Экспорт экспозиции" });
      }
    },
  });
}

export function useDiyExposureReportPackExportMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createDiyExposureReportPackExport,
    onSuccess: async (job) => {
      invalidateExports(queryClient);
      if (job.canDownload) {
        await downloadExportJob(job.id);
      } else {
        monitorQueuedExport(queryClient, job.id, { label: "Отчётный пакет DIY" });
      }
    },
  });
}

export function useDownloadExportMutation() {
  return useMutation({
    mutationFn: downloadExportJob,
  });
}
