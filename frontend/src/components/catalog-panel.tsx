"use client";

import { useEffect, useState } from "react";

type CatalogItem = { sku?: string; code?: string; name: string };
type CatalogPage = { items: CatalogItem[]; total?: number };

export function CatalogPanel() {
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const [sku, setSku] = useState("");
  const [name, setName] = useState("");
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/v1/catalog/products?offset=${page * 20}&limit=20&search=${encodeURIComponent(search)}`, {
      credentials: "include",
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("catalog unavailable");
        const body = (await response.json()) as CatalogPage;
        setItems(body.items);
        setTotal(body.total ?? body.items.length);
        setState("ready");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setState("error");
      });
    return () => controller.abort();
  }, [page, search]);

  async function createProduct(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const response = await fetch("/api/v1/catalog/products", {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": window.sessionStorage.getItem("avicola_csrf_token") ?? "",
      },
      body: JSON.stringify({ sku, name, product_type: "INPUT", base_unit_code: "unit" }),
    });
    if (response.ok) {
      setSku("");
      setName("");
      setPage(0);
      setState("loading");
    } else {
      setState("error");
    }
  }

  return (
    <section className="technical-card" aria-labelledby="catalog-title">
      <p className="eyebrow">Entrega 3</p>
      <h2 id="catalog-title">CatÃ¡logo</h2>
      <label htmlFor="catalog-search">Buscar productos</label>
      <input id="catalog-search" value={search} onChange={(event) => { setSearch(event.target.value); setPage(0); }} />
      <form onSubmit={createProduct}>
        <label htmlFor="catalog-sku">SKU</label>
        <input id="catalog-sku" value={sku} onChange={(event) => setSku(event.target.value)} required />
        <label htmlFor="catalog-name">Nombre del producto</label>
        <input id="catalog-name" value={name} onChange={(event) => setName(event.target.value)} required />
        <button type="submit">Crear producto</button>
      </form>
      {state === "loading" ? <p role="status">Cargando catÃ¡logoâ€¦</p> : null}
      {state === "error" ? <p role="alert">No se pudo cargar el catÃ¡logo.</p> : null}
      {state === "ready" && items.length === 0 ? <p>Sin productos activos.</p> : null}
      {items.length > 0 ? <ul>{items.map((item) => <li key={item.sku ?? item.code}>{item.sku ?? item.code}: {item.name}</li>)}</ul> : null}
      {total > 20 ? (
        <nav aria-label="Paginación del catálogo">
          <button type="button" onClick={() => setPage((current) => Math.max(0, current - 1))} disabled={page === 0}>Anterior</button>
          <span>Página {page + 1}</span>
          <button type="button" onClick={() => setPage((current) => current + 1)} disabled={(page + 1) * 20 >= total}>Siguiente</button>
        </nav>
      ) : null}
    </section>
  );
}
