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
  daily_mortality: { occurred_on: string; deaths: string }[];
  active_flock_ages: { flock_code: string; days_since_entry: number; as_of: string }[];
  feed_consumption_by_house: { house_code: string | null; unit_code: string; quantity: string }[];
  poultry_metrics: Record<
    string,
    {
      value: string | null;
      unit: string;
      available: boolean;
      reason: string | null;
      period: { date_from: string | null; date_to: string | null };
    }
  >;
};

type ReportFilters = { dateFrom: string; dateTo: string; channel: string };

const emptyFilters: ReportFilters = { dateFrom: "", dateTo: "", channel: "" };

function queryString(filters: ReportFilters, includeChannel: boolean): string {
  const query = new URLSearchParams();
  if (filters.dateFrom) query.set("date_from", filters.dateFrom);
  if (filters.dateTo) query.set("date_to", filters.dateTo);
  if (includeChannel && filters.channel) query.set("channel", filters.channel);
  const value = query.toString();
  return value ? `?${value}` : "";
}

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
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [channel, setChannel] = useState("");
  const [filters, setFilters] = useState(emptyFilters);
  const [filterError, setFilterError] = useState<string | null>(null);
  const dashboardUrl = `/api/v1/reports/dashboard${queryString(filters, true)}`;
  const commercialUrl = `/api/v1/reports/commercial${queryString(filters, true)}`;
  const exportUrl = `/api/v1/reports/profitability.xlsx${queryString(filters, true)}`;

  useEffect(() => {
    const controller = new AbortController();
    fetch(dashboardUrl, { credentials: "include", signal: controller.signal })
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
  }, [dashboardUrl]);

  useEffect(() => {
    const controller = new AbortController();
    fetch(commercialUrl, { credentials: "include", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("commercial reports unavailable");
        setCommercial((await response.json()) as CommercialRow[]);
      })
      .catch(() => {
        if (!(controller.signal.aborted)) setCommercial([]);
      });
    return () => controller.abort();
  }, [commercialUrl]);

  function applyFilters(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (dateFrom && dateTo && dateFrom > dateTo) {
      setFilterError("La fecha inicial no puede ser posterior a la fecha final.");
      return;
    }
    setFilterError(null);
    setFilters({ dateFrom, dateTo, channel });
  }

  return (
    <section className="technical-card" aria-labelledby="reporting-title">
      <p className="eyebrow">Entrega 10</p>
      <h2 id="reporting-title">Dashboard y reportes</h2>
      <form className="report-filters" onSubmit={applyFilters}>
        <label>
          Desde
          <input aria-label="Desde" type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
        </label>
        <label>
          Hasta
          <input aria-label="Hasta" type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
        </label>
        <label>
          Canal de ventas
          <select aria-label="Canal de ventas" value={channel} onChange={(event) => setChannel(event.target.value)}>
            <option value="">Todos</option>
            <option value="WHOLESALE">Mayorista</option>
            <option value="RETAIL">Minorista</option>
          </select>
        </label>
        <button type="submit">Aplicar filtros</button>
        {filterError ? <p role="alert">{filterError}</p> : null}
      </form>
      <p>
        Las ventas, clientes y cobertura respetan el canal seleccionado; los indicadores productivos usan todas las
        granjas y galpones.
      </p>
      <p>Inventario, aves, cuentas, caja y costos muestran saldos actuales, no saldos hist�ricos del rango seleccionado.</p>
      {state === "loading" ? <p role="status">Cargando indicadores.</p> : null}
      {state === "error" ? <p role="alert">No se pudieron cargar los reportes.</p> : null}
      {state === "ready" && dashboard ? (
        <>
          <dl className="report-grid">
            <div><dt>Ventas emitidas</dt><dd>{dashboard.sales_documents}</dd><small>Seg�n fecha y canal.</small></div>
            <div><dt>Ventas PYG</dt><dd>{dashboard.sales_total}</dd><small>Seg�n fecha y canal.</small></div>
            <div><dt>Inventario PYG</dt><dd>{dashboard.inventory_value}</dd></div>
            <div><dt>Aves vivas</dt><dd>{dashboard.live_birds}</dd></div>
            <div><dt>Por pagar PYG</dt><dd>{dashboard.accounts_payable}</dd></div>
            <div><dt>Por cobrar PYG</dt><dd>{dashboard.accounts_receivable}</dd></div>
            <div><dt>Caja PYG</dt><dd>{dashboard.cash_balance}</dd></div>
            <div><dt>Costos confirmados</dt><dd>{dashboard.confirmed_costs}</dd></div>
          </dl>
          <h3>Indicadores de producci�n y ventas</h3>
          <dl className="report-grid">
            {Object.entries(dashboard.poultry_metrics).map(([key, metric]) => {
              const labels: Record<string, string> = {
                posture: "Huevos por ave promedio",
                feed_per_bird: "Alimento por ave",
                feed_conversion: "Conversi�n alimenticia",
                feed_cost_per_egg: "Costo confirmado de alimento por huevo vendible",
                average_ticket: "Ticket promedio neto",
                new_customers: "Clientes nuevos",
                stock_coverage: "Cobertura de stock",
              };
              const reasons: Record<string, string> = {
                average_live_birds_missing: "Faltan registros de aves vivas.",
                average_live_birds_is_zero: "No hay aves vivas registradas en el per�odo.",
                feed_data_missing: "No hay consumos de alimento registrados.",
                feed_unit_not_kg_or_unconfirmed: "La unidad o confirmaci�n del alimento no permite calcularlo.",
                feed_cost_unconfirmed: "El consumo no tiene costo de inventario confirmado.",
                egg_count_is_zero: "No hay huevos producidos en el per�odo.",
                saleable_egg_count_is_zero: "No hay huevos vendibles clasificados en el per�odo.",
                issued_invoice_count_is_zero: "No hay facturas emitidas en el per�odo.",
                customer_identity_missing: "Hay facturas sin cliente asociado; no se puede identificar la primera venta.",
                historical_sales_conversion_missing: "Falta conservar la conversi�n de presentaci�n de cada venta hist�rica.",
              };
              return (
                <div key={key}>
                  <dt>{labels[key] ?? key}</dt>
                  <dd>{metric.available && metric.value !== null ? `${metric.value} ${metric.unit}` : "No disponible"}</dd>
                  <small>
                    Per�odo: {metric.period.date_from ?? "sin inicio"} - {metric.period.date_to ?? "sin fin"}
                  </small>
                  {!metric.available && metric.reason ? <small>{reasons[metric.reason] ?? "Faltan datos confirmados."}</small> : null}
                </div>
              );
            })}
          </dl>
          <h3>Consumo confirmado de alimento por galp�n</h3>
          {dashboard.feed_consumption_by_house.length === 0 ? <p>Sin consumos confirmados en el per�odo.</p> : null}
          {dashboard.feed_consumption_by_house.length > 0 ? (
            <ul>
              {dashboard.feed_consumption_by_house.map((item) => (
                <li key={`${item.house_code ?? "unassigned"}-${item.unit_code}`}>
                  {item.house_code ?? "Sin galp�n asignado"}: {item.quantity} {item.unit_code} consumidos
                </li>
              ))}
            </ul>
          ) : null}
          <h3>Mortalidad diaria registrada</h3>
          {dashboard.daily_mortality.length === 0 ? <p>Sin registros de mortalidad en el per�odo.</p> : null}
          {dashboard.daily_mortality.length > 0 ? (
            <ul>
              {dashboard.daily_mortality.map((day) => (
                <li key={day.occurred_on}>{day.occurred_on}: {day.deaths} aves</li>
              ))}
            </ul>
          ) : null}
          <h3>D�as desde el ingreso de los lotes activos</h3>
          {dashboard.active_flock_ages.length === 0 ? <p>Sin lotes activos con fecha de ingreso registrada.</p> : null}
          {dashboard.active_flock_ages.length > 0 ? (
            <ul>
              {dashboard.active_flock_ages.map((flock) => (
                <li key={flock.flock_code}>{flock.flock_code}: {flock.days_since_entry} d�as desde el ingreso (al {flock.as_of})</li>
              ))}
            </ul>
          ) : null}
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
                  {row.channel === "WHOLESALE" ? "Mayorista" : row.channel === "RETAIL" ? "Minorista" : "Hist�rico sin clasificar"}: {row.net_revenue} PYG netos ({row.invoices} facturas, {row.credit_notes} notas de cr�dito)
                </li>
              ))}
            </ul>
          ) : null}
          <a href={exportUrl} download="profitability.xlsx">
            Exportar reporte XLSX
          </a>
          <small>
            El reporte incluye ventas por canal; costo total por huevo y margen no se calculan hasta aprobar la regla de
            asignaci�n de costos y devoluciones.
          </small>
        </>
      ) : null}
    </section>
  );
}

