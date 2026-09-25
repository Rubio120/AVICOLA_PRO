import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { IdentityPanel } from "@/components/identity-panel";

const user = {
  id: "00000000-0000-0000-0000-000000000001",
  username: "admin",
  email: "admin@example.test",
  display_name: "Admin",
  must_change_password: false,
};

describe("IdentityPanel", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("logs in through the backend and shows the authenticated session", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(user), {
        status: 200,
        headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf-token" },
      }),
    );

    render(<IdentityPanel apiBaseUrl="http://backend.test" />);
    fireEvent.change(screen.getByLabelText("Usuario o correo"), { target: { value: "admin" } });
    fireEvent.change(screen.getByLabelText("Contraseña"), { target: { value: "secret-password" } });
    fireEvent.submit(screen.getByRole("button", { name: "Iniciar sesión" }));

    await waitFor(() => expect(screen.getByText("Sesión activa como admin")).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledWith(
      "http://backend.test/api/v1/auth/login",
      expect.objectContaining({ method: "POST", credentials: "include" }),
    );
    expect(screen.getByRole("button", { name: "Cerrar sesión" })).toBeInTheDocument();
  });

  it("shows a generic error when the backend rejects login", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Invalid credentials" }), { status: 401 }),
    );

    render(<IdentityPanel apiBaseUrl="http://backend.test" />);
    fireEvent.change(screen.getByLabelText("Usuario o correo"), { target: { value: "admin" } });
    fireEvent.change(screen.getByLabelText("Contraseña"), { target: { value: "wrong-password" } });
    fireEvent.submit(screen.getByRole("button", { name: "Iniciar sesión" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("No fue posible iniciar sesión."));
  });

  it("requires the temporary password to be replaced before showing the session", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ ...user, must_change_password: true }), {
        status: 200,
        headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf-token" },
      }),
    );
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify(user), {
        status: 200,
        headers: { "Content-Type": "application/json", "X-CSRF-Token": "new-csrf" },
      }),
    );

    render(<IdentityPanel apiBaseUrl="http://backend.test" />);
    fireEvent.change(screen.getByLabelText("Usuario o correo"), { target: { value: "admin" } });
    fireEvent.change(screen.getByLabelText("Contraseña"), { target: { value: "temporary-password" } });
    fireEvent.submit(screen.getByRole("button", { name: "Iniciar sesión" }));

    await waitFor(() => expect(screen.getByRole("heading", { name: "Cambiar contraseña" })).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("Contraseña actual"), { target: { value: "temporary-password" } });
    fireEvent.change(screen.getByLabelText("Nueva contraseña"), { target: { value: "new-secure-password" } });
    fireEvent.submit(screen.getByRole("button", { name: "Cambiar contraseña" }));

    await waitFor(() => expect(screen.getByText("Sesión activa como admin")).toBeInTheDocument());
    expect(fetchMock).toHaveBeenLastCalledWith(
      "http://backend.test/api/v1/auth/change-password",
      expect.objectContaining({ method: "POST", credentials: "include" }),
    );
  });

  it("logs out the active session with the CSRF token", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(user), {
        status: 200,
        headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf-token" },
      }),
    );
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));

    render(<IdentityPanel apiBaseUrl="http://backend.test" />);
    fireEvent.change(screen.getByLabelText("Usuario o correo"), { target: { value: "admin" } });
    fireEvent.change(screen.getByLabelText("Contraseña"), { target: { value: "secret-password" } });
    fireEvent.submit(screen.getByRole("button", { name: "Iniciar sesión" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Cerrar sesión" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Cerrar sesión" }));

    await waitFor(() => expect(screen.getByRole("button", { name: "Iniciar sesión" })).toBeInTheDocument());
    expect(fetchMock).toHaveBeenLastCalledWith(
      "http://backend.test/api/v1/auth/logout",
      expect.objectContaining({ method: "POST", headers: { "X-CSRF-Token": "csrf-token" } }),
    );
  });

  it("shows the login fields and backend authorization boundary", () => {
    render(<IdentityPanel apiBaseUrl="http://backend.test" />);

    expect(screen.getByLabelText("Usuario o correo")).toBeInTheDocument();
    expect(screen.getByLabelText("Contraseña")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Iniciar sesión" })).toBeInTheDocument();
    expect(screen.getByText("Los permisos se validan en el backend.")).toBeInTheDocument();
  });
});
