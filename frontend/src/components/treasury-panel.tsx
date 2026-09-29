"use client";

import { useEffect, useState } from "react";

type Account = { id: string; code: string; name: string; currency_code: string };

export function TreasuryPanel() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      fetch("/api/v1/treasury/accounts", { credentials: "include" })
        .then(async (response) => {
          if (!response.ok) throw new Error("treasury unavailable");
          setAccounts((await response.json()) as Account[]);
          setState("ready");
        })
        .catch(() => setState("error"));
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <section className="technical-card" aria-labelledby="treasury-title">
      <p className="eyebrow">Entrega 8</p>
      <h2 id="treasury-title">Caja y cierres</h2>
      <p>Cuentas, sesiones, movimientos, transferencias y cierres auditables.</p>
      {state === "loading" ? <p role="status">Cargando caja…</p> : null}
      {state === "error" ? <p role="alert">No se pudo cargar la caja.</p> : null}
      {state === "ready" && accounts.length === 0 ? <p>Sin cuentas de caja activas.</p> : null}
      {accounts.length > 0 ? <ul>{accounts.map((account) => <li key={account.id}>{account.code} · {account.name} · {account.currency_code}</li>)}</ul> : null}
    </section>
  );
}
