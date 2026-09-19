"use client";

import { useEffect, useState } from "react";

type Order = { id: string; supplier_id: string; order_date: string; status: string; total: string };

export function PurchasingPanel() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      fetch("/api/v1/purchasing/orders", { credentials: "include" })
        .then(async (response) => {
          if (!response.ok) throw new Error("purchasing unavailable");
          setOrders((await response.json()) as Order[]);
          setState("ready");
        })
        .catch(() => setState("error"));
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <section className="technical-card" aria-labelledby="purchasing-title">
      <p className="eyebrow">Entrega 6</p>
      <h2 id="purchasing-title">Compras y cuentas por pagar</h2>
      <p>Órdenes aprobadas, recepciones parciales y obligaciones de proveedores.</p>
      {state === "loading" ? <p role="status">Cargando compras…</p> : null}
      {state === "error" ? <p role="alert">No se pudo cargar compras.</p> : null}
      {state === "ready" && orders.length === 0 ? <p>Sin órdenes de compra.</p> : null}
      {orders.length > 0 ? (
        <ul>
          {orders.map((order) => <li key={order.id}>{order.order_date} · {order.status} · {order.total} PYG</li>)}
        </ul>
      ) : null}
    </section>
  );
}
