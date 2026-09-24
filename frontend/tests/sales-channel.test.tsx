import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SalesPanel } from "@/components/sales-panel";

describe("SalesPanel sales channels", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [
          { id: "1", customer_id: "c1", order_date: "2026-09-24", status: "DRAFT", total: "10", channel: "WHOLESALE" },
          { id: "2", customer_id: "c2", order_date: "2026-09-24", status: "DRAFT", total: "20", channel: "RETAIL" },
          { id: "3", customer_id: "c3", order_date: "2026-09-24", status: "DRAFT", total: "30", channel: null },
        ],
      }),
    );
  });
  afterEach(() => vi.unstubAllGlobals());

  it("filters channels without guessing legacy records", async () => {
    render(<SalesPanel />);
    await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(3));
    expect(screen.getAllByRole("listitem")[2]).toHaveTextContent("Histórico sin clasificar");

    await userEvent.selectOptions(screen.getByLabelText("Filtrar canal de venta"), "WHOLESALE");
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getByRole("listitem")).toHaveTextContent("Mayorista");
  });
});
