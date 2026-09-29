import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CostingPanel } from "@/components/costing-panel";

describe("CostingPanel", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows versioned runs from the same-origin API", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify([{ id: "run-1", run_date: "2026-09-20", version: 1, status: "CLOSED" }]), { status: 200 }),
    );
    render(<CostingPanel />);
    await waitFor(() => expect(screen.getByText("2026-09-20 · v1 · CLOSED")).toBeInTheDocument());
  });

  it("shows a safe error state", async () => {
    vi.spyOn(global, "fetch").mockRejectedValue(new Error("offline"));
    render(<CostingPanel />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("No se pudieron cargar los costos."));
  });
});
