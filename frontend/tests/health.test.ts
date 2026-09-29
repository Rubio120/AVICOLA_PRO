import { afterEach, describe, expect, it, vi } from "vitest";

import { getBackendHealth } from "@/lib/api/health";


afterEach(() => {
  vi.restoreAllMocks();
});

describe("getBackendHealth", () => {
  it("reports readiness for a valid backend response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ status: "ready", database: "available" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const result = await getBackendHealth("http://backend:8000");

    expect(result).toEqual({ available: true });
    expect(fetch).toHaveBeenCalledWith("http://backend:8000/health/ready", expect.objectContaining({ cache: "no-store" }));
  });

  it.each([
    ["network failure", () => Promise.reject(new Error("internal secret"))],
    ["non-success response", () => Promise.resolve(new Response("failure", { status: 503 }))],
    ["invalid payload", () => Promise.resolve(new Response(JSON.stringify({ status: "unknown" }), { status: 200 }))],
  ])("degrades safely on %s", async (_name, responseFactory) => {
    vi.spyOn(globalThis, "fetch").mockImplementation(responseFactory);

    await expect(getBackendHealth("http://backend:8000")).resolves.toEqual({ available: false });
  });
});
