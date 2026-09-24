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
    <>
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
    <EggInventorySettings />
    </>
  );
}

type EggProductOption = { id: string; sku: string; name: string; base_unit_code: string };
type EggUnitOption = { code: string; name: string; precision: number };
type EggCategory = {
  id: string;
  code: string;
  name: string;
  product_id: string;
  product_sku: string;
  base_unit_code: string;
  is_saleable: boolean;
  is_active: boolean;
};
type EggBalance = {
  category_id: string;
  category_code: string;
  category_name: string;
  product_sku: string;
  warehouse_id: string | null;
  quantity_eggs: string;
  inventory_value: string;
};
type EggConversion = { id: string; unit_code: string; version: number; units_per_package: number };

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { credentials: "include" });
  if (!response.ok) throw new Error("egg inventory unavailable");
  return (await response.json()) as T;
}

export function EggInventorySettings() {
  const [products, setProducts] = useState<EggProductOption[]>([]);
  const [units, setUnits] = useState<EggUnitOption[]>([]);
  const [categories, setCategories] = useState<EggCategory[]>([]);
  const [balances, setBalances] = useState<EggBalance[]>([]);
  const [categoryCode, setCategoryCode] = useState("");
  const [categoryName, setCategoryName] = useState("");
  const [productId, setProductId] = useState("");
  const [isSaleable, setIsSaleable] = useState("");
  const [isActive, setIsActive] = useState("");
  const [conversionCategoryId, setConversionCategoryId] = useState("");
  const [unitCode, setUnitCode] = useState("");
  const [factor, setFactor] = useState("");
  const [conversionsResult, setConversionsResult] = useState<{ categoryId: string; items: EggConversion[] } | null>(null);
  const conversions = conversionsResult?.categoryId === conversionCategoryId ? conversionsResult.items : [];
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [message, setMessage] = useState("");

  async function loadSettings() {
    setState("loading");
    try {
      const [options, categoryRows, balancePage] = await Promise.all([
        getJson<{ products?: EggProductOption[]; units?: EggUnitOption[] }>("/api/v1/inventory/egg-configuration-options"),
        getJson<EggCategory[]>("/api/v1/inventory/egg-categories"),
        getJson<{ items?: EggBalance[] }>("/api/v1/inventory/egg-balances?offset=0&limit=100"),
      ]);
      setProducts(options.products ?? []);
      setUnits(options.units ?? []);
      setCategories(Array.isArray(categoryRows) ? categoryRows : []);
      setBalances(balancePage.items ?? []);
      setState("ready");
    } catch {
      setState("error");
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => void loadSettings(), 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!conversionCategoryId) {
      return;
    }
    const controller = new AbortController();
    fetch(`/api/v1/inventory/egg-categories/${conversionCategoryId}/conversions`, {
      credentials: "include",
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("egg conversions unavailable");
        const body = (await response.json()) as EggConversion[];
        setConversionsResult({ categoryId: conversionCategoryId, items: Array.isArray(body) ? body : [] });
      })
      .catch(() => {
        if (!controller.signal.aborted) setConversionsResult({ categoryId: conversionCategoryId, items: [] });
      });
    return () => controller.abort();
  }, [conversionCategoryId]);

  async function createCategory(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    const response = await fetch("/api/v1/inventory/egg-categories", {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": window.sessionStorage.getItem("avicola_csrf_token") ?? "",
      },
      body: JSON.stringify({
        code: categoryCode,
        name: categoryName,
        product_id: productId,
        is_saleable: isSaleable === "true",
        is_active: isActive === "true",
      }),
    });
    if (!response.ok) {
      setMessage("No se pudo guardar la categoría.");
      return;
    }
    setCategoryCode("");
    setCategoryName("");
    setProductId("");
    setIsSaleable("");
    setIsActive("");
    setMessage("Categoría guardada.");
    await loadSettings();
  }

  async function createConversion(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const response = await fetch(`/api/v1/inventory/egg-categories/${conversionCategoryId}/conversions`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": window.sessionStorage.getItem("avicola_csrf_token") ?? "",
      },
      body: JSON.stringify({ unit_code: unitCode, units_per_package: Number(factor) }),
    });
    if (!response.ok) {
      setMessage("No se pudo guardar la equivalencia.");
      return;
    }
    setUnitCode("");
    setFactor("");
    setMessage("Nueva versión de equivalencia guardada.");
    await loadSettings();
    const rows = await getJson<EggConversion[]>(
      `/api/v1/inventory/egg-categories/${conversionCategoryId}/conversions`,
    ).catch(() => []);
    setConversionsResult({ categoryId: conversionCategoryId, items: rows });
  }

  return (
    <section className="technical-card" aria-labelledby="egg-inventory-title">
      <p className="eyebrow">Inventario avícola</p>
      <h2 id="egg-inventory-title">Inventario de huevos</h2>
      <p>Las categorías y equivalencias se configuran aquí; no hay calidades ni tamaños precargados.</p>
      {state === "loading" ? <p role="status">Cargando configuración de huevos.</p> : null}
      {state === "error" ? <p role="alert">No se pudo cargar la configuración de huevos.</p> : null}
      <form onSubmit={createCategory}>
        <label htmlFor="egg-category-code">Código de categoría</label>
        <input id="egg-category-code" value={categoryCode} onChange={(event) => setCategoryCode(event.target.value)} required />
        <label htmlFor="egg-category-name">Nombre de categoría</label>
        <input id="egg-category-name" value={categoryName} onChange={(event) => setCategoryName(event.target.value)} required />
        <label htmlFor="egg-category-product">Producto base (un huevo por unidad)</label>
        <select id="egg-category-product" value={productId} onChange={(event) => setProductId(event.target.value)} required>
          <option value="">Selecciona producto</option>
          {products.map((item) => (
            <option key={item.id} value={item.id}>{item.sku} · {item.name} ({item.base_unit_code})</option>
          ))}
        </select>
        <label htmlFor="egg-category-saleable">¿Se puede vender?</label>
        <select id="egg-category-saleable" value={isSaleable} onChange={(event) => setIsSaleable(event.target.value)} required>
          <option value="">Elige una opción</option>
          <option value="true">Sí</option>
          <option value="false">No</option>
        </select>
        <label htmlFor="egg-category-active">Estado de categoría</label>
        <select id="egg-category-active" value={isActive} onChange={(event) => setIsActive(event.target.value)} required>
          <option value="">Elige una opción</option>
          <option value="true">Activa</option>
          <option value="false">Inactiva</option>
        </select>
        <button type="submit" disabled={state !== "ready"}>Crear categoría</button>
      </form>
      {categories.length > 0 ? (
        <ul>{categories.map((item) => <li key={item.id}>{item.code} · {item.name} · {item.product_sku} · {item.is_active ? "Activa" : "Inactiva"}</li>)}</ul>
      ) : null}
      <h3>Equivalencias de presentación</h3>
      <p>Indica cuántos huevos individuales representa cada unidad; cada cambio crea una versión nueva.</p>
      <form onSubmit={createConversion}>
        <label htmlFor="egg-conversion-category">Categoría</label>
        <select id="egg-conversion-category" value={conversionCategoryId} onChange={(event) => setConversionCategoryId(event.target.value)} required>
          <option value="">Selecciona categoría</option>
          {categories.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}
        </select>
        <label htmlFor="egg-conversion-unit">Unidad de presentación</label>
        <select id="egg-conversion-unit" value={unitCode} onChange={(event) => setUnitCode(event.target.value)} required>
          <option value="">Selecciona unidad</option>
          {units.map((item) => <option key={item.code} value={item.code}>{item.code} · {item.name}</option>)}
        </select>
        <label htmlFor="egg-conversion-factor">Huevos por unidad</label>
        <input id="egg-conversion-factor" type="number" min="1" step="1" value={factor} onChange={(event) => setFactor(event.target.value)} required />
        <button type="submit" disabled={state !== "ready" || !conversionCategoryId}>Guardar equivalencia</button>
      </form>
      {conversions.map((item) => (
        <p key={item.id}>{item.unit_code}, versión {item.version}: {item.units_per_package} huevos</p>
      ))}
      <h3>Existencias por categoría</h3>
      {balances.length === 0 ? <p>Sin saldos clasificados.</p> : null}
      {balances.length > 0 ? (
        <ul>{balances.map((item, index) => <li key={`${item.category_id}-${item.warehouse_id ?? index}`}>
          {item.category_code} · {item.quantity_eggs} huevos · {item.warehouse_id ?? "Sin depósito"}
        </li>)}</ul>
      ) : null}
      {message ? <p role="status">{message}</p> : null}
    </section>
  );
}
