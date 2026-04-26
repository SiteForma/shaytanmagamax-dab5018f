import { useCallback, useEffect, useState } from "react";
import { NAV_SECTIONS } from "@/lib/constants";

export const SIDEBAR_MENU_ORDER_STORAGE_KEY = "magamax.sidebar.menuOrder.v1";
export const SIDEBAR_MENU_LABELS_STORAGE_KEY = "magamax.sidebar.menuLabels.v1";
const SIDEBAR_MENU_ORDER_EVENT = "magamax:sidebar-menu-order";
const SIDEBAR_MENU_LABELS_EVENT = "magamax:sidebar-menu-labels";

export const DEFAULT_SIDEBAR_MENU_ORDER = NAV_SECTIONS.map((item) => item.path);
export const DEFAULT_SIDEBAR_MENU_LABELS = Object.fromEntries(
  NAV_SECTIONS.map((item) => [item.path, item.label]),
);

function isKnownPath(value: string): value is (typeof DEFAULT_SIDEBAR_MENU_ORDER)[number] {
  return DEFAULT_SIDEBAR_MENU_ORDER.includes(value as (typeof DEFAULT_SIDEBAR_MENU_ORDER)[number]);
}

export function normalizeSidebarMenuOrder(value: unknown): string[] {
  const source = Array.isArray(value) ? value : DEFAULT_SIDEBAR_MENU_ORDER;
  const seen = new Set<string>();
  const normalized: string[] = [];

  for (const item of source) {
    if (typeof item !== "string" || !isKnownPath(item) || seen.has(item)) continue;
    seen.add(item);
    normalized.push(item);
  }

  for (const path of DEFAULT_SIDEBAR_MENU_ORDER) {
    if (!seen.has(path)) normalized.push(path);
  }

  return normalized;
}

export function normalizeSidebarMenuLabels(value: unknown): Record<string, string> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const labels: Record<string, string> = {};
  for (const [path, label] of Object.entries(value)) {
    if (!isKnownPath(path) || typeof label !== "string") continue;
    const trimmed = label.trim().replace(/\s+/g, " ");
    if (!trimmed) continue;
    const defaultLabel = DEFAULT_SIDEBAR_MENU_LABELS[path];
    if (trimmed !== defaultLabel) labels[path] = trimmed.slice(0, 48);
  }
  return labels;
}

export function readSidebarMenuOrder(): string[] {
  if (typeof window === "undefined") return [...DEFAULT_SIDEBAR_MENU_ORDER];
  try {
    const raw = window.localStorage.getItem(SIDEBAR_MENU_ORDER_STORAGE_KEY);
    return normalizeSidebarMenuOrder(raw ? JSON.parse(raw) : null);
  } catch {
    return [...DEFAULT_SIDEBAR_MENU_ORDER];
  }
}

export function saveSidebarMenuOrder(order: unknown): string[] {
  const normalized = normalizeSidebarMenuOrder(order);
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(SIDEBAR_MENU_ORDER_STORAGE_KEY, JSON.stringify(normalized));
    } catch {
      // localStorage can be disabled; keep in-memory UI state working.
    }
    window.dispatchEvent(new CustomEvent(SIDEBAR_MENU_ORDER_EVENT, { detail: { order: normalized } }));
  }
  return normalized;
}

export function resetSidebarMenuOrder(): string[] {
  if (typeof window !== "undefined") {
    try {
      window.localStorage.removeItem(SIDEBAR_MENU_ORDER_STORAGE_KEY);
    } catch {
      // noop
    }
    window.dispatchEvent(
      new CustomEvent(SIDEBAR_MENU_ORDER_EVENT, { detail: { order: [...DEFAULT_SIDEBAR_MENU_ORDER] } }),
    );
  }
  return [...DEFAULT_SIDEBAR_MENU_ORDER];
}

export function readSidebarMenuLabels(): Record<string, string> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(SIDEBAR_MENU_LABELS_STORAGE_KEY);
    return normalizeSidebarMenuLabels(raw ? JSON.parse(raw) : null);
  } catch {
    return {};
  }
}

export function saveSidebarMenuLabels(labels: unknown): Record<string, string> {
  const normalized = normalizeSidebarMenuLabels(labels);
  if (typeof window !== "undefined") {
    try {
      if (Object.keys(normalized).length) {
        window.localStorage.setItem(SIDEBAR_MENU_LABELS_STORAGE_KEY, JSON.stringify(normalized));
      } else {
        window.localStorage.removeItem(SIDEBAR_MENU_LABELS_STORAGE_KEY);
      }
    } catch {
      // localStorage can be disabled; keep in-memory UI state working.
    }
    window.dispatchEvent(new CustomEvent(SIDEBAR_MENU_LABELS_EVENT, { detail: { labels: normalized } }));
  }
  return normalized;
}

export function resetSidebarMenuLabels(): Record<string, string> {
  if (typeof window !== "undefined") {
    try {
      window.localStorage.removeItem(SIDEBAR_MENU_LABELS_STORAGE_KEY);
    } catch {
      // noop
    }
    window.dispatchEvent(new CustomEvent(SIDEBAR_MENU_LABELS_EVENT, { detail: { labels: {} } }));
  }
  return {};
}

