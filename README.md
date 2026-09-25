# AVICOLA PRO

Sistema de gestion avicola para una sola empresa. Usa FastAPI, PostgreSQL 16, Alembic y Next.js; conserva la arquitectura modular y la interfaz actual.

## Funciones

- Identidad, roles/permisos, sesiones seguras y auditoria.
- Granjas, galpones, lotes, movimientos de aves y mortalidad.
- Registro diario de produccion por lote/galpon y clasificacion de huevos.
- Inventario de insumos y huevos, conversiones configurables, recepciones, salidas y reversiones trazables.
- Compras, proveedores, pedidos/ventas, documentos internos, cuentas por pagar/cobrar y pagos.
- Caja, costos confirmados, reportes de ventas por canal, dashboard y exportacion XLSX.
- Preparacion de Compose, secretos montados, backup/restauracion y bundle reproducible de release.

Los indicadores nuevos usan solo registros confirmados. El dashboard muestra el motivo cuando un dato no se puede sostener: por ejemplo, alimento sin unidad kg confirmada o ventas historicas sin conversion conservada. Por ahora la cobertura de inventario queda no disponible cuando no se puede reconstruir esa conversion; costo total por huevo y margen por canal siguen pendientes de reglas de asignacion aprobadas. No se integra con SIFEN ni se ha desplegado a produccion.

## Entregas y estado

El roadmap contiene entregas numeradas 0-12 (0 es documental). Las entregas 0-10 constan como cerradas en el historial. D11/D12 tienen implementacion de despliegue/backup y bundle/attestation, pero no se consideran cerradas hasta que el SHA final pase todos los jobs de CI y la verificacion del bundle. Revisa [PROJECT_STATUS.md](PROJECT_STATUS.md) y los artefactos de calidad para la evidencia mas reciente; un resultado local no sustituye CI ni una restauracion fuera del equipo.

El sistema esta preparado para pruebas locales con datos sinteticos. La persona responsable del proyecto conserva el despliegue de produccion para una etapa posterior.

## Desarrollo local (Windows)

Con el entorno Python y Node instalados:

1. `scripts/db-up.ps1` inicia PostgreSQL local y prepara `avicola_pro` y `avicola_pro_test` con credenciales de prueba locales.
2. `scripts/migrate.ps1` aplica las migraciones. Configura `AVICOLA_SESSION_HMAC_KEY` con una clave sintetica solo para desarrollo.
3. Ejecuta `scripts/dev-backend.ps1` y `scripts/dev-frontend.ps1` en terminales separadas.
4. `scripts/check.ps1` ejecuta formato, lint, tipos, pruebas PostgreSQL/frontend y build.

La primera cuenta administrativa se crea con `avicola-pro bootstrap-admin`; la contrasena temporal se muestra una sola vez. No reutilices credenciales de prueba en otros entornos y nunca incluyas secretos reales en el ZIP o en Git.

## Documentacion

- [Arquitectura](ARCHITECTURE.md)
- [Base de datos](DATABASE.md)
- [Seguridad](SECURITY.md)
- [Estrategia de pruebas](TESTING_STRATEGY.md)
- [Roadmap](IMPLEMENTATION_PLAN.md)
- [Estado y evidencias](PROJECT_STATUS.md)
- [Cambios](CHANGELOG.md)
