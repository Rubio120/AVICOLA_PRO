import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReportingPanel } from "@/components/reporting-panel";

describe("ReportingPanel", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows confirmed operational indicators", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        sales_documents: 3,
        sales_total: "1000.00",
        inventory_value: "250.00",
        live_birds: "900.0000",
        accounts_payable: "80.00",
        accounts_receivable: "120.00",
        cash_balance: "40.00",
        confirmed_costs: "500.00",
      }), { status: 200 }),
    );
    render(<ReportingPanel />);
    await waitFor(() => expect(screen.getByText("Ventas emitidas")).toBeInTheDocument());
    expect(screen.getByText("1000.00")).toBeInTheDocument();
  });

  it("shows a safe error state", async () => {
    vi.spyOn(global, "fetch").mockRejectedValue(new Error("offline"));
    render(<ReportingPanel />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("No se pudieron cargar los reportes."));
  });
});
