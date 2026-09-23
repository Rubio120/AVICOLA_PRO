import { afterEach, describe, expect, it, vi } from "vitest";

import { GET } from "@/app/api/[...path]/route";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

describe("backend-for-frontend proxy allowlist", () => {
  it.each([
    "v1/auth/login",
    "v1/company-profile",
    "v1/tax-rates",
    "v1/parties/suppliers",
    "v1/catalog/products",
    "v1/inventory/balances",
    "v1/production/balances",
    "v1/purchasing/orders",
    "v1/sales/orders",
    "v1/treasury/accounts",
    "v1/costing/runs",
    "v1/reports/dashboard",
  ])(
    "forwards %s to the backend",
    async (path) => {
      vi.stubEnv("BACKEND_INTERNAL_URL", "http://backend:8000");
      vi.spyOn(globalThis, "fetch").mockResolvedValue(
        new Response("{}", { status: 200, headers: { "content-type": "application/json" } }),
      );

      const request = new Request(`http://frontend/api/${path}`);
      const response = await GET(request as never, { params: Promise.resolve({ path: path.split("/") }) });

      expect(response.status).toBe(200);
      expect(fetch).toHaveBeenCalledWith(`http://backend:8000/api/${path}`, expect.any(Object));
    },
  );

  it("rejects paths outside the allowlist without calling the backend", async () => {
    vi.spyOn(globalThis, "fetch");

    const response = await GET(new Request("http://frontend/api/v1/admin/secrets") as never, {
      params: Promise.resolve({ path: ["v1", "admin", "secrets"] }),
    });

    expect(response.status).toBe(404);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("forwards approved request headers and returns only approved backend headers", async () => {
    vi.stubEnv("BACKEND_INTERNAL_URL", "http://backend:8000");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("{}", {
        status: 200,
        headers: {
          "content-type": "application/json",
          "x-csrf-token": "rotated-token",
          "set-cookie": "session=rotated; HttpOnly; SameSite=Strict",
          "x-internal-debug": "should-not-escape",
        },
      }),
    );

    const request = new Request("http://frontend/api/v1/reports/dashboard", {
      headers: {
        "content-type": "application/json",
        cookie: "session=synthetic",
        "user-agent": "test-agent",
        "x-correlation-id": "correlation-id",
        "x-csrf-token": "request-token",
        authorization: "not-forwarded",
      },
    });
    const response = await GET(request as never, {
      params: Promise.resolve({ path: ["v1", "reports", "dashboard"] }),
    });
    const forwardedOptions = vi.mocked(fetch).mock.calls[0]?.[1];

    expect(new Headers(forwardedOptions?.headers).get("cookie")).toBe("session=synthetic");
    expect(new Headers(forwardedOptions?.headers).get("x-csrf-token")).toBe("request-token");
    expect(new Headers(forwardedOptions?.headers).has("authorization")).toBe(false);
    expect(response.headers.get("x-csrf-token")).toBe("rotated-token");
    expect(response.headers.get("set-cookie")).toContain("session=rotated");
    expect(response.headers.has("x-internal-debug")).toBe(false);
  });
});
