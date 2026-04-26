import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query/keys";
import { getSkuDetail, listSkus } from "@/services/sku.service";

export function useSkusQuery(query = "") {
  return useQuery({
    queryKey: queryKeys.catalog.skus(query),
    queryFn: () => listSkus(query || undefined),
  });
}

export function useSkuDetailQuery(skuId: string | null) {
  return useQuery({
    queryKey: queryKeys.catalog.skuDetail(skuId),
    queryFn: () => getSkuDetail(skuId as string),
    enabled: Boolean(skuId),
  });
}
