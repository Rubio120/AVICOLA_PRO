import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SystemStatus } from "@/components/system-status";


describe("SystemStatus", () => {
  it("announces an operational API and database", () => {
    render(<SystemStatus available />);

    expect(screen.getByRole("status")).toHaveTextContent("API y base de datos disponibles");
  });

  it("announces a degraded dependency without technical details", () => {
    render(<SystemStatus available={false} />);

    expect(screen.getByRole("status")).toHaveTextContent("API o base de datos no disponibles");
    expect(screen.queryByText(/postgresql:\/\//i)).not.toBeInTheDocument();
  });
});

