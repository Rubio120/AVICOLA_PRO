import { afterEach, describe, expect, it, vi } from "vitest";

import { getServerEnv, parseServerEnv } from "@/lib/env";


afterEach(() => {
  vi.unstubAllEnvs();
});


describe("parseServerEnv", () => {
  it("accepts a valid internal backend URL", () => {
    expect(parseServerEnv({ BACKEND_INTERNAL_URL: "http://127.0.0.1:8000" })).toEqual({
      BACKEND_INTERNAL_URL: "http://127.0.0.1:8000",
    });
  });

  it("rejects a missing backend URL", () => {
    expect(() => parseServerEnv({})).toThrow();
  });

  it("rejects a malformed backend URL", () => {
    expect(() => parseServerEnv({ BACKEND_INTERNAL_URL: "backend" })).toThrow();
  });

  it("reads the server-only URL from the process environment", () => {
    vi.stubEnv("BACKEND_INTERNAL_URL", "http://backend:8000");

    expect(getServerEnv().BACKEND_INTERNAL_URL).toBe("http://backend:8000");
  });
});
