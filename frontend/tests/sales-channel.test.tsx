import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SalesPanel } from "@/components/sales-panel";

describe("SalesPanel sales channels", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((input: RequestInfo | URL) => {
        const url = String(input);
        return Promise.resolve({
          ok: true,
          json: async () =>
            url.endsWith("order-options")
              ? { customers: [], products: [] }
              : [
                  { id: "1", customer_id: "c1", order_date: "2026-09-24", status: "DRAFT", total: "10", channel: "WHOLESALE" },
                  { id: "2", customer_id: "c2", order_date: "2026-09-24", status: "DRAFT", total: "20", channel: "RETAIL" },
                  { id: "3", customer_id: "c3", order_date: "2026-09-24", status: "DRAFT", total: "30", channel: null },
                ],
        });
      }),
    );
  });
  afterEach(() => vi.unstubAllGlobals());

  it("filters channels without guessing legacy records", async () => {
    render(<SalesPanel />);
    await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(3));
    expect(screen.getAllByRole("listitem")[2]).toHaveTextContent("Histórico sin clasificar");

    await userEvent.selectOptions(screen.getByLabelText("Filtrar canal de venta"), "WHOLESALE");
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getByRole("listitem")).toHaveTextContent("Mayorista");
  });

  it("creates a draft order with explicit customer, channel and tax", async () => {
    const customerId = "11111111-1111-4111-8111-111111111111";
    const productId = "22222222-2222-4222-8222-222222222222";
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation((input, init) => {
      const url = String(input);
      if (init?.method === "POST") {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "created-order",
            customer_id: customerId,
            order_date: "2026-09-24",
            status: "DRAFT",
            total: "107.50",
            channel: "RETAIL",
          }),
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: async () =>
          url.endsWith("order-options")
            ? {
                customers: [{ id: customerId, code: "C-01", name: "Cliente de prueba" }],
                products: [{ id: productId, sku: "HUEVO-01", name: "Huevos" }],
              }
            : [],
      } as Response);
    });
    window.sessionStorage.setItem("avicola_csrf_token", "csrf-synthetic");

    render(<SalesPanel />);
    await screen.findByRole("option", { name: /Cliente de prueba/ });
    await userEvent.selectOptions(screen.getByLabelText("Cliente"), customerId);
    await userEvent.selectOptions(screen.getByLabelText("Producto"), productId);
    fireEvent.change(screen.getByLabelText("Fecha del pedido"), { target: { value: "2026-09-24" } });
    await userEvent.selectOptions(screen.getByLabelText("Canal del pedido"), "RETAIL");
    await userEvent.type(screen.getByLabelText("Cantidad"), "10");
    await userEvent.type(screen.getByLabelText("Precio unitario"), "10");
    await userEvent.selectOptions(screen.getByLabelText("Impuesto"), "0.05");
    await userEvent.click(screen.getByRole("button", { name: "Crear pedido borrador" }));

    expect(await screen.findByRole("listitem")).toHaveTextContent("Minorista");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/sales/orders",
      expect.objectContaining({ method: "POST", headers: expect.objectContaining({ "X-CSRF-Token": "csrf-synthetic" }) }),
    );
    const post = fetchMock.mock.calls.find((call) => (call[1] as RequestInit | undefined)?.method === "POST");
    expect(JSON.parse(String((post?.[1] as RequestInit | undefined)?.body))).toMatchObject({
      customer_id: customerId,
      channel: "RETAIL",
      lines: [{ product_id: productId, tax_rate: "0.05" }],
    });
  });

  it("keeps the form available and reports a failed draft order", async () => {
    const customerId = "11111111-1111-4111-8111-111111111111";
    const productId = "22222222-2222-4222-8222-222222222222";
    vi.mocked(fetch).mockImplementation((input, init) => {
      if (init?.method === "POST") return Promise.resolve({ ok: false } as Response);
      return Promise.resolve({
        ok: true,
        json: async () => String(input).endsWith("order-options")
          ? {
              customers: [{ id: customerId, code: "C-01", name: "Cliente de prueba" }],
              products: [{ id: productId, sku: "HUEVO-01", name: "Huevos" }],
            }
          : [],
      } as Response);
    });

    render(<SalesPanel />);
    await screen.findByRole("option", { name: /Cliente de prueba/ });
    await userEvent.selectOptions(screen.getByLabelText("Cliente"), customerId);
    await userEvent.selectOptions(screen.getByLabelText("Producto"), productId);
    fireEvent.change(screen.getByLabelText("Fecha del pedido"), { target: { value: "2026-09-24" } });
    await userEvent.selectOptions(screen.getByLabelText("Canal del pedido"), "WHOLESALE");
    await userEvent.type(screen.getByLabelText("Cantidad"), "1");
    await userEvent.type(screen.getByLabelText("Precio unitario"), "1");
    await userEvent.selectOptions(screen.getByLabelText("Impuesto"), "0");
    await userEvent.click(screen.getByRole("button", { name: "Crear pedido borrador" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo crear el pedido");
    expect(screen.getByRole("button", { name: "Crear pedido borrador" })).toBeEnabled();
  });
});
