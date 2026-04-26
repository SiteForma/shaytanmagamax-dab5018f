import {
  paginatedStockCoverageApiToViewModel,
  stockoutRowApiToViewModel,
  type PotentialStockoutRowViewModel,
  type StockCoverageRowViewModel,
} from "@/adapters/stock.adapter";
import { api } from "@/lib/api/client";
import type { PaginatedResult } from "@/types";

export type StockCoverageRow = StockCoverageRowViewModel;

export interface StockCoverageFilters {
  category?: string;
  risk?: "low_stock" | "overstock" | "all";
  search?: string;
  page?: number;
  pageSize?: number;
  sortBy?:
    | "article"
    | "product_name"
    | "category_name"
    | "free"
    | "demand_per_month"
    | "coverage_months"
    | "shortage_qty_total"
    | "affected_clients_count"
    | "worst_status";
  sortDir?: "asc" | "desc";
}

export async function getStockCoverage(
  filters: StockCoverageFilters = {},
): Promise<PaginatedResult<StockCoverageRow>> {
  const query = new URLSearchParams();
  if (filters.category) query.set("category", filters.category);
  if (filters.risk) query.set("risk", filters.risk);
  if (filters.search) query.set("search", filters.search);
  if (filters.page) query.set("page", String(filters.page));
  if (filters.pageSize) query.set("page_size", String(filters.pageSize));
  if (filters.sortBy) query.set("sort_by", filters.sortBy);
  if (filters.sortDir) query.set("sort_dir", filters.sortDir);
  const response = await api.get<any>(`/stock/coverage${query.size ? `?${query.toString()}` : ""}`);
  return paginatedStockCoverageApiToViewModel(response);
}

export type PotentialStockoutRow = PotentialStockoutRowViewModel;

export async function getPotentialStockout(): Promise<PotentialStockoutRow[]> {
  const response = await api.get<any[]>("/stock/potential-stockout");
  return response.map(stockoutRowApiToViewModel);
}
