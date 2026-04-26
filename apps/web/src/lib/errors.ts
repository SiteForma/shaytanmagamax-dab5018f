import { ApiError } from "@/lib/api/client";

export function getErrorMessage(error: unknown, fallback = "Не удалось загрузить данные") {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

export function getErrorRequestId(error: unknown) {
  if (error instanceof ApiError) {
    return error.requestId;
  }
  return undefined;
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}
