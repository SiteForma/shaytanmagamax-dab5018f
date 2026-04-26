import type { AuthSession, CurrentUser } from "@/types";
import { api } from "@/lib/api/client";
import { clearStoredSession, getStoredSession, setStoredSession } from "@/lib/api/session";

interface LoginPayload {
  email: string;
  password: string;
}

export async function login(payload: LoginPayload): Promise<AuthSession> {
  const response = await api.post<any>(
    "/auth/login",
    { email: payload.email, password: payload.password },
    { authMode: "none" },
  );
  const session: AuthSession = {
    accessToken: response.access_token,
    tokenType: response.token_type,
    userId: response.user_id,
    email: response.email,
    fullName: response.full_name,
    roles: response.roles ?? [],
    capabilities: response.capabilities ?? [],
  };
  setStoredSession(session);
  return session;
}

export async function getCurrentUser(): Promise<CurrentUser> {
  const response = await api.get<any>("/auth/me");
  return {
    id: response.id,
    email: response.email,
    fullName: response.full_name,
    roles: response.roles ?? [],
    capabilities: response.capabilities ?? [],
  };
}

export function getCurrentSession() {
  return getStoredSession();
}

export function logout() {
  clearStoredSession();
}
