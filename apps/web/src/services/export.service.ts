import { exportJobApiToViewModel, paginatedExportJobsApiToViewModel } from "@/adapters/export.adapter";
import { api } from "@/lib/api/client";
import type { ExportJob, PaginatedResult } from "@/types";

function saveBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export async function createReserveRunExport(
  runId: string,
  format: "csv" | "xlsx" = "xlsx",
): Promise<ExportJob> {
  const response = await api.post<any>(`/exports/reserve-runs/${runId}?format=${format}`, {});
  return exportJobApiToViewModel(response);
}

export async function createStockCoverageExport(payload: {
  format?: "csv" | "xlsx";
  category?: string;
  risk?: string;
  search?: string;
  sortBy?: string;
  sortDir?: "asc" | "desc";
}): Promise<ExportJob> {
  const response = await api.post<any>("/exports/stock-coverage", payload);
  return exportJobApiToViewModel(response);
}

export async function createDashboardTopRiskExport(format: "csv" | "xlsx" = "xlsx"): Promise<ExportJob> {
  const response = await api.post<any>("/exports/dashboard/top-risk", { format });
  return exportJobApiToViewModel(response);
}

export async function createQualityIssuesExport(payload: {
  format?: "csv" | "xlsx";
  severity?: string;
  type?: string;
  search?: string;
  sortBy?: string;
  sortDir?: "asc" | "desc";
}): Promise<ExportJob> {
  const response = await api.post<any>("/exports/quality/issues", payload);
  return exportJobApiToViewModel(response);
}

export async function createClientExposureExport(
  format: "csv" | "xlsx" = "xlsx",
): Promise<ExportJob> {
  const response = await api.post<any>("/exports/clients/exposure", { format });
  return exportJobApiToViewModel(response);
}

export async function createDiyExposureReportPackExport(): Promise<ExportJob> {
  const response = await api.post<any>("/exports/report-packs/diy-exposure", { format: "xlsx" });
  return exportJobApiToViewModel(response);
}

export async function getExportJobs(status?: string): Promise<PaginatedResult<ExportJob>> {
  const query = new URLSearchParams();
  if (status) query.set("status", status);
  const response = await api.get<any>(`/exports/jobs${query.size ? `?${query.toString()}` : ""}`);
  return paginatedExportJobsApiToViewModel(response);
}

export async function getExportJob(jobId: string): Promise<ExportJob> {
  const response = await api.get<any>(`/exports/jobs/${jobId}`);
  return exportJobApiToViewModel(response);
}

export async function downloadExportJob(jobId: string): Promise<void> {
  const result = await api.download(`/exports/jobs/${jobId}/download`);
  saveBlob(result.blob, result.fileName);
}

export async function waitForExportJobCompletion(
  jobId: string,
  options: { pollMs?: number; timeoutMs?: number } = {},
): Promise<ExportJob> {
  const pollMs = options.pollMs ?? 2500;
  const timeoutMs = options.timeoutMs ?? 120000;
  const deadline = Date.now() + timeoutMs;
  let latest = await getExportJob(jobId);
  while (["queued", "running"].includes(latest.status)) {
    if (Date.now() > deadline) {
      throw new Error("timeout_waiting_for_export");
    }
    await new Promise((resolve) => window.setTimeout(resolve, pollMs));
    latest = await getExportJob(jobId);
  }
  return latest;
}
