import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { ProductionPanel } from "@/components/production-panel";

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

test("shows flock live bird balances", async () => {
  vi.spyOn(global, "fetch").mockResolvedValue({ ok: true, json: async () => [{ flock_id: "flock-1", live_birds: "42.0000" }] } as Response);
  render(<ProductionPanel />);
  await waitFor(() => expect(screen.getByText(/42\.0000 aves vivas/)).toBeInTheDocument());
});

test("shows a safe error state when production is unavailable", async () => {
  vi.spyOn(global, "fetch").mockRejectedValue(new Error("offline"));
  render(<ProductionPanel />);
  await waitFor(() => expect(screen.getByText("No se pudo cargar producción.")).toBeInTheDocument());
});

test("records daily whole-egg production with CSRF and an idempotency key", async () => {
  vi.stubGlobal("crypto", { randomUUID: () => "egg-record-test-key" });
  const fetchMock = vi.spyOn(global, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith("/production/balances")) return { ok: true, json: async () => [] } as Response;
    if (url.includes("egg-record-options")) {
      return {
        ok: true,
        json: async () => [{ flock_id: "flock-1", flock_code: "F-1", house_id: "house-1", house_code: "H-1" }],
      } as Response;
    }
    if (url.includes("egg-records") && init?.method === "POST") return { ok: true } as Response;
    return { ok: true, json: async () => [] } as Response;
  });
  render(<ProductionPanel />);
  await screen.findByRole("option", { name: "F-1" });
  await screen.findByText("Sin registros para esta fecha.");
  fireEvent.change(await screen.findByLabelText("Lote"), { target: { value: "flock-1" } });
  fireEvent.change(screen.getByLabelText("Galpón"), { target: { value: "house-1" } });
  fireEvent.change(screen.getByLabelText("Cantidad de huevos"), { target: { value: "120" } });
  fireEvent.click(screen.getByRole("button", { name: "Registrar huevos" }));
  await waitFor(() => expect(screen.getByText("Producción de huevos registrada.")).toBeInTheDocument());
  const postCall = fetchMock.mock.calls.find(([url, init]) =>
    String(url) === "/api/v1/production/egg-records" && init?.method === "POST",
  );
  expect(postCall).toBeDefined();
  expect(postCall).toEqual([
    "/api/v1/production/egg-records",
    expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({ "X-CSRF-Token": "" }),
      body: expect.stringContaining('"egg_count":120'),
    }),
  ]);
  const request = JSON.parse(String(postCall?.[1]?.body)) as { idempotency_key: string };
  expect(request.idempotency_key).toBeTruthy();
});

test("reuses the idempotency key when an egg-record request is retried after a network error", async () => {
  let keySequence = 0;
  let postCount = 0;
  vi.stubGlobal("crypto", { randomUUID: () => `egg-retry-key-${++keySequence}` });
  const fetchMock = vi.spyOn(global, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith("/production/balances")) return { ok: true, json: async () => [] } as Response;
    if (url.includes("egg-record-options")) {
      return {
        ok: true,
        json: async () => [{ flock_id: "flock-1", flock_code: "F-1", house_id: "house-1", house_code: "H-1" }],
      } as Response;
    }
    if (url.includes("egg-records") && init?.method === "POST") {
      postCount += 1;
      if (postCount === 1) throw new Error("network");
      return { ok: true } as Response;
    }
    return { ok: true, json: async () => [] } as Response;
  });
  render(<ProductionPanel />);
  await screen.findByRole("option", { name: "F-1" });
  fireEvent.change(screen.getByLabelText("Lote"), { target: { value: "flock-1" } });
  fireEvent.change(screen.getByLabelText("Galpón"), { target: { value: "house-1" } });
  fireEvent.change(screen.getByLabelText("Cantidad de huevos"), { target: { value: "120" } });
  fireEvent.click(screen.getByRole("button", { name: "Registrar huevos" }));
  await screen.findByText("No se pudo registrar la producción de huevos.");
  const firstPost = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
  const firstKey = (JSON.parse(String(firstPost?.[1]?.body)) as { idempotency_key: string }).idempotency_key;
  fireEvent.click(screen.getByRole("button", { name: "Registrar huevos" }));
  await screen.findByText("Producción de huevos registrada.");
  const postBodies = fetchMock.mock.calls
    .filter(([, init]) => init?.method === "POST")
    .map(([, init]) => JSON.parse(String(init?.body)) as { idempotency_key: string });
  expect(postBodies).toHaveLength(2);
  expect(postBodies[1]?.idempotency_key).toBe(firstKey);
});

test("classifies an unclassified daily egg total into explicit categories and warehouse", async () => {
  let unclassifiedRequests = 0;
  const fetchMock = vi.spyOn(global, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith("/production/balances")) return { ok: true, json: async () => [] } as Response;
    if (url.includes("egg-record-options")) return { ok: true, json: async () => [] } as Response;
    if (url.includes("egg-records/unclassified")) {
      unclassifiedRequests += 1;
      return {
        ok: true,
        json: async () => unclassifiedRequests === 1
          ? [{ id: "event-1", flock_id: "flock-1", house_id: "house-1", occurred_on: "2026-09-19", egg_count: 12 }]
          : [],
      } as Response;
    }
    if (url.endsWith("/inventory/egg-categories")) {
      return {
        ok: true,
        json: async () => [
          { id: "category-a", code: "CAT-A", name: "Categoría A", is_active: true },
          { id: "category-b", code: "CAT-B", name: "Categoría B", is_active: true },
        ],
      } as Response;
    }
    if (url.endsWith("/inventory/egg-configuration-options")) {
      return {
        ok: true,
        json: async () => ({ warehouses: [{ id: "warehouse-1", code: "WH-1", name: "Depósito 1" }] }),
      } as Response;
    }
    if (url.includes("egg-records") && init?.method === "POST") return { ok: true, json: async () => ({}) } as Response;
    return { ok: true, json: async () => [] } as Response;
  });
  render(<ProductionPanel />);
  await screen.findByRole("heading", { name: "Clasificación de producción pendiente" });
  fireEvent.change(screen.getByLabelText("Depósito para event-1"), { target: { value: "warehouse-1" } });
  fireEvent.change(screen.getByLabelText("Huevos CAT-A"), { target: { value: "7" } });
  fireEvent.change(screen.getByLabelText("Huevos CAT-B"), { target: { value: "5" } });
  fireEvent.click(screen.getByRole("button", { name: "Confirmar clasificación" }));
  await waitFor(() => expect(screen.getByText("Clasificación de huevos guardada.")).toBeInTheDocument());
  const postCall = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
  expect(postCall).toBeDefined();
  expect(String(postCall?.[0])).toContain("event-1/classifications");
  expect(JSON.parse(String(postCall?.[1]?.body))).toMatchObject({
    warehouse_id: "warehouse-1",
    allocations: [
      { category_id: "category-a", egg_count: 7 },
      { category_id: "category-b", egg_count: 5 },
    ],
  });
});
