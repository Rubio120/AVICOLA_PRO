"use client";

import { useEffect, useState } from "react";

type Balance = { flock_id: string; live_birds: string };
type EggOption = { flock_id: string; flock_code: string; house_id: string; house_code: string };
type EggRecord = { id: string; flock_id: string; house_id: string; occurred_on: string; egg_count: number };
type EggCategoryOption = { id: string; code: string; name: string; is_active: boolean };
type EggWarehouseOption = { id: string; code: string; name: string };
type EggClassification = {
  id: string;
  warehouse_id: string;
  inventory_status: string | null;
  allocations: { category_id: string; category_code: string; egg_count: number }[];
};

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
  const [classificationHistory, setClassificationHistory] = useState<Record<string, EggClassification[]>>({});
  const [historyOpen, setHistoryOpen] = useState<Record<string, boolean>>({});
  const [historyLoading, setHistoryLoading] = useState<Record<string, boolean>>({});
  const [reversalReasons, setReversalReasons] = useState<Record<string, string>>({});
  const [reversalFormOpen, setReversalFormOpen] = useState<Record<string, boolean>>({});
  const [reversalErrors, setReversalErrors] = useState<Record<string, string>>({});
  const [reversingId, setReversingId] = useState<string | null>(null);
  const [reversalSaved, setReversalSaved] = useState(false);

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

  async function loadClassificationHistory(recordId: string) {
    setHistoryLoading((current) => ({ ...current, [recordId]: true }));
    try {
      const response = await fetch(`/api/v1/production/egg-records/${recordId}/classifications`, {
        credentials: "include",
      });
      if (!response.ok) throw new Error("classification history unavailable");
      const history = (await response.json()) as EggClassification[];
      setClassificationHistory((current) => ({ ...current, [recordId]: history }));
      setHistoryOpen((current) => ({ ...current, [recordId]: true }));
    } catch {
      setReversalErrors((current) => ({ ...current, [recordId]: "No se pudo cargar el historial de clasificaci�n." }));
    } finally {
      setHistoryLoading((current) => ({ ...current, [recordId]: false }));
    }
  }

  async function reverseClassification(
    event: React.FormEvent<HTMLFormElement>,
    recordId: string,
    classificationId: string,
  ) {
    event.preventDefault();
    const reason = reversalReasons[classificationId]?.trim() ?? "";
    if (!reason) {
      setReversalErrors((current) => ({ ...current, [recordId]: "Indica un motivo para revertir la clasificaci�n." }));
      return;
    }
    setReversalErrors((current) => ({ ...current, [recordId]: "" }));
    setReversingId(classificationId);
    try {
      const response = await fetch(
        `/api/v1/production/egg-records/${recordId}/classifications/${classificationId}/reverse`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": window.sessionStorage.getItem("avicola_csrf_token") ?? "",
          },
          body: JSON.stringify({ reason }),
        },
      );
      if (!response.ok) throw new Error("egg classification reversal failed");
      await loadClassificationHistory(recordId);
      await refreshEggRecords();
      setReversalSaved(true);
    } catch {
      setReversalErrors((current) => ({ ...current, [recordId]: "No se pudo revertir la clasificaci�n." }));
    } finally {
      setReversingId(null);
    }
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
      setClassificationError("Las cantidades por categor�a deben ser huevos enteros no negativos.");
      return;
    }
    if (values.reduce((total, item) => total + item.egg_count, 0) !== record.egg_count) {
      setClassificationError("La suma por categor�as debe coincidir con el total diario.");
      return;
    }
    const warehouseId = classificationWarehouse[record.id];
    if (!warehouseId) {
      setClassificationError("Selecciona el dep�sito que recibir� los huevos.");
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
      setClassificationError("No se pudo guardar la clasificaci�n de huevos.");
    }
  }


  return (
    <section className="technical-card" aria-labelledby="production-title">
      <p className="eyebrow">Entrega 5</p>
      <h2 id="production-title">Producci�n av�cola</h2>
      <p>Lotes activos y saldo de aves vivas reconstruible desde eventos.</p>
      {state === "loading" ? <p role="status">Cargando producci�n.</p> : null}
      {state === "error" ? <p role="alert">No se pudo cargar producci�n.</p> : null}
      {state === "ready" && balances.length === 0 ? <p>Sin lotes activos.</p> : null}
      {balances.length > 0 ? (
        <ul>
          {balances.map((balance) => <li key={balance.flock_id}>{balance.flock_id}: {balance.live_birds} aves vivas</li>)}
        </ul>
      ) : null}
      <h3>Producci�n diaria de huevos</h3>
      <p>Registra unidades enteras por lote, galp�n y fecha.</p>
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
        <label htmlFor="egg-house-id">Galp�n</label>
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
          <option value="">Selecciona un galp�n</option>
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
          {eggState === "saving" ? "Guardando." : "Registrar huevos"}
        </button>
      </form>
      {!optionsAreCurrent ? <p role="status">Cargando lotes y galpones.</p> : null}
      {optionsAreCurrent && optionsResult.state === "error" ? <p role="alert">No se pudieron cargar lotes y galpones.</p> : null}
      {optionsAreCurrent && optionsResult.state === "ready" && eggOptions.length === 0 ? (
        <p>No hay lotes y galpones activos para esa fecha.</p>
      ) : null}
      {eggState === "saved" ? <p role="status">Producci�n de huevos registrada.</p> : null}
      {eggState === "error" ? <p role="alert">No se pudo registrar la producci�n de huevos.</p> : null}
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
            <li key={record.id}>
              {record.occurred_on}: {record.egg_count} huevos (lote {record.flock_id})
              <button
                type="button"
                disabled={historyLoading[record.id]}
                onClick={() => {
                  if (historyOpen[record.id]) {
                    setHistoryOpen((current) => ({ ...current, [record.id]: false }));
                  } else {
                    void loadClassificationHistory(record.id);
                  }
                }}
              >
                {historyLoading[record.id] ? "Cargando historial." : "Ver clasificaciones"}
              </button>
              {historyOpen[record.id] ? (
                <ul>
                  {(classificationHistory[record.id] ?? []).map((classification) => (
                    <li key={classification.id}>
                      <p>
                        {classification.allocations.map((allocation) => `${allocation.category_code}: ${allocation.egg_count} huevos`).join(", ") || "Sin unidades clasificadas"}
                        {classification.inventory_status === "REVERSED" ? " - Revertida" : ""}
                      </p>
                      {classification.inventory_status === "CONFIRMED" ? (
                        <form onSubmit={(event) => void reverseClassification(event, record.id, classification.id)}>
                          <button
                            type="button"
                            disabled={reversingId !== null}
                            onClick={() => {
                              setReversalFormOpen((current) => ({ ...current, [classification.id]: !current[classification.id] }));
                              setReversalErrors((current) => ({ ...current, [record.id]: "" }));
                            }}
                          >
                            Revertir clasificaci�n
                          </button>
                          {reversalFormOpen[classification.id] ? (
                            <>
                              <label htmlFor={`classification-reason-${classification.id}`}>Motivo de reversi�n</label>
                              <textarea
                                id={`classification-reason-${classification.id}`}
                                maxLength={500}
                                value={reversalReasons[classification.id] ?? ""}
                                onChange={(event) => setReversalReasons((current) => ({ ...current, [classification.id]: event.target.value }))}
                              />
                              <button type="submit" disabled={reversingId === classification.id}>
                                {reversingId === classification.id ? "Revirtiendo." : "Confirmar reversi�n"}
                              </button>
                            </>
                          ) : null}
                        </form>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : null}
              {reversalErrors[record.id] ? <p role="alert">{reversalErrors[record.id]}</p> : null}
            </li>
          ))}
        </ul>
      ) : null}
      {reversalSaved ? <p role="status">Clasificaci�n revertida; el movimiento compensatorio qued� registrado.</p> : null}
      <h3>Clasificaci�n de producci�n pendiente</h3>
      {!unclassifiedAreCurrent ? <p role="status">Cargando clasificaciones pendientes.</p> : null}
      {unclassifiedAreCurrent && unclassifiedResult.state === "error" ? (
        <p role="alert">No se pudieron cargar las clasificaciones pendientes.</p>
      ) : null}
      {unclassifiedAreCurrent && unclassifiedResult.state === "ready" && unclassifiedRecords.length === 0 ? (
        <p>Sin producci�n pendiente de clasificar.</p>
      ) : null}
      {unclassifiedRecords.map((record) => (
        <form key={record.id} onSubmit={(event) => void classifyEggs(event, record)}>
          <p>{record.occurred_on}: {record.egg_count} huevos pendientes � lote {record.flock_id}</p>
          <label htmlFor={`egg-classification-warehouse-${record.id}`}>Dep�sito para {record.id}</label>
          <select
            id={`egg-classification-warehouse-${record.id}`}
            value={classificationWarehouse[record.id] ?? ""}
            onChange={(event) => setClassificationWarehouse((current) => ({ ...current, [record.id]: event.target.value }))}
            required
          >
            <option value="">Selecciona dep�sito</option>
            {eggWarehouses.map((warehouse) => (
              <option key={warehouse.id} value={warehouse.id}>{warehouse.code} � {warehouse.name}</option>
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
            <p>Primero configura al menos una categor�a de huevos en Inventario.</p>
          ) : null}
          <button
            type="submit"
            disabled={classificationState === "saving" || eggWarehouses.length === 0 || (record.egg_count > 0 && eggCategories.length === 0)}
          >
            {classificationState === "saving" ? "Guardando clasificaci�n." : "Confirmar clasificaci�n"}
          </button>
        </form>
      ))}
      {classificationError ? <p role="alert">{classificationError}</p> : null}
      {classificationState === "saved" ? <p role="status">Clasificaci�n de huevos guardada.</p> : null}
      {unclassifiedRecords.length > 0 ? (
        <p>La existencia f�sica se registra por huevo individual; el costo por huevo sigue pendiente de la f�rmula aprobada.</p>
      ) : null}
    </section>
  );
}

