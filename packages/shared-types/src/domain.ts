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
  | "healthy"
  | "inactive"
  | "overstocked"
  | "enough"
  | "no_history"
  | "inbound_helps";

export type DeliveryStatus = "confirmed" | "in_transit" | "delayed" | "uncertain";
export type QualitySeverity =
  | "info"
  | "warning"
  | "error"
  | "critical"
  | "low"
  | "medium"
  | "high";

export type QualityIssueType =
  | "duplicate"
  | "missing_sku"
  | "unmatched_client"
  | "negative_stock"
  | "suspicious_spike"
  | "missing_month"
  | "category_mismatch"
  | "unmatched_reference"
  | "mapping_required";

export type UploadState =
  | "uploaded"
  | "parsing"
  | "source_confirmation_required"
  | "mapping_required"
  | "validating"
  | "issues_found"
  | "ready_to_review"
  | "ready_to_apply"
  | "applying"
  | "applied"
  | "applied_with_warnings"
  | "failed"
  | "normalized"
  | "mapped"
  | "ready";

export interface Sku {
  id: ID;
  article: string;
  name: string;
  category: SkuCategory | string | null;
  brand: string;
  unit: string;
  active: boolean;
}

export interface DiyClient {
  id: ID;
  name: string;
  region: string;
  reserveMonths: number;
  positionsTracked: number;
  shortageQty: number;
  criticalPositions: number;
  warningPositions?: number;
  coverageMonths: number;
  expectedInboundRelief: number;
  latestRunId?: ID | null;
}

export interface MonthlySalesPoint {
  month: string;
  qty: number;
}

export interface StockSnapshot {
  skuId: ID;
  freeStock: number;
  reservedLike: number;
  warehouse: string;
  updatedAt: string;
}

export interface InboundDelivery {
  id: ID;
  skuId: ID;
  qty: number;
  freeStockAfterAllocation?: number;
  clientOrderQty?: number;
  eta: string;
  status: DeliveryStatus | string;
  affectedClients: ID[];
  clientAllocations?: Record<string, number>;
  reserveImpact: number;
}

export interface ReserveCalculationRequest {
  clientIds?: ID[];
  skuIds?: ID[];
  skuCodes?: string[];
  categoryIds?: ID[];
  categories?: string[];
  reserveMonths?: number;
  safetyFactor?: number;
  demandBasis?: "sales_3m" | "sales_6m" | "blended";
  demandStrategy?: "weighted_recent_average" | "strict_recent_average" | "conservative_fallback";
  includeInbound?: boolean;
  inboundStatusesToCount?: string[];
  asOfDate?: string;
  groupingMode?: string;
  persistRun?: boolean;
  horizonDays?: number;
}

export interface ReserveRow {
  clientId: ID;
  clientName: string;
  skuId: ID;
  article: string;
  productName: string;
  category: string | null;
  avgMonthly3m: number;
  avgMonthly6m: number;
  demandPerMonth: number;
  reserveMonths: number;
  safetyFactor?: number;
  targetReserveQty: number;
  freeStock: number;
  inboundWithinHorizon: number;
  totalFreeStockQty?: number;
  totalInboundWithinHorizonQty?: number;
  allocatedFreeStockQty?: number;
  allocatedInboundQty?: number;
  availableQty: number;
  shortageQty: number;
  coverageMonths: number | null;
  status: ReserveStatus | string;
  statusReason?: string;
  demandBasis?: string;
  demandBasisType?: string;
  fallbackLevel?: string;
  basisWindowUsed?: string;
  historyMonthsAvailable?: number;
  salesQty1m?: number;
  salesQty3m?: number;
  salesQty6m?: number;
  trendSignal?: string;
  demandStability?: number;
  lastSaleDate?: string | null;
  explanationPayload?: Record<string, unknown>;
}

