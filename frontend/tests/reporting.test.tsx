import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReportingPanel } from "@/components/reporting-panel";

describe("ReportingPanel", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows confirmed operational indicators", async () => {
    vi.spyOn(global, "fetch").mockImplementation((input) => {
      const isCommercial = String(input).includes("/commercial");
      return Promise.resolve(new Response(JSON.stringify(isCommercial ? [{
        channel: "WHOLESALE",
        invoices: 2,
        credit_notes: 1,
        customers_with_documents: 2,
        net_revenue: "900.00",
      }] : {
        sales_documents: 3,
        sales_total: "1000.00",
        inventory_value: "250.00",
        live_birds: "900.0000",
        accounts_payable: "80.00",
        accounts_receivable: "120.00",
        cash_balance: "40.00",
        confirmed_costs: "500.00",
      }), { status: 200 }));
    });
    render(<ReportingPanel />);
    await waitFor(() => expect(screen.getByText("Ventas emitidas")).toBeInTheDocument());
    expect(screen.getByText("1000.00")).toBeInTheDocument();
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

  it("explains when the commercial period has no issued documents", async () => {
    vi.spyOn(global, "fetch").mockImplementation((input) => {
      const isCommercial = String(input).includes("/commercial");
      return Promise.resolve(
        new Response(
          JSON.stringify(
            isCommercial
              ? []
              : {
                  sales_documents: 0,
                  sales_total: "0.00",
                  inventory_value: "0.00",
                  live_birds: "0",
                  accounts_payable: "0.00",
                  accounts_receivable: "0.00",
                  cash_balance: "0.00",
                  confirmed_costs: "0.00",
                },
          ),
          { status: 200 },
        ),
      );
    });
    render(<ReportingPanel />);
    expect(await screen.findByText("Sin comprobantes emitidos por canal.")).toBeInTheDocument();
    expect(screen.getByText("Clientes nuevos y ticket promedio: pendientes de definición de negocio.")).toBeInTheDocument();
  });
});
