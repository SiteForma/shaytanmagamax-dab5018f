import type { AuthSession } from "@/types";

const SESSION_STORAGE_KEY = "magamax.session.v1";

function storage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage;
}

export function getStoredSession(): AuthSession | null {
  const target = storage();
  if (!target) {
    return null;
  }
  const raw = target.getItem(SESSION_STORAGE_KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as AuthSession;
  } catch {
    target.removeItem(SESSION_STORAGE_KEY);
    return null;
  }
}

export function setStoredSession(session: AuthSession | null) {
  const target = storage();
  if (!target) {
    return;
  }
  if (!session) {
    target.removeItem(SESSION_STORAGE_KEY);
    return;
  }
  target.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
}

export function clearStoredSession() {
  setStoredSession(null);
}

export function hasStoredSession() {
  return Boolean(getStoredSession());
}
