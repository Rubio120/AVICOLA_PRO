"use client";

import { FormEvent, useState } from "react";

export function IdentityPanel() {
  const [message, setMessage] = useState<string | null>(null);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("La autenticación se procesa de forma segura en la API.");
  }

  return (
    <section className="technical-card identity-panel" aria-labelledby="identity-title">
      <p className="eyebrow">Acceso seguro</p>
      <h2 id="identity-title">Identidad y permisos</h2>
      <p>Los permisos se validan en el backend.</p>
      <form onSubmit={submit}>
        <label htmlFor="identity">Usuario o correo</label>
        <input id="identity" name="identity" autoComplete="username" required />
        <label htmlFor="password">Contraseña</label>
        <input id="password" name="password" type="password" autoComplete="current-password" required />
        <button type="submit">Iniciar sesión</button>
      </form>
      {message ? <p role="status">{message}</p> : null}
    </section>
  );
}
