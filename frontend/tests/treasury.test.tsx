import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { TreasuryPanel } from "@/components/treasury-panel";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));
});

test("shows the treasury empty state after loading", async () => {
  render(<TreasuryPanel />);
  await waitFor(() => expect(screen.getByText("Sin cuentas de caja activas.")).toBeInTheDocument());
  expect(screen.getByRole("heading", { name: "Caja y cierres" })).toBeInTheDocument();
});

test("shows a safe error state when treasury is unavailable", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

  render(<TreasuryPanel />);

  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("No se pudo cargar la caja."));
});
