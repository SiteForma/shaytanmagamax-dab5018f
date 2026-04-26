import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import { getPotentialStockout, getStockCoverage, type StockCoverageFilters } from "@/services/stock.service";

export function useStockCoverageQuery(filters: StockCoverageFilters) {
  return useQuery({
    queryKey: queryKeys.stock.coverage(filters),
    queryFn: () => getStockCoverage(filters),
  });
}

export function usePotentialStockoutQuery() {
  return useQuery({
    queryKey: queryKeys.stock.stockout(),
    queryFn: getPotentialStockout,
  });
}
