import type {
  Sku,
  DiyClient,
  StockSnapshot,
  InboundDelivery,
  ReserveRow,
  UploadJob,
  QualityIssue,
  MappingField,
  MonthlySalesPoint,
  DashboardSummary,
  SkuCategory,
  ReserveStatus,
} from "@/types";
import { createRng, pick, rand, randFloat } from "../generators/rng";

const rng = createRng(7);

const CATEGORIES: SkuCategory[] = [
  "Furniture handles",
  "Cabinet legs",
  "Drawer slides",
  "Hinges",
  "Connectors",
  "Decor & accessories",
  "Sink accessories",
  "Lighting hardware",
];

const BRANDS = ["KERRON", "LEMAX", "LEMAX Prof", "HANDY HOME", "Natural House"] as const;

const NAME_BASES = [
  "Trilliant Knob",
  "Linear Pull",
  "Chrome Bar",
  "Soft-close Slide",
  "Concealed Hinge",
  "Adjustable Leg",
  "Edge Profile RT-004",
  "Matte Pull RT-150",
  "Cabinet Connector",
  "Decor Insert",
  "Sink Bracket",
  "LED Strip Mount",
];

export const SKUS: Sku[] = Array.from({ length: 220 }).map((_, i) => {
  const cat = pick(CATEGORIES, rng);
  return {
    id: `sku_${i + 1}`,
    article: `${pick(["K", "L", "RT", "H", "C"], rng)}-${rand(1000, 9999, rng)}-${pick(["CR", "BL", "GR", "MT", "WH"], rng)}`,
    name: `${pick(NAME_BASES, rng)} ${rand(50, 320, rng)}mm`,
    category: cat,
    brand: pick(BRANDS, rng),
    unit: pick(["pcs", "set", "m"] as const, rng),
    active: rng() > 0.05,
  };
});

const CLIENT_NAMES = [
  "Leroy Merlin",
  "Leman Pro",
  "OBI Russia",
  "Petrovich",
  "Castorama",
  "Maxidom",
  "Vseinstrumenti",
  "Stroydvor",
  "Domovoy",
  "Hoff",
];

export const DIY_CLIENTS: DiyClient[] = CLIENT_NAMES.map((name, i) => {
  const positions = rand(80, 320, rng);
  const shortage = rand(400, 14000, rng);
  return {
    id: `client_${i + 1}`,
    name,
    region: pick(["Moscow", "Saint Petersburg", "Krasnodar", "Ekaterinburg", "Novosibirsk"], rng),
    reserveMonths: pick([2, 3] as const, rng),
    positionsTracked: positions,
    shortageQty: shortage,
    criticalPositions: rand(4, 38, rng),
    coverageMonths: randFloat(0.4, 4.2, rng, 1),
    expectedInboundRelief: rand(200, 5800, rng),
  };
});

export const STOCK_SNAPSHOTS: StockSnapshot[] = SKUS.map((s) => ({
  skuId: s.id,
  freeStock: rand(0, 4200, rng),
  reservedLike: rand(0, 1800, rng),
  warehouse: pick(["Shchelkovo", "Krasnodar", "Simferopol"] as const, rng),
  updatedAt: new Date(Date.now() - rand(1, 72, rng) * 3600_000).toISOString(),
}));

export const INBOUND: InboundDelivery[] = Array.from({ length: 64 }).map((_, i) => {
  const sku = pick(SKUS, rng);
  const status = pick(["confirmed", "in_transit", "delayed", "uncertain"] as const, rng);
  const eta = new Date(Date.now() + rand(2, 110, rng) * 86_400_000).toISOString();
  const aff = Array.from(new Set(Array.from({ length: rand(1, 4, rng) }).map(() => pick(DIY_CLIENTS, rng).id)));
  return {
    id: `inb_${i + 1}`,
    skuId: sku.id,
    qty: rand(120, 5400, rng),
    eta,
    status,
    affectedClients: aff,
    reserveImpact: rand(60, 3200, rng),
  };
});

