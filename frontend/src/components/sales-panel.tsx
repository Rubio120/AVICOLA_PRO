"use client";

import { useEffect, useState, type FormEvent } from "react";

type Channel = "WHOLESALE" | "RETAIL";
type Order = {
  id: string;
  customer_id: string;
  order_date: string;
  status: string;
  total: string;
  channel: Channel | null;
};
type CustomerOption = { id: string; code: string; name: string };
type ProductOption = { id: string; sku: string; name: string };
type OrderOptions = { customers: CustomerOption[]; products: ProductOption[] };

export function SalesPanel() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [options, setOptions] = useState<OrderOptions>({ customers: [], products: [] });
  const [channel, setChannel] = useState<"ALL" | Channel>("ALL");
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetch("/api/v1/sales/orders", { credentials: "include", signal: controller.signal }),
      fetch("/api/v1/sales/order-options", { credentials: "include", signal: controller.signal }),
    ])
      .then(async ([ordersResponse, optionsResponse]) => {
        if (!ordersResponse.ok || !optionsResponse.ok) throw new Error("sales unavailable");
        setOrders((await ordersResponse.json()) as Order[]);
        setOptions((await optionsResponse.json()) as OrderOptions);
        setState("ready");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setState("error");
      });
    return () => controller.abort();
  }, []);

  async function createOrder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setSubmitting(true);
    setFormError(false);
    try {
      const response = await fetch("/api/v1/sales/orders", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": window.sessionStorage.getItem("avicola_csrf_token") ?? "",
        },
        body: JSON.stringify({
          customer_id: form.get("customer_id"),
          order_date: form.get("order_date"),
          channel: form.get("order_channel"),
          lines: [
            {
              product_id: form.get("product_id"),
              quantity: form.get("quantity"),
              unit_price: form.get("unit_price"),
              discount_rate: "0",
              tax_rate: form.get("tax_rate"),
            },
          ],
        }),
      });
      if (!response.ok) throw new Error("order creation failed");
      const order = (await response.json()) as Order;
      setOrders((current) => [order, ...current]);
      formElement.reset();
    } catch {
      setFormError(true);
    } finally {
      setSubmitting(false);
    }
  }

  const visibleOrders = orders.filter((order) => channel === "ALL" || order.channel === channel);

  return (
    <section className="technical-card" aria-labelledby="sales-title">
      <p className="eyebrow">Entrega 7</p>
      <h2 id="sales-title">Ventas y cuentas por cobrar</h2>
      <p>Pedidos, entregas y comprobantes internos no fiscales ni electrónicos.</p>
      {state === "loading" ? <p role="status">Cargando ventas.</p> : null}
      {state === "error" ? <p role="alert">No se pudieron cargar o guardar las ventas.</p> : null}
      {formError ? <p role="alert">No se pudo crear el pedido. Revisa los datos e inténtalo de nuevo.</p> : null}
      {state === "ready" ? (
        <form onSubmit={createOrder}>
          <h3>Crear pedido borrador</h3>
          <label>
            Cliente
            <select name="customer_id" aria-label="Cliente" required defaultValue="">
              <option value="" disabled>Seleccionar cliente</option>
              {options.customers.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}
            </select>
          </label>
          <label>
            Producto
            <select name="product_id" aria-label="Producto" required defaultValue="">
              <option value="" disabled>Seleccionar producto</option>
              {options.products.map((item) => <option key={item.id} value={item.id}>{item.sku} · {item.name}</option>)}
            </select>
          </label>
          <label>Fecha del pedido<input name="order_date" type="date" required /></label>
          <label>
            Canal del pedido
            <select name="order_channel" aria-label="Canal del pedido" required defaultValue="">
              <option value="" disabled>Seleccionar canal</option>
              <option value="WHOLESALE">Mayorista</option>
              <option value="RETAIL">Minorista</option>
            </select>
          </label>
          <label>Cantidad<input name="quantity" type="number" min="0.0001" step="0.0001" required /></label>
          <label>Precio unitario<input name="unit_price" type="number" min="0" step="0.000001" required /></label>
          <label>
            Impuesto
            <select name="tax_rate" aria-label="Impuesto" required defaultValue="">
              <option value="" disabled>Seleccionar impuesto</option>
              <option value="0">Exento</option>
              <option value="0.05">IVA 5%</option>
              <option value="0.10">IVA 10%</option>
            </select>
          </label>
          <button type="submit" disabled={submitting || !options.customers.length || !options.products.length}>
            {submitting ? "Guardando pedido…" : "Crear pedido borrador"}
          </button>
          {!options.customers.length || !options.products.length ? <p>Se necesitan clientes y productos activos para crear pedidos.</p> : null}
        </form>
      ) : null}
      {state === "ready" ? (
        <label>
          Filtrar pedidos por canal
          <select aria-label="Filtrar canal de venta" value={channel} onChange={(event) => setChannel(event.target.value as typeof channel)}>
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
