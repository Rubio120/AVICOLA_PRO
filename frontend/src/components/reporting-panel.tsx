"use client";

import { useEffect, useState } from "react";

type Dashboard = {
  sales_documents: number;
  sales_total: string;
  inventory_value: string;
  live_birds: string;
  accounts_payable: string;
  accounts_receivable: string;
  cash_balance: string;
  confirmed_costs: string;
  poultry_metrics: Record<string, { value: string | null; unit: string; available: boolean; reason: string | null }>;
};

type CommercialRow = {
  channel: string;
  invoices: number;
  credit_notes: number;
  customers_with_documents: number;
  net_revenue: string;
};

export function ReportingPanel() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [commercial, setCommercial] = useState<CommercialRow[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/v1/reports/dashboard", { credentials: "include", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("reports unavailable");
        setDashboard((await response.json()) as Dashboard);
        setState("ready");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setState("error");
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/v1/reports/commercial", { credentials: "include", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("commercial reports unavailable");
        setCommercial((await response.json()) as CommercialRow[]);
      })
      .catch(() => {
        if (!(controller.signal.aborted)) setCommercial([]);
      });
    return () => controller.abort();
  }, []);

  return (
    <section className="technical-card" aria-labelledby="reporting-title">
      <p className="eyebrow">Entrega 10</p>
      <h2 id="reporting-title">Dashboard y reportes</h2>
      <p>Indicadores operativos calculados únicamente con hechos confirmados.</p>
      {state === "loading" ? <p role="status">Cargando indicadores…</p> : null}
      {state === "error" ? <p role="alert">No se pudieron cargar los reportes.</p> : null}
      {state === "ready" && dashboard ? (
        <>
          <dl className="report-grid">
            <div><dt>Ventas emitidas</dt><dd>{dashboard.sales_documents}</dd></div>
            <div><dt>Ventas PYG</dt><dd>{dashboard.sales_total}</dd></div>
            <div><dt>Inventario PYG</dt><dd>{dashboard.inventory_value}</dd></div>
            <div><dt>Aves vivas</dt><dd>{dashboard.live_birds}</dd></div>
            <div><dt>Por pagar PYG</dt><dd>{dashboard.accounts_payable}</dd></div>
            <div><dt>Por cobrar PYG</dt><dd>{dashboard.accounts_receivable}</dd></div>
            <div><dt>Caja PYG</dt><dd>{dashboard.cash_balance}</dd></div>
            <div><dt>Costos confirmados</dt><dd>{dashboard.confirmed_costs}</dd></div>
          </dl>
          <h3>Indicadores de producción y ventas</h3>
          <dl className="report-grid">
            {Object.entries(dashboard.poultry_metrics).map(([key, metric]) => {
              const labels: Record<string, string> = {
                posture: "Huevos por ave promedio",
                feed_per_bird: "Alimento por ave",
                feed_conversion: "Conversión alimenticia",
                feed_cost_per_egg: "Costo confirmado de alimento por huevo vendible",
                average_ticket: "Ticket promedio neto",
                new_customers: "Clientes nuevos",
                stock_coverage: "Cobertura de stock",
              };
              const reasons: Record<string, string> = {
                average_live_birds_missing: "Faltan registros de aves vivas.",
                average_live_birds_is_zero: "No hay aves vivas registradas en el período.",
                feed_data_missing: "No hay consumos de alimento registrados.",
                feed_unit_not_kg_or_unconfirmed: "La unidad o confirmación del alimento no permite calcularlo.",
                feed_cost_unconfirmed: "El consumo no tiene costo de inventario confirmado.",
                egg_count_is_zero: "No hay huevos producidos en el período.",
                saleable_egg_count_is_zero: "No hay huevos vendibles clasificados en el período.",
                issued_invoice_count_is_zero: "No hay facturas emitidas en el período.",
                customer_identity_missing: "Hay facturas sin cliente asociado; no se puede identificar la primera venta.",
                historical_sales_conversion_missing: "Falta conservar la conversión de presentación de cada venta histórica.",
              };
              return (
                <div key={key}>
                  <dt>{labels[key] ?? key}</dt>
                  <dd>{metric.available && metric.value !== null ? `${metric.value} ${metric.unit}` : "No disponible"}</dd>
                  {!metric.available && metric.reason ? <small>{reasons[metric.reason] ?? "Faltan datos confirmados."}</small> : null}
                </div>
              );
            })}
          </dl>
        </>
      ) : null}
      {state === "ready" ? (
        <>
          <h3>Ventas por canal</h3>
          {commercial.length === 0 ? <p>Sin comprobantes emitidos por canal.</p> : null}
          {commercial.length > 0 ? (
            <ul>
              {commercial.map((row) => (
                <li key={row.channel}>
                  {row.channel === "WHOLESALE" ? "Mayorista" : row.channel === "RETAIL" ? "Minorista" : "Histórico sin clasificar"}: {row.net_revenue} PYG netos ({row.invoices} facturas, {row.credit_notes} notas de crédito)
                </li>
              ))}
            </ul>
          ) : null}
          <a href="/api/v1/reports/profitability.xlsx" download="profitability.xlsx">
            Exportar reporte XLSX
          </a>
        </>
      ) : null}
    </section>
  );
}
