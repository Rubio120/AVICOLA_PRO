"use client";

import { useEffect, useState } from "react";

type Order = { id: string; customer_id: string; order_date: string; status: string; total: string };

export function SalesPanel() {
  const [orders, setOrders] = useState<Order[]>([]);
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

  return (
    <section className="technical-card" aria-labelledby="sales-title">
      <p className="eyebrow">Entrega 7</p>
      <h2 id="sales-title">Ventas y cuentas por cobrar</h2>
      <p>Pedidos, entregas y comprobantes internos no fiscales ni electrónicos.</p>
      {state === "loading" ? <p role="status">Cargando ventas…</p> : null}
      {state === "error" ? <p role="alert">No se pudo cargar ventas.</p> : null}
      {state === "ready" && orders.length === 0 ? <p>Sin pedidos de venta.</p> : null}
      {orders.length > 0 ? <ul>{orders.map((order) => <li key={order.id}>{order.order_date} · {order.status} · {order.total} PYG</li>)}</ul> : null}
    </section>
  );
}
