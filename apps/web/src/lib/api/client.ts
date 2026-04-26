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
  signal?: AbortSignal;
};

type DownloadResult = {
  blob: Blob;
  fileName: string;
  requestId: string;
};

type StreamOptions<TEvent> = Omit<RequestOptions, "body"> & {
  body?: unknown;
  onEvent: (event: TEvent) => void;
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
    signal: options.signal,
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
    signal: options.signal,
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

function parseSseBlock<TEvent>(block: string): TEvent | null {
  let eventType = "";
  const dataLines: string[] = [];

  for (const rawLine of block.split(/\r?\n/)) {
    const line = rawLine.trimEnd();
    if (!line || line.startsWith(":")) continue;
    if (line.startsWith("event:")) {
      eventType = line.slice("event:".length).trim();
      continue;
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }

  if (!dataLines.length) return null;
  const payload = JSON.parse(dataLines.join("\n"));
  return {
    type: eventType || payload.type || "message",
    ...payload,
  } as TEvent;
}

function parseNdjsonLines<TEvent>(buffer: string, onEvent: (event: TEvent) => void) {
  const lines = buffer.split(/\r?\n/);
  const remaining = lines.pop() ?? "";
  for (const line of lines) {
    const normalized = line.trim();
    if (!normalized) continue;
    onEvent(JSON.parse(normalized) as TEvent);
  }
  return remaining;
}

async function streamServerEvents<TEvent>(
  path: string,
  options: StreamOptions<TEvent>,
): Promise<void> {
  const headers = new Headers(options.headers);
  const requestId = buildRequestId();
  const session = getStoredSession();
  headers.set("X-Request-Id", requestId);
  headers.set("Accept", "text/event-stream");
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (options.authMode !== "none") {
    if (session?.accessToken) {
      headers.set("Authorization", `Bearer ${session.accessToken}`);
    } else if (DEV_USER_ID) {
      headers.set("X-Dev-User", DEV_USER_ID);
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "POST",
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    headers,
    signal: options.signal,
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

  if (!response.body) {
    throw new ApiError({
      code: "stream_body_missing",
      message: "Сервер не вернул поток ответа",
      request_id: responseRequestId,
      status: response.status,
    });
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const contentType = response.headers.get("content-type") ?? "";
  const isSse = contentType.includes("text/event-stream");

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });

    if (isSse) {
      const blocks = buffer.split(/\r?\n\r?\n/);
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        const event = parseSseBlock<TEvent>(block);
        if (event) options.onEvent(event);
      }
    } else {
      buffer = parseNdjsonLines(buffer, options.onEvent);
    }
    if (done) break;
  }

  const trailing = buffer.trim();
  if (trailing) {
    if (isSse) {
      const event = parseSseBlock<TEvent>(trailing);
      if (event) options.onEvent(event);
    } else {
      options.onEvent(JSON.parse(trailing) as TEvent);
    }
  }
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
  stream: streamServerEvents,
};
