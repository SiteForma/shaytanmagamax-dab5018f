import type { PaginatedResult, PaginationMeta } from "@/types";

export interface ApiPaginationEnvelope<T> {
  items: T[];
  meta: {
    page: number;
    pageSize: number;
    total: number;
  };
}

export function mapPaginationMeta(payload: ApiPaginationEnvelope<unknown>["meta"]): PaginationMeta {
  return {
    page: payload.page,
    pageSize: payload.pageSize,
    total: payload.total,
  };
}

export function mapPaginatedResult<TInput, TOutput>(
  payload: ApiPaginationEnvelope<TInput>,
  mapper: (item: TInput) => TOutput,
): PaginatedResult<TOutput> {
  return {
    items: payload.items.map(mapper),
    meta: mapPaginationMeta(payload.meta),
  };
}
