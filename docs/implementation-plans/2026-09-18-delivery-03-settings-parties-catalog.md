# Entrega 3 - Plan de implementación

> Ejecución autónoma en el worktree actual. No se harán commits ni se avanzará a Entrega 4.

**Objetivo:** entregar configuración, terceros y catálogo sobre PostgreSQL, con maestros desactivables, auditoría y UI operativa básica.

**Arquitectura:** `settings`, `parties` y `catalog` son módulos hexagonales que comparten la metadata SQLAlchemy y los puertos de auditoría/RBAC existentes. La API usa DTOs estrictos, paginación acotada y permisos granulares; las mutaciones se ejecutan en una sola UoW y dejan eventos funcionales.

**Gates:** pruebas RED/GREEN, migración limpia y roundtrip en PostgreSQL 16, suite backend/cobertura, Ruff, Mypy, frontend/Vitest (delegado por la restricción conocida de esbuild), ESLint, TypeScript, build, health checks y revisión de seguridad.

## Tareas

- [x] Modelos y migración: `company_profile`, monedas, unidades, impuestos, timbrados, secuencias, métodos de pago, parties, categorías, productos, granjas, galpones y depósitos; constraints, índices, seed idempotente y protección histórica.
- [x] Dominio y aplicación: normalización, PYG, vigencias, singleton, secuencias bajo lock, desactivación y validación de optimismo.
- [x] API protegida: endpoints de consulta/alta para configuración, terceros y catálogo con permisos, búsqueda, offset/limit, CSRF y auditoría.
- [x] Frontend: panel de catálogo con estados de carga, vacío, error, formulario y paginación.
- [x] Gates: integración PostgreSQL, suite completa, calidad, seguridad, migración desde vacío, health checks y revisión independiente.

## Evidencia

- PostgreSQL 16 real en `127.0.0.1:55432`: migración limpia, roundtrip y seed idempotente.
- Backend: 100 tests, cobertura 81.58 %, Ruff, formato y Mypy verdes.
- Frontend: ESLint, TypeScript y build verdes; Vitest escrito y delegado al PowerShell externo por el `PermissionError` ambiental de esbuild.
- Dependencias: `npm audit --audit-level=high` y `pip-audit --cache-dir .cache/pip-audit` sin vulnerabilidades conocidas auditables.
