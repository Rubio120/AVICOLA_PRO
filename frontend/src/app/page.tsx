import { IdentityPanel } from "@/components/identity-panel";
import { SystemStatus } from "@/components/system-status";
import { getBackendHealth } from "@/lib/api/health";
import { getServerEnv } from "@/lib/env";


export const dynamic = "force-dynamic";

export default async function HomePage() {
  const environment = getServerEnv();
  const health = await getBackendHealth(environment.BACKEND_INTERNAL_URL);

  return (
    <main className="technical-shell">
      <section className="technical-card" aria-labelledby="product-title">
        <div className="brand-mark" aria-hidden="true">AP</div>
        <p className="eyebrow">Base técnica</p>
        <h1 id="product-title">AVÍCOLA PRO</h1>
        <p className="lead">
          Plataforma empresarial preparada para iniciar la implementación modular de forma segura y trazable.
        </p>
        <SystemStatus available={health.available} />
        <p className="scope-note">Entrega 2 · Identidad, RBAC y auditoría base</p>
      </section>
      <IdentityPanel />
    </main>
  );
}
