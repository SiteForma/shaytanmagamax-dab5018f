// Core domain types for Shaytan Machine.
// These contracts mirror what the future backend should expose.

export type ID = string;

export type SkuCategory =
  | "Furniture handles"
  | "Cabinet legs"
  | "Drawer slides"
  | "Hinges"
  | "Connectors"
  | "Decor & accessories"
  | "Sink accessories"
  | "Lighting hardware";

export type ReserveStatus =
  | "critical"
  | "warning"
  | "enough"
  | "no_history"
  | "inbound_helps";

export type DeliveryStatus = "confirmed" | "in_transit" | "delayed" | "uncertain";

export type QualitySeverity = "low" | "medium" | "high" | "critical";

export type QualityIssueType =
  | "duplicate"
  | "missing_sku"
  | "unmatched_client"
  | "negative_stock"
  | "suspicious_spike"
  | "missing_month"
  | "category_mismatch";

export interface Sku {
  id: ID;
  article: string;        // e.g. "K-2650-CR"
  name: string;           // human label
  category: SkuCategory;
  brand: "KERRON" | "LEMAX" | "LEMAX Prof" | "HANDY HOME" | "Natural House";
  unit: "pcs" | "set" | "m";
  active: boolean;
}

export interface DiyClient {
  id: ID;
  name: string;            // e.g. "Leman Pro"
  region: string;
  reserveMonths: 2 | 3;
  positionsTracked: number;
  shortageQty: number;
  criticalPositions: number;
  coverageMonths: number;  // weighted
  expectedInboundRelief: number;
}

export interface MonthlySalesPoint {
  month: string; // ISO yyyy-MM
  qty: number;
}

export interface StockSnapshot {
  skuId: ID;
  freeStock: number;
  reservedLike: number;
  warehouse: "Shchelkovo" | "Krasnodar" | "Simferopol";
  updatedAt: string;
}

export interface InboundDelivery {
  id: ID;
  skuId: ID;
  qty: number;
  eta: string;             // ISO date
  status: DeliveryStatus;
  affectedClients: ID[];
  reserveImpact: number;   // qty applied to shortage
}

export interface ReserveCalculationRequest {
  clientIds: ID[];
  skuIds?: ID[];
  categories?: SkuCategory[];
  reserveMonths: 2 | 3;
  safetyFactor: number;    // 1.0 - 1.5
  demandBasis: "sales_3m" | "sales_6m" | "blended";
  horizonDays: number;     // 30..120
}

export interface ReserveRow {
  clientId: ID;
  clientName: string;
  skuId: ID;
  article: string;
  productName: string;
  category: SkuCategory;
  avgMonthly3m: number;
  avgMonthly6m: number;
  demandPerMonth: number;
  reserveMonths: number;
  targetReserveQty: number;
  freeStock: number;
  inboundWithinHorizon: number;
  availableQty: number;
  shortageQty: number;
  coverageMonths: number;
  status: ReserveStatus;
}

export interface UploadJob {
  id: ID;
  fileName: string;
  sourceType:
    | "sales"
    | "stock"
    | "diy_clients"
    | "category_structure"
    | "inbound"
    | "raw_report";
  sizeBytes: number;
  uploadedAt: string;
  state: "uploaded" | "validating" | "mapped" | "issues_found" | "ready";
  rows: number;
  issues: number;
}

export interface MappingField {
  source: string;
  canonical: string;
  confidence: number;     // 0..1
  status: "ok" | "review" | "missing";
  sample?: string;
}

export interface QualityIssue {
  id: ID;
  type: QualityIssueType;
  severity: QualitySeverity;
  entity: string;        // SKU article / client / row id
  description: string;
  detectedAt: string;
  source: string;        // file or system
}

export interface DashboardSummary {
  totalSkusTracked: number;
  diyClientsUnderReserve: number;
  positionsAtRisk: number;
  totalReserveShortage: number;
  inboundWithinHorizon: number;
  avgCoverageMonths: number;
  lastUpdate: string;
  freshnessHours: number;
}

export interface AiResponseMock {
  id: ID;
  question: string;
  answer: string;
  sources: { label: string; ref: string }[];
  followUps: string[];
  createdAt: string;
}
