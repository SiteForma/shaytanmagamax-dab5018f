import type { Sku, MonthlySalesPoint, StockSnapshot, InboundDelivery, DiyClient } from "@/types";
import { SKUS, STOCK_SNAPSHOTS, INBOUND, DIY_CLIENTS, monthlySales } from "@/mocks/data/seed";
import { latency } from "./_latency";

export async function listSkus(query?: string): Promise<Sku[]> {
  await latency(160);
  if (!query) return SKUS;
  const q = query.toLowerCase();
  return SKUS.filter((s) => s.article.toLowerCase().includes(q) || s.name.toLowerCase().includes(q));
}

export interface SkuDetail {
  sku: Sku;
  sales: MonthlySalesPoint[];
  stock: StockSnapshot | undefined;
  inbound: InboundDelivery[];
  clientSplit: { client: DiyClient; share: number; reservePosition: number }[];
}

export async function getSkuDetail(skuId: string): Promise<SkuDetail | null> {
  await latency();
  const sku = SKUS.find((s) => s.id === skuId);
  if (!sku) return null;
  const sales = monthlySales(skuId, 12);
  const stock = STOCK_SNAPSHOTS.find((s) => s.skuId === skuId);
  const inbound = INBOUND.filter((i) => i.skuId === skuId);

  // deterministic split among first 5 clients
  const totalShare = 100;
  const shares = [34, 22, 18, 14, 12];
  const clientSplit = DIY_CLIENTS.slice(0, 5).map((client, i) => ({
    client,
    share: shares[i] ?? 0,
    reservePosition: Math.round(((shares[i] ?? 0) / totalShare) * (sales.at(-1)?.qty ?? 0) * 2),
  }));

  return { sku, sales, stock, inbound, clientSplit };
}
