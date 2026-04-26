export const queryKeys = {
  auth: {
    all: ["auth"] as const,
    currentUser: () => ["auth", "current-user"] as const,
  },
  dashboard: {
    all: ["dashboard"] as const,
    overview: () => ["dashboard", "overview"] as const,
  },
  reserve: {
    all: ["reserve"] as const,
    runs: () => ["reserve", "runs"] as const,
  },
  clients: {
    all: ["clients"] as const,
    list: () => ["clients", "list"] as const,
    detail: (clientId: string | null) => ["clients", "detail", clientId] as const,
    reserveRows: (clientId: string | null) => ["clients", "reserve-rows", clientId] as const,
    topSkus: (clientId: string | null) => ["clients", "top-skus", clientId] as const,
    categoryExposure: (clientId: string | null) =>
      ["clients", "category-exposure", clientId] as const,
  },
  catalog: {
    all: ["catalog"] as const,
    skus: (query: string) => ["catalog", "skus", query] as const,
    skuDetail: (skuId: string | null) => ["catalog", "sku-detail", skuId] as const,
  },
  stock: {
    all: ["stock"] as const,
    coverage: (filters: Record<string, unknown>) => ["stock", "coverage", filters] as const,
    stockout: () => ["stock", "potential-stockout"] as const,
  },
  inbound: {
    all: ["inbound"] as const,
    timeline: () => ["inbound", "timeline"] as const,
  },
  quality: {
    all: ["quality"] as const,
    issues: (filters: Record<string, unknown>) => ["quality", "issues", filters] as const,
  },
  uploads: {
    all: ["uploads"] as const,
    files: (filters: Record<string, unknown>) => ["uploads", "files", filters] as const,
    file: (fileId: string | null) => ["uploads", "file", fileId] as const,
    mappingTemplates: (sourceType: string | undefined) =>
      ["uploads", "mapping-templates", sourceType ?? "all"] as const,
    issues: (fileId: string | null, filters: Record<string, unknown>) =>
      ["uploads", "issues", fileId, filters] as const,
  },
  assistant: {
    all: ["assistant"] as const,
    sessions: () => ["assistant", "sessions"] as const,
    session: (sessionId: string | null) => ["assistant", "session", sessionId] as const,
    messages: (sessionId: string | null) => ["assistant", "messages", sessionId] as const,
    capabilities: () => ["assistant", "capabilities"] as const,
    suggestions: () => ["assistant", "suggestions"] as const,
    contextOptions: () => ["assistant", "context-options"] as const,
  },
  exports: {
    all: ["exports"] as const,
    jobs: (status?: string) => ["exports", "jobs", status ?? "all"] as const,
    job: (jobId: string | null) => ["exports", "job", jobId] as const,
  },
  admin: {
    all: ["admin"] as const,
    users: () => ["admin", "users"] as const,
    jobs: (filters?: Record<string, unknown>) => ["admin", "jobs", filters ?? {}] as const,
    audit: (filters: Record<string, unknown>) => ["admin", "audit", filters] as const,
    freshness: () => ["admin", "freshness"] as const,
    health: () => ["admin", "health"] as const,
  },
} as const;
