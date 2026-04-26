import type { ApiErrorEnvelope } from "../../../../../packages/shared-contracts/src/api";
import { DEV_USER_ID } from "@/lib/auth/config";
import { getStoredSession } from "@/lib/api/session";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8001/api";

export class ApiError extends Error {
  code: string;
  status: number;
  requestId?: string;
  details?: Record<string, unknown>;

  constructor(
    payload: ApiErrorEnvelope & {
      status?: number;
    },
  ) {
    super(payload.message);
    this.name = "ApiError";
    this.code = payload.code;
    this.status = payload.status ?? 500;
    this.requestId = payload.request_id;
    this.details = payload.details;
  }
}

type RequestOptions = {
  method?: string;
  body?: BodyInit | null;
  headers?: HeadersInit;
  authMode?: "auto" | "none";
};

type DownloadResult = {
  blob: Blob;
  fileName: string;
  requestId: string;
};

function buildRequestId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `req_${Date.now()}`;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const requestId = buildRequestId();
  const session = getStoredSession();
  headers.set("X-Request-Id", requestId);
  if (options.authMode !== "none") {
    if (session?.accessToken) {
      headers.set("Authorization", `Bearer ${session.accessToken}`);
    } else if (DEV_USER_ID) {
      headers.set("X-Dev-User", DEV_USER_ID);
    }
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    body: options.body,
    headers,
  });
  const responseRequestId = response.headers.get("x-request-id") ?? requestId;
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ApiErrorEnvelope | null;
    throw new ApiError(
      {
        ...(payload ?? {
          code: "network_error",
          message: `Запрос завершился с ошибкой ${response.status}`,
          request_id: responseRequestId,
        }),
        code: payload?.code ?? "network_error",
        message:
          payload?.message ??
          String((payload as { detail?: string } | null)?.detail ?? `Запрос завершился с ошибкой ${response.status}`),
        request_id: payload?.request_id ?? responseRequestId,
        status: response.status,
      },
    );
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

async function download(path: string, options: Omit<RequestOptions, "body"> = {}): Promise<DownloadResult> {
  const headers = new Headers(options.headers);
  const requestId = buildRequestId();
  const session = getStoredSession();
  headers.set("X-Request-Id", requestId);
  if (options.authMode !== "none") {
    if (session?.accessToken) {
      headers.set("Authorization", `Bearer ${session.accessToken}`);
    } else if (DEV_USER_ID) {
      headers.set("X-Dev-User", DEV_USER_ID);
    }
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
  });
  const responseRequestId = response.headers.get("x-request-id") ?? requestId;
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ApiErrorEnvelope | null;
    throw new ApiError(
      {
        ...(payload ?? {
          code: "network_error",
          message: `Запрос завершился с ошибкой ${response.status}`,
          request_id: responseRequestId,
        }),
        code: payload?.code ?? "network_error",
        message:
          payload?.message ??
          String((payload as { detail?: string } | null)?.detail ?? `Запрос завершился с ошибкой ${response.status}`),
        request_id: payload?.request_id ?? responseRequestId,
        status: response.status,
      },
    );
  }
  const contentDisposition = response.headers.get("content-disposition") ?? "";
  const fileNameMatch = contentDisposition.match(/filename="?([^"]+)"?/i);
  return {
    blob: await response.blob(),
    fileName: fileNameMatch?.[1] ?? "export.bin",
    requestId: responseRequestId,
  };
}

export const api = {
  get: <T>(path: string, options?: Omit<RequestOptions, "method" | "body">) => request<T>(path, options),
  post: <T>(path: string, body: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, {
      ...options,
      method: "POST",
      body: JSON.stringify(body),
      headers: { "Content-Type": "application/json", ...(options?.headers ?? {}) },
    }),
  postForm: <T>(path: string, body: FormData, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, {
      ...options,
      method: "POST",
      body,
    }),
  patch: <T>(path: string, body: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, {
      ...options,
      method: "PATCH",
      body: JSON.stringify(body),
      headers: { "Content-Type": "application/json", ...(options?.headers ?? {}) },
    }),
  delete: <T>(path: string, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, {
      ...options,
      method: "DELETE",
    }),
  download: (path: string, options?: Omit<RequestOptions, "method" | "body">) => download(path, options),
};
