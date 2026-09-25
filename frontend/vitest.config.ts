import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": resolve(process.cwd(), "src") },
  },
  test: {
    environment: "jsdom",
    pool: "threads",
    maxWorkers: 1,
    setupFiles: [resolve(process.cwd(), "tests/setup.ts")],
    coverage: {
      provider: "v8",
      reporter: ["text"],
      thresholds: { lines: 80, functions: 80, statements: 80, branches: 80 },
    },
  },
});