export function monthlySales(skuId: string, months = 12): MonthlySalesPoint[] {
  const local = createRng(skuId.split("").reduce((a, c) => a + c.charCodeAt(0), 0));
  const base = 80 + Math.floor(local() * 600);
  const points: MonthlySalesPoint[] = [];
  const now = new Date();
  for (let i = months - 1; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const seasonal = 1 + 0.25 * Math.sin((d.getMonth() / 12) * Math.PI * 2);
    const noise = 0.7 + local() * 0.6;
    points.push({
      month: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`,
      qty: Math.max(0, Math.round(base * seasonal * noise)),
    });
  }
  return points;
}

function statusFromCoverage(c: number, hist: boolean, inbound: number, shortage: number): ReserveStatus {
  if (!hist) return "no_history";
  if (shortage > 0 && inbound >= shortage * 0.7) return "inbound_helps";
  if (c < 0.6) return "critical";
  if (c < 1) return "warning";
  return "enough";
}

export function buildReserveRows(opts: {
  clientIds: string[];
  skuIds?: string[];
  categories?: SkuCategory[];
  reserveMonths: 2 | 3;
  safetyFactor: number;
}): ReserveRow[] {
  const skus = SKUS.filter(
    (s) =>
      (!opts.skuIds || opts.skuIds.includes(s.id)) &&
      (!opts.categories?.length || opts.categories.includes(s.category)),
  ).slice(0, 60);

  const clients = DIY_CLIENTS.filter((c) => opts.clientIds.includes(c.id));
  const rows: ReserveRow[] = [];

  for (const c of clients) {
    for (const s of skus) {
      const sales = monthlySales(s.id, 6);
      const last3 = sales.slice(-3);
      const avg3 = Math.round(last3.reduce((a, b) => a + b.qty, 0) / 3);
      const avg6 = Math.round(sales.reduce((a, b) => a + b.qty, 0) / 6);
      const demand = Math.round(((avg3 + avg6) / 2) * opts.safetyFactor);
      const target = demand * opts.reserveMonths;
      const stock = STOCK_SNAPSHOTS.find((st) => st.skuId === s.id);
      const free = stock?.freeStock ?? 0;
      const inbound = INBOUND.filter((i) => i.skuId === s.id).reduce((a, b) => a + b.qty, 0);
      const available = free + inbound;
      const shortage = Math.max(0, target - available);
      const coverage = demand > 0 ? +((free / demand).toFixed(1)) : 0;
      const status = statusFromCoverage(
        demand > 0 ? available / target : 0,
        avg6 > 0,
        inbound,
        shortage,
      );

      rows.push({
        clientId: c.id,
        clientName: c.name,
        skuId: s.id,
        article: s.article,
        productName: s.name,
        category: s.category,
        avgMonthly3m: avg3,
        avgMonthly6m: avg6,
        demandPerMonth: demand,
        reserveMonths: opts.reserveMonths,
        targetReserveQty: target,
        freeStock: free,
        inboundWithinHorizon: inbound,
        availableQty: available,
        shortageQty: shortage,
        coverageMonths: coverage,
        status,
      });
    }
  }
  return rows;
}

export const UPLOAD_JOBS: UploadJob[] = [
  { id: "u1", fileName: "sales_2025_11.xlsx", sourceType: "sales", sizeBytes: 1_840_211, uploadedAt: hoursAgo(2), state: "ready", rows: 18420, issues: 3 },
  { id: "u2", fileName: "stock_snapshot_shch.csv", sourceType: "stock", sizeBytes: 220_998, uploadedAt: hoursAgo(6), state: "mapped", rows: 4302, issues: 0 },
  { id: "u3", fileName: "diy_clients_master.xlsx", sourceType: "diy_clients", sizeBytes: 38_100, uploadedAt: hoursAgo(26), state: "issues_found", rows: 211, issues: 12 },
  { id: "u4", fileName: "inbound_dec.csv", sourceType: "inbound", sizeBytes: 91_044, uploadedAt: hoursAgo(48), state: "validating", rows: 1180, issues: 0 },
  { id: "u5", fileName: "category_tree_v3.xlsx", sourceType: "category_structure", sizeBytes: 12_400, uploadedAt: hoursAgo(96), state: "ready", rows: 144, issues: 0 },
];

function hoursAgo(h: number) {
  return new Date(Date.now() - h * 3600_000).toISOString();
}

export const MAPPING_FIELDS: MappingField[] = [
  { source: "артикул", canonical: "sku.article", confidence: 0.99, status: "ok", sample: "K-2650-CR" },
  { source: "Наименование", canonical: "sku.name", confidence: 0.97, status: "ok", sample: "Trilliant Knob 128mm" },
  { source: "Категория", canonical: "sku.category", confidence: 0.84, status: "review", sample: "Ручки мебельные" },
  { source: "Контрагент", canonical: "client.name", confidence: 0.91, status: "ok", sample: "Леруа Мерлен" },
  { source: "Кол-во", canonical: "sales.qty", confidence: 0.95, status: "ok", sample: "1240" },
  { source: "Дата", canonical: "sales.month", confidence: 0.99, status: "ok", sample: "2025-11" },
  { source: "Склад", canonical: "stock.warehouse", confidence: 0.78, status: "review", sample: "Щёлково" },
  { source: "ETA", canonical: "inbound.eta", confidence: 0.88, status: "ok", sample: "2026-01-14" },
  { source: "—", canonical: "client.region", confidence: 0.0, status: "missing" },
];

export const QUALITY_ISSUES: QualityIssue[] = Array.from({ length: 28 }).map((_, i) => {
  const type = pick(
    ["duplicate", "missing_sku", "unmatched_client", "negative_stock", "suspicious_spike", "missing_month", "category_mismatch"] as const,
    rng,
  );
  const sev = pick(["low", "medium", "high", "critical"] as const, rng);
  return {
    id: `iss_${i + 1}`,
    type,
    severity: sev,
    entity: pick(SKUS, rng).article,
    description: describeIssue(type),
    detectedAt: hoursAgo(rand(1, 240, rng)),
    source: pick(["sales_2025_11.xlsx", "stock_snapshot_shch.csv", "diy_clients_master.xlsx", "inbound_dec.csv"], rng),
  };
});

function describeIssue(t: QualityIssue["type"]) {
  switch (t) {
    case "duplicate": return "Duplicate row detected for SKU/month combination";
    case "missing_sku": return "SKU referenced in sales not present in master";
    case "unmatched_client": return "Client name does not resolve to known DIY network";
    case "negative_stock": return "Negative free stock value reported";
    case "suspicious_spike": return "Monthly sales spike >5σ vs trailing 6m";
    case "missing_month": return "Gap detected in monthly sales series";
    case "category_mismatch": return "Category in source disagrees with canonical category tree";
  }
}

export const DASHBOARD_SUMMARY: DashboardSummary = {
  totalSkusTracked: SKUS.length,
  diyClientsUnderReserve: DIY_CLIENTS.length,
  positionsAtRisk: 184,
  totalReserveShortage: 38_420,
  inboundWithinHorizon: 22_180,
  avgCoverageMonths: 1.7,
  lastUpdate: hoursAgo(3),
  freshnessHours: 3,
};
