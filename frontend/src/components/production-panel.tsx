"use client";

import { useEffect, useState } from "react";

type Balance = { flock_id: string; live_birds: string };

export function ProductionPanel() {
  const [balances, setBalances] = useState<Balance[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    fetch("/api/v1/production/balances", { credentials: "include" })
      .then(async (response) => {
        if (!response.ok) throw new Error("production unavailable");
        setBalances((await response.json()) as Balance[]);
        setState("ready");
      })
      .catch(() => setState("error"));
  }, []);

  return (
    <section className="technical-card" aria-labelledby="production-title">
      <p className="eyebrow">Entrega 5</p>
      <h2 id="production-title">Producción avícola</h2>
      <p>Lotes activos y saldo de aves vivas reconstruible desde eventos.</p>
      {state === "loading" ? <p role="status">Cargando producción…</p> : null}
      {state === "error" ? <p role="alert">No se pudo cargar producción.</p> : null}
      {state === "ready" && balances.length === 0 ? <p>Sin lotes activos.</p> : null}
      {balances.length > 0 ? (
        <ul>
          {balances.map((balance) => <li key={balance.flock_id}>{balance.flock_id}: {balance.live_birds} aves vivas</li>)}
        </ul>
      ) : null}
    </section>
  );
}
