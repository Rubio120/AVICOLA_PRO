"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

type IdentityUser = {
  username: string;
  must_change_password: boolean;
};

type IdentityPanelProps = {
  apiBaseUrl: string;
};

async function responseMessage(response: Response): Promise<string> {
  if (response.status === 401) return "No fue posible iniciar sesión.";
  try {
    const body = (await response.json()) as { detail?: string };
    return body.detail || "No fue posible completar la operación.";
  } catch {
    return "No fue posible completar la operación.";
  }
}

export function IdentityPanel({ apiBaseUrl }: IdentityPanelProps) {
  const baseUrl = apiBaseUrl.replace(/\/$/, "");
  const csrfToken = useRef<string | null>(null);
  const [user, setUser] = useState<IdentityUser | null>(null);
  const [identity, setIdentity] = useState("");
  const [password, setPassword] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const storedCsrf = window.sessionStorage.getItem("avicola_csrf_token");
    if (!storedCsrf) return;
    csrfToken.current = storedCsrf;
    void fetch(`${baseUrl}/api/v1/auth/me`, { credentials: "include" })
      .then(async (response) => {
        if (response.ok) {
          setUser((await response.json()) as IdentityUser);
        } else {
          window.sessionStorage.removeItem("avicola_csrf_token");
          csrfToken.current = null;
        }
      })
      .catch(() => {
        setMessage("No fue posible restaurar la sesión.");
      });
  }, [baseUrl]);

  function rememberCsrf(response: Response) {
    const token = response.headers.get("X-CSRF-Token");
    if (token) {
      csrfToken.current = token;
      window.sessionStorage.setItem("avicola_csrf_token", token);
    }
  }

  async function submitLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      const response = await fetch(`${baseUrl}/api/v1/auth/login`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identity, password }),
      });
      rememberCsrf(response);
      if (!response.ok) {
        setMessage(await responseMessage(response));
        return;
      }
      const loggedInUser = (await response.json()) as IdentityUser;
      setUser(loggedInUser);
      setPassword("");
    } catch {
      setMessage("No fue posible conectar con el servicio de identidad.");
    } finally {
      setBusy(false);
    }
  }

  async function submitPasswordChange(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      const response = await fetch(`${baseUrl}/api/v1/auth/change-password`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken.current || "" },
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      rememberCsrf(response);
      if (!response.ok) {
        setMessage(await responseMessage(response));
        return;
      }
      const changedUser = (await response.json()) as IdentityUser;
      setUser(changedUser);
      setCurrentPassword("");
      setNewPassword("");
    } catch {
      setMessage("No fue posible conectar con el servicio de identidad.");
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    setBusy(true);
    setMessage(null);
    try {
      const response = await fetch(`${baseUrl}/api/v1/auth/logout`, {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-Token": csrfToken.current || "" },
      });
      if (!response.ok) {
        setMessage(await responseMessage(response));
        return;
      }
      csrfToken.current = null;
      window.sessionStorage.removeItem("avicola_csrf_token");
      setUser(null);
      setIdentity("");
    } catch {
      setMessage("No fue posible conectar con el servicio de identidad.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="technical-card identity-panel" aria-labelledby="identity-title">
      <p className="eyebrow">Acceso seguro</p>
      <h2 id="identity-title">Identidad y permisos</h2>
      <p>Los permisos se validan en el backend.</p>
      {user ? (
        user.must_change_password ? (
          <form onSubmit={submitPasswordChange}>
            <h3>Cambiar contraseña</h3>
            <p>El primer acceso requiere reemplazar la contraseña temporal.</p>
            <label htmlFor="current-password">Contraseña actual</label>
            <input
              id="current-password"
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              required
            />
            <label htmlFor="new-password">Nueva contraseña</label>
            <input
              id="new-password"
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              required
            />
            <button type="submit" disabled={busy}>
              Cambiar contraseña
            </button>
          </form>
        ) : (
          <div>
            <p role="status">Sesión activa como {user.username}</p>
            <button type="button" onClick={logout} disabled={busy}>
              Cerrar sesión
            </button>
          </div>
        )
      ) : (
        <form onSubmit={submitLogin}>
          <label htmlFor="identity">Usuario o correo</label>
          <input
            id="identity"
            name="identity"
            autoComplete="username"
            value={identity}
            onChange={(event) => setIdentity(event.target.value)}
            required
          />
          <label htmlFor="password">Contraseña</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
          <button type="submit" disabled={busy}>
            Iniciar sesión
          </button>
        </form>
      )}
      {message ? <p role="alert">{message}</p> : null}
    </section>
  );
}
