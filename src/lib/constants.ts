export const NAV_SECTIONS = [
  { label: "Overview", path: "/", icon: "LayoutDashboard" as const },
  { label: "Reserve Calculator", path: "/reserve", icon: "Calculator" as const },
  { label: "SKU Explorer", path: "/sku", icon: "Boxes" as const },
  { label: "DIY Networks", path: "/clients", icon: "Building2" as const },
  { label: "Stock & Coverage", path: "/stock", icon: "Warehouse" as const },
  { label: "Inbound Deliveries", path: "/inbound", icon: "Truck" as const },
  { label: "Upload Center", path: "/uploads", icon: "Upload" as const },
  { label: "Data Mapping", path: "/mapping", icon: "Workflow" as const },
  { label: "Data Quality", path: "/quality", icon: "ShieldAlert" as const },
  { label: "AI Console", path: "/ai", icon: "Sparkles" as const },
  { label: "Settings", path: "/settings", icon: "Settings" as const },
] as const;

export const PRODUCT = {
  name: "Shaytan Machine",
  subtitle: "Reserve & Supply Intelligence",
  org: "MAGAMAX",
} as const;
