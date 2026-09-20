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
};

export function ReportingPanel() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
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

  return (
    <section className="technical-card" aria-labelledby="reporting-title">
      <p className="eyebrow">Entrega 10</p>
      <h2 id="reporting-title">Dashboard y reportes</h2>
      <p>Indicadores operativos calculados únicamente con hechos confirmados.</p>
      {state === "loading" ? <p role="status">Cargando indicadores…</p> : null}
      {state === "error" ? <p role="alert">No se pudieron cargar los reportes.</p> : null}
      {state === "ready" && dashboard ? (
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
      ) : null}
    </section>
  );
}
