import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReportingPanel } from "@/components/reporting-panel";

const reportPeriod = { date_from: null, date_to: null };

const metrics = {
  posture: { value: "0.95", unit: "eggs/bird/period", available: true, reason: null, period: reportPeriod },
  feed_per_bird: { value: null, unit: "kg/bird/period", available: false, reason: "feed_data_missing", period: reportPeriod },
  feed_conversion: { value: "1.2", unit: "kg/dozen", available: true, reason: null, period: reportPeriod },
  feed_cost_per_egg: { value: "25", unit: "currency/egg", available: true, reason: null, period: reportPeriod },
  average_ticket: { value: "500", unit: "currency/invoice", available: true, reason: null, period: reportPeriod },
  new_customers: { value: "1", unit: "customers", available: true, reason: null, period: reportPeriod },
  stock_coverage: { value: null, unit: "days", available: false, reason: "historical_sales_conversion_missing", period: reportPeriod },
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
  daily_mortality: [{ occurred_on: "2026-01-10", deaths: "3" }],
  active_flock_ages: [{ flock_code: "FLOCK-TEST", days_since_entry: 120, as_of: "2026-01-31" }],
  feed_consumption_by_house: [
    { house_code: "HOUSE-TEST", unit_code: "kg", quantity: "90.0000" },
    { house_code: null, unit_code: "kg", quantity: "5.0000" },
  ],
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
    expect(screen.getByText("2026-01-10: 3 aves")).toBeInTheDocument();
    expect(screen.getByText("HOUSE-TEST: 90.0000 kg consumidos")).toBeInTheDocument();
    expect(screen.getByText("Sin galp�n asignado: 5.0000 kg consumidos")).toBeInTheDocument();
      expect(screen.getByText("FLOCK-TEST: 120 d�as desde el ingreso (al 2026-01-31)")).toBeInTheDocument();
    expect(screen.getByText("No hay consumos de alimento registrados.")).toBeInTheDocument();
    expect(screen.getByText("Falta conservar la conversi�n de presentaci�n de cada venta hist�rica.")).toBeInTheDocument();
    expect(await screen.findByText(/Mayorista: 900.00 PYG netos/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Exportar reporte XLSX" })).toHaveAttribute(
      "href",
      "/api/v1/reports/profitability.xlsx",
    );
  });

  it("applies one date range to the dashboard and filters sales/export by channel", async () => {
    const requestedUrls: string[] = [];
    const filteredDashboard = {
      ...dashboard,
      poultry_metrics: Object.fromEntries(
        Object.entries(metrics).map(([key, metric]) => [
          key,
          {
            ...metric,
            period:
              key === "stock_coverage"
                ? { date_from: "2026-01-02", date_to: "2026-01-31" }
                : { date_from: "2026-01-01", date_to: "2026-01-31" },
          },
        ]),
      ),
    };
    vi.spyOn(global, "fetch").mockImplementation((input) => {
      const url = String(input);
      requestedUrls.push(url);
      return Promise.resolve(
        new Response(
          JSON.stringify(url.includes("/commercial") ? [] : url.includes("/dashboard?") ? filteredDashboard : dashboard),
          { status: 200 },
        ),
      );
    });
    render(<ReportingPanel />);

    fireEvent.change(screen.getByLabelText("Desde"), { target: { value: "2026-01-01" } });
    fireEvent.change(screen.getByLabelText("Hasta"), { target: { value: "2026-01-31" } });
    fireEvent.change(screen.getByLabelText("Canal de ventas"), { target: { value: "WHOLESALE" } });
    fireEvent.click(screen.getByRole("button", { name: "Aplicar filtros" }));

    await waitFor(() => {
      expect(requestedUrls).toContain(
        "/api/v1/reports/dashboard?date_from=2026-01-01&date_to=2026-01-31&channel=WHOLESALE",
      );
      expect(requestedUrls).toContain(
        "/api/v1/reports/commercial?date_from=2026-01-01&date_to=2026-01-31&channel=WHOLESALE",
      );
    });
    expect(screen.getByRole("link", { name: "Exportar reporte XLSX" })).toHaveAttribute(
      "href",
      "/api/v1/reports/profitability.xlsx?date_from=2026-01-01&date_to=2026-01-31&channel=WHOLESALE",
    );
    expect(screen.getAllByText(/Per�odo: 2026-01-01 .* 2026-01-31/)).toHaveLength(6);
    expect(screen.getByText(/Per�odo: 2026-01-02 .* 2026-01-31/)).toBeInTheDocument();
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
                      period: reportPeriod,
                    },
                    new_customers: { value: "0", unit: "customers", available: true, reason: null, period: reportPeriod },
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

