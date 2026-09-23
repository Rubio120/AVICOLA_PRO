import { describe, expect, it } from "vitest";

import nextConfig from "../next.config";

describe("production frontend packaging", () => {
  it("enables the standalone Next.js runtime used by the image", () => {
    expect(nextConfig.output).toBe("standalone");
  });
});
