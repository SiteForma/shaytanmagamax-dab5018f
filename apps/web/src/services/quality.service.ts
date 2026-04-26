import { paginatedQualityIssuesApiToViewModel } from "@/adapters/quality.adapter";
import { api } from "@/lib/api/client";
import type { PaginatedResult, QualityIssue } from "@/types";

export interface QualityFilters {
  severity?: QualityIssue["severity"];
  type?: QualityIssue["type"];
  search?: string;
  page?: number;
  pageSize?: number;
  sortBy?: "detected_at" | "severity" | "type" | "entity" | "source";
  sortDir?: "asc" | "desc";
}

export async function getQualityIssues(
  filters: QualityFilters = {},
): Promise<PaginatedResult<QualityIssue>> {
  const query = new URLSearchParams();
  if (filters.severity) query.set("severity", filters.severity);
  if (filters.type) query.set("type", filters.type);
  if (filters.search) query.set("search", filters.search);
  if (filters.page) query.set("page", String(filters.page));
  if (filters.pageSize) query.set("page_size", String(filters.pageSize));
  if (filters.sortBy) query.set("sort_by", filters.sortBy);
  if (filters.sortDir) query.set("sort_dir", filters.sortDir);
  const response = await api.get<any>(`/quality/issues${query.size ? `?${query.toString()}` : ""}`);
  return paginatedQualityIssuesApiToViewModel(response);
}
