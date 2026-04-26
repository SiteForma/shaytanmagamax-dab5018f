import type { CurrentUser } from "@/types";

export type Capability =
  | "dashboard:read"
  | "catalog:read"
  | "clients:read"
  | "stock:read"
  | "inbound:read"
  | "sales:read"
  | "reserve:read"
  | "reserve:run"
  | "uploads:read"
  | "uploads:write"
  | "uploads:apply"
  | "mapping:read"
  | "mapping:write"
  | "quality:read"
  | "quality:resolve"
  | "assistant:query"
  | "exports:generate"
  | "exports:download"
  | "admin:read"
  | "admin:manage-users"
  | "settings:manage";

export function hasCapability(
  user: Pick<CurrentUser, "capabilities"> | null | undefined,
  capability: Capability,
) {
  return Boolean(user?.capabilities?.includes(capability));
}
