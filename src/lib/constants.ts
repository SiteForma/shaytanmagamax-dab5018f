export const NAV_SECTIONS = [
  { label: "Обзор", path: "/", icon: "LayoutDashboard" as const },
  { label: "Расчёт резерва", path: "/reserve", icon: "Calculator" as const },
  { label: "Каталог SKU", path: "/sku", icon: "Boxes" as const },
  { label: "Сети DIY", path: "/clients", icon: "Building2" as const },
  { label: "Склад и покрытие", path: "/stock", icon: "Warehouse" as const },
  { label: "Входящие поставки", path: "/inbound", icon: "Truck" as const },
  { label: "Центр загрузки", path: "/uploads", icon: "Upload" as const },
  { label: "Сопоставление данных", path: "/mapping", icon: "Workflow" as const },
  { label: "Качество данных", path: "/quality", icon: "ShieldAlert" as const },
  { label: "ИИ-консоль", path: "/ai", icon: "Sparkles" as const },
  { label: "Настройки", path: "/settings", icon: "Settings" as const },
] as const;

export const PRODUCT = {
  name: "Шайтан-машина",
  subtitle: "Аналитика резерва и поставок",
  org: "МАГАМАКС",
} as const;
