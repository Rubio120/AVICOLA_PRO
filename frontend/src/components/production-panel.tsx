"use client";

import { useEffect, useState } from "react";

type Balance = { flock_id: string; live_birds: string };
type EggOption = { flock_id: string; flock_code: string; house_id: string; house_code: string };
type EggRecord = { id: string; flock_id: string; house_id: string; occurred_on: string; egg_count: number };
type EggCategoryOption = { id: string; code: string; name: string; is_active: boolean };
type EggWarehouseOption = { id: string; code: string; name: string };

async function fetchEggRecords(recordDate: string, signal?: AbortSignal): Promise<EggRecord[]> {
  const query = new URLSearchParams({ date_from: recordDate, date_to: recordDate, limit: "100", offset: "0" });
  const response = await fetch(`/api/v1/production/egg-records?${query}`, { credentials: "include", signal });
  if (!response.ok) throw new Error("egg production records unavailable");
  return (await response.json()) as EggRecord[];
}

async function fetchUnclassifiedEggRecords(recordDate: string, signal?: AbortSignal): Promise<EggRecord[]> {
  const query = new URLSearchParams({ date_from: recordDate, date_to: recordDate, limit: "100", offset: "0" });
  const response = await fetch(`/api/v1/production/egg-records/unclassified?${query}`, {
    credentials: "include",
    signal,
  });
  if (!response.ok) throw new Error("unclassified egg production unavailable");
  return (await response.json()) as EggRecord[];
}

