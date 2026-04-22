import type { QualityIssue } from "@/types";
import { QUALITY_ISSUES } from "@/mocks/data/seed";
import { latency } from "./_latency";

export interface QualityFilters {
  severity?: QualityIssue["severity"];
  type?: QualityIssue["type"];
  search?: string;
}

export async function getQualityIssues(filters: QualityFilters = {}): Promise<QualityIssue[]> {
  await latency();
  const q = filters.search?.toLowerCase();
  return QUALITY_ISSUES.filter((i) => {
    if (filters.severity && i.severity !== filters.severity) return false;
    if (filters.type && i.type !== filters.type) return false;
    if (q && !(i.entity.toLowerCase().includes(q) || i.description.toLowerCase().includes(q))) return false;
    return true;
  });
}
