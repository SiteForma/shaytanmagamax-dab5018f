export const NAV_SECTIONS = [
  { label: "Обзор", path: "/", icon: "LayoutDashboard" as const, capability: "dashboard:read" as const },
  { label: "ИИ-консоль", path: "/ai", icon: "Sparkles" as const, capability: "assistant:query" as const },
  { label: "Расчёт резерва", path: "/reserve", icon: "Calculator" as const, capability: "reserve:read" as const },
  { label: "Каталог SKU", path: "/sku", icon: "Boxes" as const, capability: "catalog:read" as const },
  { label: "Сети DIY", path: "/clients", icon: "Building2" as const, capability: "clients:read" as const },
  { label: "Склад и покрытие", path: "/stock", icon: "Warehouse" as const, capability: "stock:read" as const },
  { label: "Входящие поставки", path: "/inbound", icon: "Truck" as const, capability: "inbound:read" as const },
  { label: "Центр загрузки", path: "/uploads", icon: "Upload" as const, capability: "uploads:read" as const },
  { label: "Сопоставление данных", path: "/mapping", icon: "Workflow" as const, capability: "mapping:read" as const },
  { label: "Качество данных", path: "/quality", icon: "ShieldAlert" as const, capability: "quality:read" as const },
  { label: "Администрирование", path: "/admin", icon: "ShieldCheck" as const, capability: "admin:read" as const },
  { label: "Настройки", path: "/settings", icon: "Settings" as const, capability: "settings:manage" as const },
] as const;

export const PRODUCT = {
  name: "Шайтан-машина",
  subtitle: "Аналитика резерва и поставок",
  org: "МАГАМАКС",
} as const;