export function renameSidebarMenuPath(
  labels: unknown,
  path: string,
  label: string,
): Record<string, string> {
  const normalized = normalizeSidebarMenuLabels(labels);
  if (!isKnownPath(path)) return normalized;
  const trimmed = label.trim().replace(/\s+/g, " ").slice(0, 48);
  const next = { ...normalized };
  if (!trimmed || trimmed === DEFAULT_SIDEBAR_MENU_LABELS[path]) {
    delete next[path];
  } else {
    next[path] = trimmed;
  }
  return normalizeSidebarMenuLabels(next);
}

export function moveSidebarMenuPath(order: unknown, activePath: string, targetPath: string): string[] {
  const normalized = normalizeSidebarMenuOrder(order);
  if (activePath === targetPath) return normalized;
  const fromIndex = normalized.indexOf(activePath);
  const toIndex = normalized.indexOf(targetPath);
  if (fromIndex < 0 || toIndex < 0) return normalized;

  const next = [...normalized];
  const [moved] = next.splice(fromIndex, 1);
  next.splice(toIndex, 0, moved);
  return next;
}

export function orderNavItems<T extends { path: string }>(items: readonly T[], order: readonly string[]): T[] {
  const position = new Map(normalizeSidebarMenuOrder([...order]).map((path, index) => [path, index]));
  return [...items].sort((left, right) => {
    const leftIndex = position.get(left.path) ?? Number.MAX_SAFE_INTEGER;
    const rightIndex = position.get(right.path) ?? Number.MAX_SAFE_INTEGER;
    return leftIndex - rightIndex;
  });
}

export function applyNavLabels<T extends { path: string; label: string }>(
  items: readonly T[],
  labels: Record<string, string>,
): T[] {
  return items.map((item) => ({ ...item, label: labels[item.path] ?? item.label }));
}

export function findSidebarMenuPath(pathname: string): string | null {
  const normalizedPathname = pathname.split(/[?#]/)[0] || "/";
  if (normalizedPathname === "/") return "/";

  const candidates = DEFAULT_SIDEBAR_MENU_ORDER
    .filter((path) => path !== "/" && (normalizedPathname === path || normalizedPathname.startsWith(`${path}/`)))
    .sort((left, right) => right.length - left.length);

  return candidates[0] ?? null;
}

export function resolveSidebarPageTitle(
  pathname: string,
  fallbackTitle: string,
  labels: Record<string, string>,
): string {
  const matchedPath = findSidebarMenuPath(pathname);
  return matchedPath ? labels[matchedPath] ?? fallbackTitle : fallbackTitle;
}

export function useSidebarMenuOrder() {
  const [order, setOrderState] = useState<string[]>(readSidebarMenuOrder);

  useEffect(() => {
    const syncFromStorage = () => setOrderState(readSidebarMenuOrder());
    const syncFromEvent = (event: Event) => {
      const customEvent = event as CustomEvent<{ order?: unknown }>;
      setOrderState(normalizeSidebarMenuOrder(customEvent.detail?.order));
    };

    window.addEventListener("storage", syncFromStorage);
    window.addEventListener(SIDEBAR_MENU_ORDER_EVENT, syncFromEvent);
    return () => {
      window.removeEventListener("storage", syncFromStorage);
      window.removeEventListener(SIDEBAR_MENU_ORDER_EVENT, syncFromEvent);
    };
  }, []);

  const setOrder = useCallback((nextOrder: unknown) => {
    setOrderState(saveSidebarMenuOrder(nextOrder));
  }, []);

  const resetOrder = useCallback(() => {
    setOrderState(resetSidebarMenuOrder());
  }, []);

  return { order, setOrder, resetOrder };
}

export function useSidebarMenuLabels() {
  const [labels, setLabelsState] = useState<Record<string, string>>(readSidebarMenuLabels);

  useEffect(() => {
    const syncFromStorage = () => setLabelsState(readSidebarMenuLabels());
    const syncFromEvent = (event: Event) => {
      const customEvent = event as CustomEvent<{ labels?: unknown }>;
      setLabelsState(normalizeSidebarMenuLabels(customEvent.detail?.labels));
    };

    window.addEventListener("storage", syncFromStorage);
    window.addEventListener(SIDEBAR_MENU_LABELS_EVENT, syncFromEvent);
    return () => {
      window.removeEventListener("storage", syncFromStorage);
      window.removeEventListener(SIDEBAR_MENU_LABELS_EVENT, syncFromEvent);
    };
  }, []);

  const setLabels = useCallback((nextLabels: unknown) => {
    setLabelsState(saveSidebarMenuLabels(nextLabels));
  }, []);

  const renamePath = useCallback((path: string, label: string) => {
    setLabelsState((current) => saveSidebarMenuLabels(renameSidebarMenuPath(current, path, label)));
  }, []);

  const resetLabels = useCallback(() => {
    setLabelsState(resetSidebarMenuLabels());
  }, []);

  return { labels, setLabels, renamePath, resetLabels };
}
