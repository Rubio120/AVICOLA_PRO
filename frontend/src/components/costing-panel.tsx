"use client";

import { useEffect, useState } from "react";

type Run = { id: string; run_date: string; version: number; status: string };

export function CostingPanel() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      fetch("/api/v1/costing/runs", { credentials: "include" })
        .then(async (response) => {
          if (!response.ok) throw new Error("costing unavailable");
          setRuns((await response.json()) as Run[]);
          setState("ready");
        })
        .catch(() => setState("error"));
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <section className="technical-card" aria-labelledby="costing-title">
      <p className="eyebrow">Entrega 9</p>
      <h2 id="costing-title">Costos y rentabilidad</h2>
      <p>Corridas versionadas e inmutables sobre eventos confirmados.</p>
      {state === "loading" ? <p role="status">Cargando costos…</p> : null}
      {state === "error" ? <p role="alert">No se pudieron cargar los costos.</p> : null}
      {state === "ready" && runs.length === 0 ? <p>Sin corridas de costos disponibles.</p> : null}
      {runs.length > 0 ? (
        <ul>
          {runs.map((run) => <li key={run.id}>{run.run_date} · v{run.version} · {run.status}</li>)}
        </ul>
      ) : null}
    </section>
  );
}
