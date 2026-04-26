export const DEMAND_STRATEGY_LABELS: Record<string, string> = {
  weighted_recent_average: "Смешанная (3м + 6м)",
  strict_recent_average: "Строгая недавняя",
  conservative_fallback: "Консервативная с подстановкой",
};

export const FALLBACK_LEVEL_LABELS: Record<string, string> = {
  client_sku: "Клиент + SKU",
  client_category: "Клиент + категория",
  global_sku: "Глобальный SKU",
  category_baseline: "База категории",
  insufficient_history: "Недостаточно истории",
};

export const BASIS_WINDOW_LABELS: Record<string, string> = {
  weighted_3m_6m: "Взвешенный 3м + 6м",
  "3m": "Последние 3 месяца",
  "6m": "Последние 6 месяцев",
  "6m_fallback": "6 месяцев (fallback)",
  max_3m_6m: "Максимум из 3м и 6м",
  none: "Без окна",
};

export const SCOPE_TYPE_LABELS: Record<string, string> = {
  client_sku_list: "Клиент + список SKU",
  client_category: "Клиент + категория",
  client_full_assortment: "Клиент + весь ассортимент",
  portfolio_category: "Портфель + категория",
  portfolio_full_assortment: "Весь портфель",
};

export function reserveStrategyLabel(value: string | null | undefined): string {
  if (!value) return "—";
  return DEMAND_STRATEGY_LABELS[value] ?? value.replaceAll("_", " ");
}

export function fallbackLevelLabel(value: string | null | undefined): string {
  if (!value) return "—";
  return FALLBACK_LEVEL_LABELS[value] ?? value.replaceAll("_", " ");
}

export function basisWindowLabel(value: string | null | undefined): string {
  if (!value) return "—";
  return BASIS_WINDOW_LABELS[value] ?? value.replaceAll("_", " ");
}

export function scopeTypeLabel(value: string | null | undefined): string {
  if (!value) return "—";
  return SCOPE_TYPE_LABELS[value] ?? value.replaceAll("_", " ");
}
