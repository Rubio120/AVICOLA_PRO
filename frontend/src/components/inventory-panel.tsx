"use client";

import { useEffect, useState } from "react";

type Balance = { id: string; product_id: string; quantity: string; inventory_value: string; average_cost: string };
type BalancePage = { items: Balance[]; total?: number };

export function InventoryPanel() {
  const [balances, setBalances] = useState<Balance[]>([]);
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [unitCost, setUnitCost] = useState("");
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  function loadBalances() {
    setState("loading");
    fetch("/api/v1/inventory/balances?offset=0&limit=50", { credentials: "include" })
      .then(async (response) => {
        if (!response.ok) throw new Error("inventory unavailable");
        const body = (await response.json()) as BalancePage;
        setBalances(body.items);
        setState("ready");
      })
      .catch(() => setState("error"));
  }

  useEffect(() => {
    const timer = window.setTimeout(loadBalances, 0);
    return () => window.clearTimeout(timer);
  }, []);

  async function createReceipt(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const response = await fetch("/api/v1/inventory/documents", {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": window.sessionStorage.getItem("avicola_csrf_token") ?? "",
      },
      body: JSON.stringify({
        document_type: "RECEIPT",
        effective_date: new Date().toISOString().slice(0, 10),
        reason: "Entrada registrada desde inventario",
        lines: [{ ordinal: 1, product_id: productId, quantity, unit_cost: unitCost, direction: "IN" }],
      }),
    });
    if (response.ok) {
      setProductId("");
      setQuantity("");
      setUnitCost("");
      loadBalances();
    } else {
      setState("error");
    }
  }

  return (
    <section className="technical-card" aria-labelledby="inventory-title">
      <p className="eyebrow">Entrega 4</p>
      <h2 id="inventory-title">Inventario</h2>
      <p>Saldos por depósito y producto, con valoración por promedio ponderado móvil.</p>
      <form onSubmit={createReceipt}>
        <label htmlFor="inventory-product">Producto</label>
        <input id="inventory-product" value={productId} onChange={(event) => setProductId(event.target.value)} required />
        <label htmlFor="inventory-quantity">Cantidad</label>
        <input id="inventory-quantity" type="number" min="0.0001" step="0.0001" value={quantity} onChange={(event) => setQuantity(event.target.value)} required />
        <label htmlFor="inventory-cost">Costo unitario</label>
        <input id="inventory-cost" type="number" min="0" step="0.000001" value={unitCost} onChange={(event) => setUnitCost(event.target.value)} required />
        <button type="submit">Registrar entrada</button>
      </form>
      {state === "loading" ? <p role="status">Cargando inventario…</p> : null}
      {state === "error" ? <p role="alert">No se pudo cargar el inventario.</p> : null}
      {state === "ready" && balances.length === 0 ? <p>Sin saldos de inventario.</p> : null}
      {balances.length > 0 ? (
        <ul>
          {balances.map((balance) => (
            <li key={balance.id}>{balance.quantity} unidades · {balance.inventory_value} PYG · promedio {balance.average_cost}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
