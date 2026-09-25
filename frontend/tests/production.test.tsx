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
  await waitFor(() => expect(screen.getByText("No se pudo cargar producci�n.")).toBeInTheDocument());
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
  fireEvent.change(screen.getByLabelText("Galp�n"), { target: { value: "house-1" } });
  fireEvent.change(screen.getByLabelText("Cantidad de huevos"), { target: { value: "120" } });
  fireEvent.click(screen.getByRole("button", { name: "Registrar huevos" }));
  await waitFor(() => expect(screen.getByText("Producci�n de huevos registrada.")).toBeInTheDocument());
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
  fireEvent.change(screen.getByLabelText("Galp�n"), { target: { value: "house-1" } });
  fireEvent.change(screen.getByLabelText("Cantidad de huevos"), { target: { value: "120" } });
  fireEvent.click(screen.getByRole("button", { name: "Registrar huevos" }));
  await screen.findByText("No se pudo registrar la producci�n de huevos.");
  const firstPost = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
  const firstKey = (JSON.parse(String(firstPost?.[1]?.body)) as { idempotency_key: string }).idempotency_key;
  fireEvent.click(screen.getByRole("button", { name: "Registrar huevos" }));
  await screen.findByText("Producci�n de huevos registrada.");
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
          { id: "category-a", code: "CAT-A", name: "Categor�a A", is_active: true },
          { id: "category-b", code: "CAT-B", name: "Categor�a B", is_active: true },
        ],
      } as Response;
    }
    if (url.endsWith("/inventory/egg-configuration-options")) {
      return {
        ok: true,
        json: async () => ({ warehouses: [{ id: "warehouse-1", code: "WH-1", name: "Dep�sito 1" }] }),
      } as Response;
    }
    if (url.includes("egg-records") && init?.method === "POST") return { ok: true, json: async () => ({}) } as Response;
    return { ok: true, json: async () => [] } as Response;
  });
  render(<ProductionPanel />);
  await screen.findByRole("heading", { name: "Clasificaci�n de producci�n pendiente" });
  fireEvent.change(screen.getByLabelText("Dep�sito para event-1"), { target: { value: "warehouse-1" } });
  fireEvent.change(screen.getByLabelText("Huevos CAT-A"), { target: { value: "7" } });
  fireEvent.change(screen.getByLabelText("Huevos CAT-B"), { target: { value: "5" } });
  fireEvent.click(screen.getByRole("button", { name: "Confirmar clasificaci�n" }));
  await waitFor(() => expect(screen.getByText("Clasificaci�n de huevos guardada.")).toBeInTheDocument());
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

test("reverses an active egg classification only with a reason and refreshes its ledger status", async () => {
  let reversed = false;
  const fetchMock = vi.spyOn(global, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith("/production/balances")) return { ok: true, json: async () => [] } as Response;
    if (url.includes("egg-record-options")) return { ok: true, json: async () => [] } as Response;
    if (url.includes("egg-records/unclassified")) return { ok: true, json: async () => [] } as Response;
    if (url.endsWith("/egg-records/event-1/classifications") && init?.method !== "POST") {
      return {
        ok: true,
        json: async () => [{
          id: "classification-1",
          warehouse_id: "warehouse-1",
          inventory_status: reversed ? "REVERSED" : "CONFIRMED",
          allocations: [{ category_id: "category-1", category_code: "GRADE-A", egg_count: 12 }],
        }],
      } as Response;
    }
    if (url.endsWith("/classifications/classification-1/reverse") && init?.method === "POST") {
      reversed = true;
      return { ok: true } as Response;
    }
    if (url.includes("egg-records") && !url.includes("/unclassified")) {
      return {
        ok: true,
        json: async () => [{ id: "event-1", flock_id: "flock-1", house_id: "house-1", occurred_on: "2026-09-19", egg_count: 12 }],
      } as Response;
    }
    return { ok: true, json: async () => [] } as Response;
  });
  render(<ProductionPanel />);
  await screen.findByText(/12 huevos \(lote flock-1\)/);
  fireEvent.click(screen.getByRole("button", { name: "Ver clasificaciones" }));
  await screen.findByText(/GRADE-A: 12 huevos/);
  fireEvent.click(screen.getByRole("button", { name: "Revertir clasificaci�n" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirmar reversi�n" }));
  expect(await screen.findByText("Indica un motivo para revertir la clasificaci�n.")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Motivo de reversi�n"), { target: { value: "Corregir lote" } });
  fireEvent.click(screen.getByRole("button", { name: "Confirmar reversi�n" }));
  await screen.findByText("Clasificaci�n revertida; el movimiento compensatorio qued� registrado.");
  expect(screen.getByText(/Revertida/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Revertir clasificaci�n" })).not.toBeInTheDocument();
  const reverseCall = fetchMock.mock.calls.find(([url, init]) =>
    String(url).endsWith("/classifications/classification-1/reverse") && init?.method === "POST",
  );
  expect(reverseCall).toEqual([
    "/api/v1/production/egg-records/event-1/classifications/classification-1/reverse",
    expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({ "X-CSRF-Token": "" }),
      body: JSON.stringify({ reason: "Corregir lote" }),
    }),
  ]);
});

