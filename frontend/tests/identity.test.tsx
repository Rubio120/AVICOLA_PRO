import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { IdentityPanel } from "@/components/identity-panel";

describe("IdentityPanel", () => {
  it("shows the login fields and backend authorization boundary", () => {
    render(<IdentityPanel />);

    expect(screen.getByLabelText("Usuario o correo")).toBeInTheDocument();
    expect(screen.getByLabelText("Contraseña")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Iniciar sesión" })).toBeInTheDocument();
    expect(screen.getByText("Los permisos se validan en el backend.")).toBeInTheDocument();
  });
});
