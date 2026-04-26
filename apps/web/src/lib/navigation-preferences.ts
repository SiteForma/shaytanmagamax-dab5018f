import { useCallback, useEffect, useState } from "react";
import { NAV_SECTIONS } from "@/lib/constants";

export const SIDEBAR_MENU_ORDER_STORAGE_KEY = "magamax.sidebar.menuOrder.v1";
const SIDEBAR_MENU_ORDER_EVENT = "magamax:sidebar-menu-order";

export const DEFAULT_SIDEBAR_MENU_ORDER = NAV_SECTIONS.map((item) => item.path);

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
