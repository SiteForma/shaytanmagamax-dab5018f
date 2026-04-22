import type { Sku, StockSnapshot } from "@/types";
import { SKUS, STOCK_SNAPSHOTS, monthlySales } from "@/mocks/data/seed";
import { latency } from "./_latency";

export interface StockCoverageRow {
  sku: Sku;
  free: number;
  reservedLike: number;
  demandPerMonth: number;
  coverageMonths: number;
  warehouse: StockSnapshot["warehouse"];
}

export interface StockCoverageFilters {
  category?: string;
  risk?: "low_stock" | "overstock" | "all";
  search?: string;
}

export async function getStockCoverage(filters: StockCoverageFilters = {}): Promise<StockCoverageRow[]> {
  await latency();
  const q = filters.search?.toLowerCase();
  const rows: StockCoverageRow[] = SKUS.map((sku) => {
    const stock = STOCK_SNAPSHOTS.find((s) => s.skuId === sku.id)!;
    const sales = monthlySales(sku.id, 6);
    const demand = Math.max(1, Math.round(sales.reduce((a, b) => a + b.qty, 0) / 6));
    const coverage = +(stock.freeStock / demand).toFixed(1);
    return {
      sku,
      free: stock.freeStock,
      reservedLike: stock.reservedLike,
      demandPerMonth: demand,
      coverageMonths: coverage,
      warehouse: stock.warehouse,
    };
  });

  return rows.filter((r) => {
    if (filters.category && r.sku.category !== filters.category) return false;
    if (q && !(r.sku.article.toLowerCase().includes(q) || r.sku.name.toLowerCase().includes(q))) return false;
    if (filters.risk === "low_stock" && r.coverageMonths >= 1) return false;
    if (filters.risk === "overstock" && r.coverageMonths <= 6) return false;
    return true;
  });
}
