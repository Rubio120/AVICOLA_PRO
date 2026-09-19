import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import { ProductionPanel } from "@/components/production-panel";

beforeEach(() => vi.restoreAllMocks());

test("shows flock live bird balances", async () => {
  vi.spyOn(global, "fetch").mockResolvedValue({ ok: true, json: async () => [{ flock_id: "flock-1", live_birds: "42.0000" }] } as Response);
  render(<ProductionPanel />);
  await waitFor(() => expect(screen.getByText(/42\.0000 aves vivas/)).toBeInTheDocument());
});

test("shows a safe error state when production is unavailable", async () => {
  vi.spyOn(global, "fetch").mockRejectedValue(new Error("offline"));
  render(<ProductionPanel />);
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("No se pudo cargar producción."));
});
