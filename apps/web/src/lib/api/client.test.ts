import { afterEach, describe, expect, it, vi } from "vitest";

import { api, ApiError } from "@/lib/api/client";

describe("api client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("wraps browser network failures into a localized ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(api.get("/dashboard/overview")).rejects.toMatchObject({
      code: "network_error",
      message: "API MAGAMAX недоступен. Проверьте, что backend запущен, и повторите запрос.",
      status: 0,
    } satisfies Partial<ApiError>);
  });
});