export interface ReserveRunSummary {
  id: ID;
  scopeType: string;
  groupingMode: string;
  reserveMonths: number;
  safetyFactor: number;
  demandStrategy: string;
  includeInbound: boolean;
  inboundStatuses: string[];
  horizonDays: number;
  rowCount: number;
  status: string;
  createdAt: string;
  summaryPayload: Record<string, unknown>;
}

export interface ReserveCalculationResult {
  run: ReserveRunSummary;
  rows: ReserveRow[];
}

export interface UploadJob {
  id: ID;
  batchId?: ID;
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
  state: UploadState;
  rows: number;
  issues: number;
  appliedRows?: number;
  failedRows?: number;
  warningsCount?: number;
  canApply?: boolean;
  canValidate?: boolean;
  canEditMapping?: boolean;
  duplicateOfBatchId?: ID | null;
  detectedSourceType?: UploadJob["sourceType"];
  sourceDetection?: UploadSourceDetection | null;
}

export interface UploadSourceTypeCandidate {
  sourceType: UploadJob["sourceType"];
  confidence: number;
  matchedFields: string[];
}

export interface UploadSourceDetection {
  requiresConfirmation: boolean;
  confirmed: boolean;
  detectedSourceType: UploadJob["sourceType"];
  selectedSourceType: UploadJob["sourceType"];
  candidates: UploadSourceTypeCandidate[];
  customEntityName?: string | null;
}

export interface MappingField {
  source: string;
  canonical: string;
  confidence: number;
  status: "ok" | "review" | "missing";
  sample?: string;
  candidates?: string[];
  required?: boolean;
}

export interface QualityIssue {
  id: ID;
  type: QualityIssueType | string;
  severity: QualitySeverity | string;
  entity: string;
  description: string;
  detectedAt: string;
  source: string;
}

export interface IssueCounts {
  info: number;
  warning: number;
  error: number;
  critical: number;
  total: number;
}

export interface UploadPreview {
  fileId: ID;
  sourceType: UploadJob["sourceType"];
  detectedSourceType: UploadJob["sourceType"];
  parser: string;
  encoding?: string | null;
  headers: string[];
  sampleRows: Record<string, unknown>[];
  sampleRowCount: number;
  emptyRowCount: number;
}

export interface UploadValidationSummary {
  totalRows: number;
  validRows: number;
  failedRows: number;
  warningsCount: number;
  issuesCount: number;
  issueCounts: IssueCounts;
  hasBlockingIssues: boolean;
}

export interface UploadIssue {
  id: ID;
  rowNumber: number;
  fieldName?: string | null;
  code: string;
  severity: QualitySeverity | string;
  message: string;
  rawPayload?: Record<string, unknown> | null;
}

export interface UploadJobRun {
  id: ID;
  jobName: string;
  queueName: string;
  status: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  errorMessage?: string | null;
}

export interface UploadMappingState {
  sourceType: UploadJob["sourceType"];
  canonicalFields: string[];
  requiredFields: string[];
  supportsApply: boolean;
  templateId?: ID | null;
  suggestions: MappingField[];
  activeMapping: Record<string, string>;
}

export interface UploadFileDetail {
  file: UploadJob;
  preview: UploadPreview;
  mapping: UploadMappingState;
  validation: UploadValidationSummary;
  jobs: UploadJobRun[];
  issuesPreview: UploadIssue[];
}

export interface MappingTemplate {
  id: ID;
  name: string;
  sourceType: UploadJob["sourceType"];
  version: number;
  isDefault: boolean;
  isActive: boolean;
  requiredFields: string[];
  transformationHints: Record<string, unknown>;
  mappings: Record<string, string>;
  createdAt: string;
  updatedAt: string;
}

export interface AliasEntry {
  id: ID;
  alias: string;
  entityId: ID;
  entityCode: string;
  entityName: string;
  createdAt: string;
}

export interface DashboardSummary {
  totalSkusTracked: number;
  diyClientsUnderReserve: number;
  positionsAtRisk: number;
  totalReserveShortage: number;
  inboundWithinHorizon: number;
  avgCoverageMonths: number;
  assistantApiCostRub: number;
  lastUpdate: string;
  freshnessHours: number;
}