export function ProductionPanel() {
  const [balances, setBalances] = useState<Balance[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [occurredOn, setOccurredOn] = useState(new Date().toISOString().slice(0, 10));
  const [optionsResult, setOptionsResult] = useState<{
    forDate: string;
    state: "ready" | "error";
    items: EggOption[];
  } | null>(null);
  const optionsAreCurrent = optionsResult?.forDate === occurredOn;
  const eggOptions = optionsAreCurrent ? optionsResult.items : [];
  const [flockId, setFlockId] = useState("");
  const [houseId, setHouseId] = useState("");
  const [eggCount, setEggCount] = useState("");
  const [eggState, setEggState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [eggIdempotencyKey, setEggIdempotencyKey] = useState<string | null>(null);
  const [recordsResult, setRecordsResult] = useState<{
    forDate: string;
    state: "ready" | "error";
    items: EggRecord[];
  } | null>(null);
  const recordsAreCurrent = recordsResult?.forDate === occurredOn;
  const eggRecords = recordsAreCurrent ? recordsResult.items : [];
  const [unclassifiedResult, setUnclassifiedResult] = useState<{
    forDate: string;
    state: "ready" | "error";
    items: EggRecord[];
  } | null>(null);
  const unclassifiedAreCurrent = unclassifiedResult?.forDate === occurredOn;
  const unclassifiedRecords = unclassifiedAreCurrent ? unclassifiedResult.items : [];
  const [eggCategories, setEggCategories] = useState<EggCategoryOption[]>([]);
  const [eggWarehouses, setEggWarehouses] = useState<EggWarehouseOption[]>([]);
  const [classificationWarehouse, setClassificationWarehouse] = useState<Record<string, string>>({});
  const [classificationInputs, setClassificationInputs] = useState<Record<string, Record<string, string>>>({});
  const [classificationKeys, setClassificationKeys] = useState<Record<string, string>>({});
  const [classificationError, setClassificationError] = useState("");
  const [classificationState, setClassificationState] = useState<"idle" | "saving" | "saved">("idle");

  useEffect(() => {
    fetch("/api/v1/production/balances", { credentials: "include" })
      .then(async (response) => {
        if (!response.ok) throw new Error("production unavailable");
        setBalances((await response.json()) as Balance[]);
        setState("ready");
      })
      .catch(() => setState("error"));
  }, []);

  useEffect(() => {
    const query = new URLSearchParams({ on_date: occurredOn });
    const controller = new AbortController();
    fetch(`/api/v1/production/egg-record-options?${query}`, { credentials: "include", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("egg production options unavailable");
        setOptionsResult({ forDate: occurredOn, state: "ready", items: (await response.json()) as EggOption[] });
      })
      .catch(() => {
        if (!controller.signal.aborted) setOptionsResult({ forDate: occurredOn, state: "error", items: [] });
      });
    void fetchEggRecords(occurredOn, controller.signal)
      .then((items) => {
        if (!controller.signal.aborted) setRecordsResult({ forDate: occurredOn, state: "ready", items });
      })
      .catch(() => {
        if (!controller.signal.aborted) setRecordsResult({ forDate: occurredOn, state: "error", items: [] });
      });
    void fetchUnclassifiedEggRecords(occurredOn, controller.signal)
      .then(async (items) => {
        if (controller.signal.aborted) return;
        setUnclassifiedResult({ forDate: occurredOn, state: "ready", items });
        if (items.length === 0) {
          setEggCategories([]);
          setEggWarehouses([]);
          return;
        }
        const [categoryResponse, optionsResponse] = await Promise.all([
          fetch("/api/v1/inventory/egg-categories", { credentials: "include", signal: controller.signal }),
          fetch("/api/v1/inventory/egg-configuration-options", { credentials: "include", signal: controller.signal }),
        ]);
        if (!categoryResponse.ok || !optionsResponse.ok) throw new Error("egg classification options unavailable");
        const categories = (await categoryResponse.json()) as EggCategoryOption[];
        const options = (await optionsResponse.json()) as { warehouses?: EggWarehouseOption[] };
        if (!controller.signal.aborted) {
          setEggCategories(categories.filter((category) => category.is_active));
          setEggWarehouses(options.warehouses ?? []);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setUnclassifiedResult({ forDate: occurredOn, state: "error", items: [] });
      });
    return () => controller.abort();
  }, [occurredOn]);

  async function refreshEggRecords() {
    const [records, unclassified] = await Promise.all([
      fetchEggRecords(occurredOn).catch(() => null),
      fetchUnclassifiedEggRecords(occurredOn).catch(() => null),
    ]);
    if (records) setRecordsResult({ forDate: occurredOn, state: "ready", items: records });
    if (unclassified) setUnclassifiedResult({ forDate: occurredOn, state: "ready", items: unclassified });
  }

  async function recordEggs(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const count = Number(eggCount);
    if (!Number.isSafeInteger(count) || count < 0) {
      setEggState("error");
      return;
    }
    const idempotencyKey = eggIdempotencyKey ?? crypto.randomUUID();
    setEggIdempotencyKey(idempotencyKey);
    setEggState("saving");
    try {
      const response = await fetch("/api/v1/production/egg-records", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": window.sessionStorage.getItem("avicola_csrf_token") ?? "",
        },
        body: JSON.stringify({
          flock_id: flockId,
          house_id: houseId,
          occurred_on: occurredOn,
          egg_count: count,
          idempotency_key: idempotencyKey,
        }),
      });
      if (!response.ok) throw new Error("egg production unavailable");
      setEggCount("");
      setEggIdempotencyKey(null);
      setEggState("saved");
      void refreshEggRecords();
    } catch {
      setEggState("error");
    }
  }

  async function classifyEggs(event: React.FormEvent<HTMLFormElement>, record: EggRecord) {
    event.preventDefault();
    setClassificationError("");
    const values = eggCategories
      .map((category) => ({ category_id: category.id, raw: classificationInputs[record.id]?.[category.id] ?? "" }))
      .filter((item) => item.raw !== "")
      .map((item) => ({ category_id: item.category_id, egg_count: Number(item.raw) }));
    if (values.some((item) => !Number.isSafeInteger(item.egg_count) || item.egg_count < 0)) {
      setClassificationError("Las cantidades por categoría deben ser huevos enteros no negativos.");
      return;
    }
    if (values.reduce((total, item) => total + item.egg_count, 0) !== record.egg_count) {
      setClassificationError("La suma por categorías debe coincidir con el total diario.");
      return;
    }
    const warehouseId = classificationWarehouse[record.id];
    if (!warehouseId) {
      setClassificationError("Selecciona el depósito que recibirá los huevos.");
      return;
    }
    const idempotencyKey = classificationKeys[record.id] ?? crypto.randomUUID();
    setClassificationKeys((current) => ({ ...current, [record.id]: idempotencyKey }));
    setClassificationState("saving");
    try {
      const response = await fetch(`/api/v1/production/egg-records/${record.id}/classifications`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": window.sessionStorage.getItem("avicola_csrf_token") ?? "",
        },
        body: JSON.stringify({ warehouse_id: warehouseId, allocations: values, idempotency_key: idempotencyKey }),
      });
      if (!response.ok) throw new Error("egg classification failed");
      setClassificationState("saved");
      setClassificationKeys((current) => {
        const next = { ...current };
        delete next[record.id];
        return next;
      });
      await refreshEggRecords();
    } catch {
      setClassificationState("idle");
      setClassificationError("No se pudo guardar la clasificación de huevos.");
    }
  }


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
      <h3>Producción diaria de huevos</h3>
      <p>Registra unidades enteras por lote, galpón y fecha.</p>
      <form onSubmit={recordEggs}>
        <label htmlFor="egg-flock-id">Lote</label>
        <select
          id="egg-flock-id"
          value={flockId}
          disabled={eggState === "saving"}
          onChange={(event) => {
            setFlockId(event.target.value);
            setHouseId("");
            setEggIdempotencyKey(null);
          }}
          required
        >
          <option value="">Selecciona un lote</option>
          {[...new Map(eggOptions.map((option) => [option.flock_id, option.flock_code]))].map(([id, code]) => (
            <option key={id} value={id}>{code}</option>
          ))}
        </select>
        <label htmlFor="egg-house-id">Galpón</label>
        <select
          id="egg-house-id"
          value={houseId}
          disabled={eggState === "saving"}
          onChange={(event) => {
            setHouseId(event.target.value);
            setEggIdempotencyKey(null);
          }}
          required
        >
          <option value="">Selecciona un galpón</option>
          {eggOptions.filter((option) => option.flock_id === flockId).map((option) => (
            <option key={option.house_id} value={option.house_id}>{option.house_code}</option>
          ))}
        </select>
        <label htmlFor="egg-record-date">Fecha</label>
        <input
          id="egg-record-date"
          type="date"
          value={occurredOn}
          disabled={eggState === "saving"}
          onChange={(event) => {
            setOccurredOn(event.target.value);
            setEggIdempotencyKey(null);
          }}
          required
        />
        <label htmlFor="egg-count">Cantidad de huevos</label>
        <input
          id="egg-count"
          type="number"
          min="0"
          max={Number.MAX_SAFE_INTEGER}
          step="1"
          value={eggCount}
          disabled={eggState === "saving"}
          onChange={(event) => {
            setEggCount(event.target.value);
            setEggIdempotencyKey(null);
          }}
          required
        />
        <button
          type="submit"
          disabled={eggState === "saving" || !optionsAreCurrent || optionsResult.state !== "ready" || eggOptions.length === 0}
        >
          {eggState === "saving" ? "Guardando…" : "Registrar huevos"}
        </button>
      </form>
      {!optionsAreCurrent ? <p role="status">Cargando lotes y galpones.</p> : null}
      {optionsAreCurrent && optionsResult.state === "error" ? <p role="alert">No se pudieron cargar lotes y galpones.</p> : null}
      {optionsAreCurrent && optionsResult.state === "ready" && eggOptions.length === 0 ? (
        <p>No hay lotes y galpones activos para esa fecha.</p>
      ) : null}
      {eggState === "saved" ? <p role="status">Producción de huevos registrada.</p> : null}
      {eggState === "error" ? <p role="alert">No se pudo registrar la producción de huevos.</p> : null}
      <h3>Registros para la fecha</h3>
      {!recordsAreCurrent ? <p role="status">Cargando registros de huevos.</p> : null}
      {recordsAreCurrent && recordsResult.state === "error" ? (
        <p role="alert">No se pudieron cargar los registros de huevos.</p>
      ) : null}
      {recordsAreCurrent && recordsResult.state === "ready" && eggRecords.length === 0 ? (
        <p>Sin registros para esta fecha.</p>
      ) : null}
      {eggRecords.length > 0 ? (
        <ul>
          {eggRecords.map((record) => (
            <li key={record.id}>{record.occurred_on}: {record.egg_count} huevos (lote {record.flock_id})</li>
          ))}
        </ul>
      ) : null}
      <h3>Clasificación de producción pendiente</h3>
      {!unclassifiedAreCurrent ? <p role="status">Cargando clasificaciones pendientes.</p> : null}
      {unclassifiedAreCurrent && unclassifiedResult.state === "error" ? (
        <p role="alert">No se pudieron cargar las clasificaciones pendientes.</p>
      ) : null}
      {unclassifiedAreCurrent && unclassifiedResult.state === "ready" && unclassifiedRecords.length === 0 ? (
        <p>Sin producción pendiente de clasificar.</p>
      ) : null}
      {unclassifiedRecords.map((record) => (
        <form key={record.id} onSubmit={(event) => void classifyEggs(event, record)}>
          <p>{record.occurred_on}: {record.egg_count} huevos pendientes · lote {record.flock_id}</p>
          <label htmlFor={`egg-classification-warehouse-${record.id}`}>Depósito para {record.id}</label>
          <select
            id={`egg-classification-warehouse-${record.id}`}
            value={classificationWarehouse[record.id] ?? ""}
            onChange={(event) => setClassificationWarehouse((current) => ({ ...current, [record.id]: event.target.value }))}
            required
          >
            <option value="">Selecciona depósito</option>
            {eggWarehouses.map((warehouse) => (
              <option key={warehouse.id} value={warehouse.id}>{warehouse.code} · {warehouse.name}</option>
            ))}
          </select>
          {eggCategories.map((category) => (
            <div key={category.id}>
              <label htmlFor={`egg-classification-${record.id}-${category.id}`}>Huevos {category.code}</label>
              <input
                id={`egg-classification-${record.id}-${category.id}`}
                type="number"
                min="0"
                max={Number.MAX_SAFE_INTEGER}
                step="1"
                value={classificationInputs[record.id]?.[category.id] ?? ""}
                onChange={(event) => setClassificationInputs((current) => ({
                  ...current,
                  [record.id]: { ...current[record.id], [category.id]: event.target.value },
                }))}
              />
            </div>
          ))}
          {eggCategories.length === 0 && record.egg_count > 0 ? (
            <p>Primero configura al menos una categoría de huevos en Inventario.</p>
          ) : null}
          <button
            type="submit"
            disabled={classificationState === "saving" || eggWarehouses.length === 0 || (record.egg_count > 0 && eggCategories.length === 0)}
          >
            {classificationState === "saving" ? "Guardando clasificación." : "Confirmar clasificación"}
          </button>
        </form>
      ))}
      {classificationError ? <p role="alert">{classificationError}</p> : null}
      {classificationState === "saved" ? <p role="status">Clasificación de huevos guardada.</p> : null}
      {unclassifiedRecords.length > 0 ? (
        <p>La existencia física se registra por huevo individual; el costo por huevo sigue pendiente de la fórmula aprobada.</p>
      ) : null}
    </section>
  );
}
