import type { PaginatedResult, QualityIssue } from "@/types";
import { mapPaginatedResult, type ApiPaginationEnvelope } from "@/adapters/common";

export function qualityIssueApiToViewModel(item: any): QualityIssue {
  return {
    id: item.id,
    type: item.type,
    severity: item.severity,
    entity: item.entity,
    description: item.description,
    detectedAt: item.detected_at,
    source: item.source,
  };
}

export function paginatedQualityIssuesApiToViewModel(
  payload: ApiPaginationEnvelope<any>,
): PaginatedResult<QualityIssue> {
  return mapPaginatedResult(payload, qualityIssueApiToViewModel);
}