export type AssistantIntent =
  | "reserve_calculation"
  | "reserve_explanation"
  | "stock_risk_summary"
  | "inbound_impact"
  | "diy_coverage_check"
  | "sku_summary"
  | "client_summary"
  | "upload_status_summary"
  | "quality_issue_summary"
  | "management_report_summary"
  | "sales_summary"
  | "period_comparison"
  | "analytics_slice"
  | "data_overview"
  | "free_chat"
  | "unsupported_or_ambiguous";

export type AssistantResponseType = "answer" | "clarification";

export type AssistantResponseStatus =
  | "completed"
  | "partial"
  | "needs_clarification"
  | "unsupported"
  | "failed";

export type AssistantSectionType =
  | "narrative"
  | "metric_summary"
  | "reserve_table_preview"
  | "source_list"
  | "warning_block"
  | "next_actions"
  | "clarification";

export interface AssistantPinnedContext {
  selectedClientId?: ID | null;
  selectedSkuId?: ID | null;
  selectedUploadIds?: ID[];
  selectedReserveRunId?: ID | null;
  selectedCategoryId?: ID | null;
}

export interface AssistantMetric {
  key: string;
  label: string;
  value: string;
  tone: "neutral" | "warning" | "critical" | "positive";
}

export interface AssistantSection {
  id: ID;
  type: AssistantSectionType;
  title: string;
  body?: string | null;
  metrics: AssistantMetric[];
  rows: Record<string, unknown>[];
  items: string[];
}

export interface AssistantSourceRef {
  sourceType: string;
  sourceLabel: string;
  entityType: string;
  entityId?: ID | null;
  externalKey?: string | null;
  freshnessAt?: string | null;
  role: "primary" | "supporting" | "warning";
  route?: string | null;
  detail?: string | null;
}

export interface AssistantToolCall {
  toolName: string;
  status: "completed" | "failed" | "skipped";
  arguments: Record<string, unknown>;
  summary: string;
  latencyMs: number;
}

export interface AssistantWarning {
  code: string;
  message: string;
  severity: "info" | "warning" | "error";
}

export interface AssistantFollowupSuggestion {
  id: ID;
  label: string;
  prompt: string;
  action: "query" | "open";
  route?: string | null;
}

export interface AssistantTokenUsage {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  estimatedCostUsd: number;
  estimatedCostRub: number;
}

export interface AssistantMissingField {
  name: string;
  label?: string | null;
  question?: string | null;
  type?: string | null;
}

export interface AssistantResponse {
  answerId: ID;
  sessionId?: ID | null;
  type?: AssistantResponseType;
  intent: AssistantIntent;
  status: AssistantResponseStatus;
  confidence: number;
  title: string;
  summary: string;
  sections: AssistantSection[];
  sourceRefs: AssistantSourceRef[];
  toolCalls: AssistantToolCall[];
  followups: AssistantFollowupSuggestion[];
  warnings: AssistantWarning[];
  createdAt: string;
  provider?: string;
  tokenUsage?: AssistantTokenUsage;
  traceId: ID;
  contextUsed: AssistantPinnedContext;
  missingFields?: AssistantMissingField[];
  suggestedChips?: string[];
  pendingIntent?: AssistantIntent | null;
  traceMetadata?: Record<string, unknown>;
}

export interface AssistantMessage {
  id: ID;
  sessionId: ID;
  role: "user" | "assistant";
  text: string;
  createdAt: string;
  intent?: AssistantIntent | null;
  status: string;
  provider?: string | null;
  confidence?: number | null;
  traceId?: string | null;
  context: AssistantPinnedContext;
  response?: AssistantResponse | null;
}

export interface AssistantSession {
  id: ID;
  title: string;
  status: string;
  createdAt: string;
  updatedAt: string;
  lastMessageAt?: string | null;
  messageCount: number;
  pinnedContext: AssistantPinnedContext;
  lastIntent?: AssistantIntent | null;
  preferredMode: string;
  provider: string;
  latestTraceId?: string | null;
  tokenUsage?: AssistantTokenUsage;
  estimatedCostRub?: number;
}

