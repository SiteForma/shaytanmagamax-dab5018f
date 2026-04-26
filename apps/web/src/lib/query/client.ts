import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "@/lib/api/client";

function shouldRetry(failureCount: number, error: unknown) {
  if (failureCount >= 1) {
    return false;
  }
  if (error instanceof ApiError && error.status < 500) {
    return false;
  }
  return true;
}

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        retry: shouldRetry,
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: 0,
      },
    },
  });
}
