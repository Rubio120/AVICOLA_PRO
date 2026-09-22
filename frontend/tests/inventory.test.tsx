import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { InventoryPanel } from "@/components/inventory-panel";

describe("InventoryPanel", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [] }) }));
  });
  afterEach(() => vi.unstubAllGlobals());

  it("shows the empty balance state", async () => {
    render(<InventoryPanel />);
    await waitFor(() => expect(screen.getByText("Sin saldos de inventario.")).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "Inventario" })).toBeInTheDocument();
  });

  it("renders a balance and creates a receipt draft", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [{ id: "balance-1", product_id: "product-1", quantity: "10.0000", inventory_value: "150.00", average_cost: "15.000000" }], total: 1 }),
    } as Response);
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({}) } as Response);

    render(<InventoryPanel />);
    expect(await screen.findByText(/10\.0000 unidades · 150\.00 PYG/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Producto"), "product-1");
    await userEvent.type(screen.getByLabelText("Cantidad"), "10");
    await userEvent.type(screen.getByLabelText("Costo unitario"), "15");
    await userEvent.click(screen.getByRole("button", { name: "Registrar entrada" }));

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/inventory/documents", expect.objectContaining({ method: "POST" }));
  });

  it("shows a safe error state when inventory is unavailable", async () => {
    vi.mocked(fetch).mockResolvedValue({ ok: false } as Response);

    render(<InventoryPanel />);

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("No se pudo cargar el inventario."));
  });
});
