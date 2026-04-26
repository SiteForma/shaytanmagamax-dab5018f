import type { AuthSession, CurrentUser } from "@/types";
import { api } from "@/lib/api/client";
import { clearStoredSession, getStoredSession, setStoredSession } from "@/lib/api/session";

interface LoginPayload {
  email: string;
  password: string;
}

export interface UpdateCurrentUserPayload {
  firstName: string;
  lastName: string;
  currentPassword?: string;
  newPassword?: string;
}

function splitFullName(fullName: string) {
  const [firstName = "", ...rest] = fullName.trim().split(/\s+/);
  return { firstName, lastName: rest.join(" ") };
}

function currentUserFromApi(response: any): CurrentUser {
  const fallback = splitFullName(response.full_name ?? "");
  return {
    id: response.id,
    email: response.email,
    fullName: response.full_name,
    firstName: response.first_name ?? fallback.firstName,
    lastName: response.last_name ?? fallback.lastName,
    roles: response.roles ?? [],
    capabilities: response.capabilities ?? [],
  };
}

export async function login(payload: LoginPayload): Promise<AuthSession> {
  const response = await api.post<any>(
    "/auth/login",
    { email: payload.email, password: payload.password },
    { authMode: "none" },
  );
  const session: AuthSession = {
    accessToken: response.access_token,
    refreshToken: response.refresh_token,
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
  return currentUserFromApi(response);
}

export async function updateCurrentUserProfile(payload: UpdateCurrentUserPayload): Promise<CurrentUser> {
  const response = await api.patch<any>("/auth/me", {
    first_name: payload.firstName,
    last_name: payload.lastName,
    current_password: payload.currentPassword || null,
    new_password: payload.newPassword || null,
  });
  const user = currentUserFromApi(response);
  const session = getStoredSession();
  if (session) {
    setStoredSession({ ...session, fullName: user.fullName, roles: user.roles, capabilities: user.capabilities });
  }
  return user;
}

export function getCurrentSession() {
  return getStoredSession();
}

export function logout() {
  clearStoredSession();
}
