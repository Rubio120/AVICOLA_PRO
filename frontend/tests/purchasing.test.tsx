import { render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import { PurchasingPanel } from "@/components/purchasing-panel";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));
});

test("shows the purchasing empty state", async () => {
  render(<PurchasingPanel />);
  expect(await screen.findByText("Sin órdenes de compra.")).toBeInTheDocument();
});
