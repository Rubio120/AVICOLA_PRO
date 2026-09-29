import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { InventoryPanel } from "@/components/inventory-panel";

describe("InventoryPanel", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.includes("egg-configuration-options")
        ? { products: [], warehouses: [], units: [] }
        : url.endsWith("/egg-categories")
          ? []
          : url.includes("/conversions")
            ? []
            : { items: [] };
      return { ok: true, json: async () => body } as Response;
    }));
  });
  afterEach(() => vi.unstubAllGlobals());

  it("shows the empty balance state", async () => {
    render(<InventoryPanel />);
    await waitFor(() => expect(screen.getByText("Sin saldos de inventario.")).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "Inventario" })).toBeInTheDocument();
  });

  it("renders a balance and creates a receipt draft", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/inventory/balances")) {
        return {
          ok: true,
          json: async () => ({ items: [{ id: "balance-1", product_id: "product-1", quantity: "10.0000", inventory_value: "150.00", average_cost: "15.000000" }], total: 1 }),
        } as Response;
      }
      return { ok: true, json: async () => (init?.method === "POST" ? {} : []) } as Response;
    });

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

    await waitFor(() => expect(screen.getByText("No se pudo cargar el inventario.")).toBeInTheDocument());
  });

  it("configures egg categories explicitly without predefined grades or package sizes", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("egg-configuration-options")) {
        return {
          ok: true,
          json: async () => ({
            products: [{ id: "product-egg", sku: "EGG-01", name: "Huevos individuales", base_unit_code: "unit" }],
            warehouses: [{ id: "warehouse-1", code: "WH-01", name: "Depósito principal" }],
            units: [{ code: "pack", name: "Presentación configurable", precision: 0 }],
          }),
        } as Response;
      }
      if (url.endsWith("/egg-categories") && init?.method === "POST") {
        return { ok: true, json: async () => ({}) } as Response;
      }
      if (url.endsWith("/egg-categories")) return { ok: true, json: async () => [] } as Response;
      if (url.includes("/conversions")) return { ok: true, json: async () => [] } as Response;
      return { ok: true, json: async () => ({ items: [], total: 0 }) } as Response;
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<InventoryPanel />);

    expect(await screen.findByRole("heading", { name: "Inventario de huevos" })).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Código de categoría"), "CAT-SYNTHETIC");
    await userEvent.type(screen.getByLabelText("Nombre de categoría"), "Categoría de prueba");
    await userEvent.selectOptions(screen.getByLabelText("Producto base (un huevo por unidad)"), "product-egg");
    await userEvent.selectOptions(screen.getByLabelText("¿Se puede vender?"), "true");
    await userEvent.selectOptions(screen.getByLabelText("Estado de categoría"), "true");
    await userEvent.click(screen.getByRole("button", { name: "Crear categoría" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/inventory/egg-categories",
        expect.objectContaining({ method: "POST" }),
      );
    });
    const createCall = fetchMock.mock.calls.find(([url, init]) => String(url).endsWith("/egg-categories") && init?.method === "POST");
    expect(createCall?.[1]?.body).toContain('"is_saleable":true');
  });

  it("saves a versioned conversion only from an explicit category, unit, and factor", async () => {
    const conversion = { id: "conversion-1", unit_code: "pack", version: 1, units_per_package: 12 };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("egg-configuration-options")) {
        return {
          ok: true,
          json: async () => ({ products: [], warehouses: [], units: [{ code: "pack", name: "Presentación", precision: 0 }] }),
        } as Response;
      }
      if (url.endsWith("/egg-categories")) {
        return { ok: true, json: async () => [{ id: "category-1", code: "CAT-1", name: "Categoría 1", product_id: "product-1", product_sku: "EGG-1", base_unit_code: "unit", is_saleable: true, is_active: true }] } as Response;
      }
      if (url.includes("/conversions") && init?.method === "POST") {
        return { ok: true, json: async () => conversion } as Response;
      }
      if (url.includes("/conversions")) return { ok: true, json: async () => [conversion] } as Response;
      return { ok: true, json: async () => ({ items: [] }) } as Response;
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<InventoryPanel />);
    await screen.findByRole("option", { name: /CAT-1 · Categoría 1/ });
    await userEvent.selectOptions(screen.getByLabelText("Categoría"), "category-1");
    await userEvent.selectOptions(screen.getByLabelText("Unidad de presentación"), "pack");
    await userEvent.type(screen.getByLabelText("Huevos por unidad"), "12");
    await userEvent.click(screen.getByRole("button", { name: "Guardar equivalencia" }));

    expect(await screen.findByText("Nueva versión de equivalencia guardada.")).toBeInTheDocument();
    expect(screen.getByText("pack, versión 1: 12 huevos")).toBeInTheDocument();
    const createCall = fetchMock.mock.calls.find(([url, init]) => String(url).includes("/conversions") && init?.method === "POST");
    expect(createCall?.[1]?.body).toContain('"units_per_package":12');
  });
});
