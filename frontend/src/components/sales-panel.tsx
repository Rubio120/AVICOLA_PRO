"use client";

import { useEffect, useState } from "react";

type Order = {
  id: string;
  customer_id: string;
  order_date: string;
  status: string;
  total: string;
  channel: "WHOLESALE" | "RETAIL" | null;
};

export function SalesPanel() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [channel, setChannel] = useState<"ALL" | "WHOLESALE" | "RETAIL">("ALL");
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      fetch("/api/v1/sales/orders", { credentials: "include" })
        .then(async (response) => {
          if (!response.ok) throw new Error("sales unavailable");
          setOrders((await response.json()) as Order[]);
          setState("ready");
        })
        .catch(() => setState("error"));
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const visibleOrders = orders.filter((order) => channel === "ALL" || order.channel === channel);

  return (
    <section className="technical-card" aria-labelledby="sales-title">
      <p className="eyebrow">Entrega 7</p>
      <h2 id="sales-title">Ventas y cuentas por cobrar</h2>
      <p>Pedidos, entregas y comprobantes internos no fiscales ni electrónicos.</p>
      {state === "loading" ? <p role="status">Cargando ventas.</p> : null}
      {state === "error" ? <p role="alert">No se pudo cargar ventas.</p> : null}
      {state === "ready" ? (
        <label>
          Canal de venta
          <select
            aria-label="Filtrar canal de venta"
            value={channel}
            onChange={(event) => setChannel(event.target.value as typeof channel)}
          >
            <option value="ALL">Todos</option>
            <option value="WHOLESALE">Mayorista</option>
            <option value="RETAIL">Minorista</option>
          </select>
        </label>
      ) : null}
      {state === "ready" && visibleOrders.length === 0 ? <p>Sin pedidos de venta para este canal.</p> : null}
      {visibleOrders.length > 0 ? (
        <ul>
          {visibleOrders.map((order) => (
            <li key={order.id}>
              {order.order_date} · {order.status} · {order.total} PYG · {channelLabel(order.channel)}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function channelLabel(channel: Order["channel"]): string {
  if (channel === "WHOLESALE") return "Mayorista";
  if (channel === "RETAIL") return "Minorista";
  return "Histórico sin clasificar";
}
