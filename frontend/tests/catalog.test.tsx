import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CatalogPanel } from "@/components/catalog-panel";

describe("CatalogPanel", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [] }) }));
  });
  afterEach(() => vi.unstubAllGlobals());

  it("shows the empty state after loading active products", async () => {
    render(<CatalogPanel />);
    await waitFor(() => expect(screen.getByText("Sin productos activos.")).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "Catálogo" })).toBeInTheDocument();
  });

  it("renders a product row and lets an operator create one", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [{ sku: "ALIMENTO-01", name: "Alimento" }], total: 1 }),
    } as Response);
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({}) } as Response);

    render(<CatalogPanel />);
    expect(await screen.findByText("ALIMENTO-01: Alimento")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("SKU"), "NUEVO-01");
    await userEvent.type(screen.getByLabelText("Nombre del producto"), "Nuevo producto");
    await userEvent.click(screen.getByRole("button", { name: "Crear producto" }));

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/catalog/products", expect.objectContaining({ method: "POST" }));
  });

  it("shows a safe error state when the catalog is unavailable", async () => {
    vi.mocked(fetch).mockResolvedValue({ ok: false } as Response);

    render(<CatalogPanel />);

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("No se pudo cargar el catálogo."));
  });

  it("paginates catalog results in both directions", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [], total: 40 }) }));

    render(<CatalogPanel />);
    expect(await screen.findByText("Página 1")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(await screen.findByText("Página 2")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Anterior" }));
    expect(await screen.findByText("Página 1")).toBeInTheDocument();
  });
});