export interface AssistantCapabilities {
  provider: string;
  deterministicFallback: boolean;
  intents: { key: AssistantIntent | string; label: string; supported: boolean }[];
  sessionSupport: boolean;
  pinnedContextSupport: boolean;
}

export interface AssistantPromptSuggestion {
  id: ID;
  label: string;
  prompt: string;
  intent: AssistantIntent;
}

export interface AssistantContextOption {
  id: ID;
  label: string;
  hint?: string | null;
}

export interface AssistantContextOptions {
  clients: AssistantContextOption[];
  skus: AssistantContextOption[];
  uploads: AssistantContextOption[];
  reserveRuns: AssistantContextOption[];
  categories: AssistantContextOption[];
}

export interface AssistantSessionMessageResult {
  session: AssistantSession;
  userMessage: AssistantMessage;
  assistantMessage: AssistantMessage;
  response: AssistantResponse;
}

export type AiResponseMock = AssistantResponse;

export interface AuthSession {
  accessToken: string;
  refreshToken?: string;
  tokenType: string;
  userId: ID;
  email: string;
  fullName: string;
  roles: string[];
  capabilities: string[];
}

export interface CurrentUser {
  id: ID;
  email: string;
  fullName: string;
  firstName: string;
  lastName: string;
  roles: string[];
  capabilities: string[];
}

export interface ExportJob {
  id: ID;
  exportType: string;
  status: string;
  format: "csv" | "xlsx";
  fileName?: string | null;
  rowCount: number;
  requestedById?: ID | null;
  requestedAt: string;
  completedAt?: string | null;
  errorMessage?: string | null;
  filtersPayload: Record<string, unknown>;
  summaryPayload: Record<string, unknown>;
  downloadUrl?: string | null;
  canDownload: boolean;
}

export interface AdminUser {
  id: ID;
  email: string;
  fullName: string;
  isActive: boolean;
  roles: string[];
  capabilities: string[];
  createdAt: string;
}

export interface AdminJob {
  id: ID;
  jobName: string;
  queueName: string;
  status: string;
  payload: Record<string, unknown>;
  startedAt?: string | null;
  finishedAt?: string | null;
  errorMessage?: string | null;
  createdAt: string;
  canRetry: boolean;
}

export interface AuditEvent {
  id: ID;
  actorUserId?: ID | null;
  action: string;
  targetType: string;
  targetId?: string | null;
  status: string;
  traceId?: string | null;
  requestId?: string | null;
  createdAt: string;
  context: Record<string, unknown>;
}

export interface AdminSystemFreshness {
  lastSalesIngestAt?: string | null;
  lastStockSnapshotAt?: string | null;
  lastInboundUpdateAt?: string | null;
  lastQualityRunAt?: string | null;
  lastReserveRefreshAt?: string | null;
  failedJobsCount: number;
  pendingJobsCount: number;
  exportBacklogCount: number;
  failedExportsCount: number;
  runningExportsCount: number;
}

export interface AdminHealthDetails {
  appEnv: string;
  appDebug: boolean;
  appRelease?: string | null;
  databaseOk: boolean;
  redisConfigured: boolean;
  objectStorageMode: string;
  exportRoot: string;
  exportAsyncEnabled: boolean;
  exportAsyncRowThreshold: number;
  assistantProvider: string;
  sentryEnabled: boolean;
  otelEnabled: boolean;
  startupSchemaMode: string;
  startupSeedSampleData: boolean;
  startupMaterializeAnalytics: boolean;
  workerQueues: string[];
  environmentWarnings: string[];
  requestIdHeader: string;
  corsOrigins: string[];
}

export interface PaginationMeta {
  page: number;
  pageSize: number;
  total: number;
}

export interface PaginatedResult<T> {
  items: T[];
  meta: PaginationMeta;
}
