import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReportingPanel } from "@/components/reporting-panel";

const metrics = {
  posture: { value: "0.95", unit: "eggs/bird/period", available: true, reason: null },
  feed_per_bird: { value: null, unit: "kg/bird/period", available: false, reason: "feed_data_missing" },
  feed_conversion: { value: "1.2", unit: "kg/dozen", available: true, reason: null },
  feed_cost_per_egg: { value: "25", unit: "currency/egg", available: true, reason: null },
  average_ticket: { value: "500", unit: "currency/invoice", available: true, reason: null },
  new_customers: { value: "1", unit: "customers", available: true, reason: null },
  stock_coverage: { value: null, unit: "days", available: false, reason: "historical_sales_conversion_missing" },
};

const dashboard = {
  sales_documents: 3,
  sales_total: "1000.00",
  inventory_value: "250.00",
  live_birds: "900.0000",
  accounts_payable: "80.00",
  accounts_receivable: "120.00",
  cash_balance: "40.00",
  confirmed_costs: "500.00",
  poultry_metrics: metrics,
};

describe("ReportingPanel", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows confirmed operational and poultry metrics", async () => {
    vi.spyOn(global, "fetch").mockImplementation((input) => {
      const isCommercial = String(input).includes("/commercial");
      return Promise.resolve(
        new Response(
          JSON.stringify(
            isCommercial
              ? [{ channel: "WHOLESALE", invoices: 2, credit_notes: 1, customers_with_documents: 2, net_revenue: "900.00" }]
              : dashboard,
          ),
          { status: 200 },
        ),
      );
    });
    render(<ReportingPanel />);
    await waitFor(() => expect(screen.getByText("Ventas emitidas")).toBeInTheDocument());
    expect(screen.getByText("1000.00")).toBeInTheDocument();
    expect(screen.getByText("Huevos por ave promedio")).toBeInTheDocument();
    expect(screen.getByText("0.95 eggs/bird/period")).toBeInTheDocument();
    expect(screen.getByText("No hay consumos de alimento registrados.")).toBeInTheDocument();
    expect(screen.getByText("Falta conservar la conversión de presentación de cada venta histórica.")).toBeInTheDocument();
    expect(await screen.findByText(/Mayorista: 900.00 PYG netos/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Exportar reporte XLSX" })).toHaveAttribute(
      "href",
      "/api/v1/reports/profitability.xlsx",
    );
  });

  it("shows a safe error state", async () => {
    vi.spyOn(global, "fetch").mockRejectedValue(new Error("offline"));
    render(<ReportingPanel />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("No se pudieron cargar los reportes."));
  });

  it("explains when there are no issued documents", async () => {
    vi.spyOn(global, "fetch").mockImplementation((input) => {
      const isCommercial = String(input).includes("/commercial");
      return Promise.resolve(
        new Response(
          JSON.stringify(
            isCommercial
              ? []
              : {
                  ...dashboard,
                  sales_documents: 0,
                  sales_total: "0.00",
                  poultry_metrics: {
                    ...metrics,
                    average_ticket: {
                      value: null,
                      unit: "currency/invoice",
                      available: false,
                      reason: "issued_invoice_count_is_zero",
                    },
                    new_customers: { value: "0", unit: "customers", available: true, reason: null },
                  },
                },
          ),
          { status: 200 },
        ),
      );
    });
    render(<ReportingPanel />);
    expect(await screen.findByText("Sin comprobantes emitidos por canal.")).toBeInTheDocument();
    expect(screen.getByText("Clientes nuevos")).toBeInTheDocument();
  });
});
