# Estado de AVÍCOLA PRO

## Última actualización

2026-09-18 — Entrega 2 implementada y verificada; Vitest queda delegado al PowerShell externo por la restricción de esbuild del sandbox.

## Estado global

**Actualización 2026-09-19:** Entrega 5 (Producción avícola) completada y revalidada en este
working tree. No se inició la Entrega 6.

**ActualizaciÃ³n 2026-09-18:** Entrega 3 (ConfiguraciÃ³n, terceros y catÃ¡logo) completada en
working tree y revalidada. No iniciar Entrega 4 en esta ejecuciÃ³n.

**Entrega 2 / Identidad, RBAC y Auditoría completada.** La Entrega 1 permanece cerrada y
respaldada. La autenticación/sesiones se amplió con administración protegida de usuarios,
roles y permisos, auditoría funcional transaccional, eventos de seguridad y una UI de identidad
con BFF same-origin, cambio obligatorio de contraseña, restauración de sesión y logout.

Fuente maestra de continuidad: `PROJECT_CONTEXT.md`. Debe actualizarse junto con este
archivo después de cada entrega importante y antes de terminar una sesión; luego se debe
crear commit y hacer push sin incluir secretos.

## Completado

- [x] Inspección del repositorio y Git.
- [x] Inventario de especialistas/plugins instalados.
- [x] Requisitos y alcance inicial de V1.
- [x] Arquitectura base aprobada.
- [x] Modelo lógico inicial.
- [x] Mapa de módulos y dependencias.
- [x] Estrategia de seguridad y RBAC.
- [x] Estrategia de pruebas y gates.
- [x] Plan incremental de entregas.
- [x] Estrategia de backups y restauración.
- [x] Contexto maestro de continuidad consolidado en `PROJECT_CONTEXT.md`.
- [x] Primera revisión arquitectónica independiente y corrección de hallazgos.
- [x] Segunda/tercera revisión arquitectónica sin hallazgos críticos/altos (architect reviewer, 2026-09-16).
- [x] Base técnica reproducible (Entrega 1; gate local verde el 2026-09-16).
- [x] Código técnico funcional: health/readiness, configuración, errores, logging, migraciones y UI técnica.
- [x] Entrega 2: Identidad, RBAC y Auditoría.
- [x] Entrega 3: Configuración, terceros y catálogo.
- [x] Entrega 4: Inventario transaccional.
- [x] Entrega 5: Producción avícola.

## Cierre autoritativo de Entrega 5 — 2026-09-19

La primera entrega pendiente fue la Entrega 5 — Producción avícola. Se implementó la migración
PostgreSQL `0005_production`, lotes y asignaciones a galpones, saldo bloqueable de aves, eventos
INITIAL/mortalidad/ajuste, registros diarios, cierre autorizado y consumo de alimento integrado
atómicamente con el ledger de inventario. La API aplica sesión, CSRF y RBAC; la UI muestra saldos
de lotes con estados seguros.

Evidencia fresca: PostgreSQL 16 real en `127.0.0.1:55432`, migración limpia y roundtrip, 118
pruebas backend, cobertura 80,05 %, Ruff/formato/Mypy y arquitectura verdes; ESLint, TypeScript
y build frontend verdes. Vitest está correctamente escrito pero delegado al PowerShell externo
por el `PermissionError` conocido de esbuild al leer rutas padre de `C:\Users`. No se inició la
Entrega 6.

## Decisiones oficiales

- Una sola empresa y sin multiempresa V1.
- Aves por lote.
- Stock negativo prohibido.
- Promedio ponderado móvil.
- Ledgers y documentos confirmados inmutables.
- Correcciones compensatorias.
- Documento comercial interno separado del fiscal externo.
- Sin SIFEN real V1; puerto/adaptador preparado.
- Seguridad, permisos, auditoría y trazabilidad obligatorios.
- Backup restaurado y verificado antes del piloto.

## Entrega actual

**Estado vigente:** Entrega 6 completada; la primera pendiente es la Entrega 7. Las notas
históricas de Entrega 2 que siguen debajo se conservan como referencia y quedan supersedidas
por el cierre autoritativo fechado 2026-09-19.

**Entrega 2: Identidad, RBAC y Auditoría base.** Arquitectura oficial: sesión opaca
completamente estatal, cookie HttpOnly/SameSite=Lax, Secure configurable, CSRF separado,
rotación con detección de reutilización, revocación inmediata, RBAC backend, auditoría
transaccional y bootstrap idempotente del administrador inicial.

Rama activa: `delivery/02-identity-rbac-audit`. No iniciar Entrega 3 sin aprobación explícita.

Evidencia local fresca del 2026-09-18:

- backend completo sobre PostgreSQL 16 real: 95 pruebas, cobertura 86,24 %, Ruff, formato y Mypy verdes;
- integración administrativa: login, RBAC, creación/desactivación de usuarios, revocación de sesiones, roles y auditoría verificados;
- frontend: ESLint, TypeScript y build Next.js verdes; Vitest quedó escrito y delegado al PowerShell externo por acceso denegado a `../..` desde esbuild;
- migración PostgreSQL desde base vacía, downgrade/upgrade y health checks verdes;
- `pip-audit` (caché `.cache/pip-audit`), `npm audit --audit-level=high` y búsqueda de secretos sin hallazgos reales;

- clean install: CPython 3.13.15/79 paquetes y npm/471 paquetes desde lockfiles;
- Alembic: base vacía a `0001_baseline (head)` y roundtrip validado;
- backend: Ruff y mypy verdes; 36 pruebas, cobertura 92,09 %;
- frontend: ESLint y TypeScript verdes; 10 pruebas, cobertura 100 %; build Next.js verde;
- dependencias: `pip-audit` y `npm audit --audit-level=high`, cero vulnerabilidades conocidas;
- smoke: `/health/live`, `/health/ready`, `/openapi.json` y `/` respondieron HTTP 200.

El bloque publicado de revisión final corrige portabilidad Alembic en Linux, validación de
URL PostgreSQL productiva, matriz/ciclos de dependencias hexagonales, correlación de logs
y whitespace histórico. La revisión no dejó hallazgos críticos/importantes de código pendientes.

Evidencia documental actual: documentos de arquitectura y continuidad, verificación local de enlaces/whitespace/placeholders y revisión independiente. La evidencia local de Entrega 1 se resume arriba; GitHub Actions procesa el commit publicado. `artifacts/quality/` mantiene por ahora solo su marcador versionado.

## Especialistas disponibles

- Full-stack orchestration: testing, seguridad, rendimiento y despliegue.
- Backend architect, FastAPI/Python specialists.
- Frontend developer.
- Test automator/TDD orchestrator.
- Security auditor y threat-modeling expert.
- Debugger.
- Architect/code/comprehensive reviewers.

## Riesgos abiertos

1. Validar reglas paraguayas exactas de redondeo y representación de IVA antes de Ventas; los documentos V1 se rotulan como internos, no fiscales/electrónicos.
2. Confirmar cuándo se reconoce el costo de compra: recepción o documento del proveedor.
3. Definir política exacta entrega-facturación para entregas parciales/consolidadas.
4. Acordar RPO, RTO y retención final antes del piloto.
5. Acordar volumen de datos y concurrencia objetivo para presupuestos de rendimiento.
6. Definir manejo funcional de reapertura de caja y autorizaciones de alto impacto.
7. Definir métricas productivas adicionales —huevos, peso, conversión— antes de ampliar `production_events`.

Ninguno de estos riesgos impide construir la base técnica o Identidad; deben resolverse antes de la fase afectada.

## Protocolo de continuidad

## Cierre autoritativo de Entrega 6 — 2026-09-19

La primera entrega pendiente identificada en este working tree fue la Entrega 6 — Compras y
cuentas por pagar. Quedó implementada sin commit ni push. Incluye migraciones PostgreSQL
`0006_purchasing` y `0007_supplier_document_lines`, órdenes con aprobación, recepciones
parciales con lotes y actualización atómica de inventario, documentos de proveedor, AP,
pagos N:M, idempotencia, saldos exactos y reversión compensatoria con `cash_movement_id`.

La API aplica sesión, CSRF, RBAC y auditoría; la UI incorpora consulta segura de órdenes. Se
añadieron pruebas unitarias, de rutas, migración limpia/roundtrip e integración PostgreSQL
real para el flujo orden → recepción → stock → AP → pago → reversión.

Evidencia fresca: 125 pruebas backend verdes, cobertura 80,02 %, Ruff/formato/Mypy y reglas
arquitectónicas verdes; PostgreSQL 16 real en `127.0.0.1:55432` en
`0007_supplier_document_lines (head)`; health/migraciones verdes; ESLint, TypeScript y build
frontend verdes; `npm audit` sin vulnerabilidades y `pip-audit` sin vulnerabilidades conocidas.
Vitest está correctamente escrito pero su ejecución queda delegada al PowerShell externo por
el `PermissionError` ambiental de esbuild al leer rutas padre de `C:\Users`.

No se inició la Entrega 7. La siguiente entrega pendiente es Ventas + cuentas por cobrar.

## Cierre autoritativo de Entrega 4 — 2026-09-19

La primera entrega pendiente identificada fue la Entrega 4 — Inventario transaccional, porque las
Entregas 2 y 3 ya estaban implementadas en el estado actual del worktree. La Entrega 4 quedó
implementada sin commit ni push. Esta sección supersede las notas históricas que indicaban no
iniciar Entrega 4.

Se implementó la migración PostgreSQL `0004_inventory`, lotes, documentos, líneas, ledger
append-only, saldos por bucket depósito-producto-lote, promedio ponderado móvil, transferencias,
confirmación idempotente, reversión compensatoria y variaciones de costo. La API está protegida
por sesión, CSRF, RBAC y auditoría; la UI incorpora consulta de saldos y registro de entradas.

Evidencia fresca: PostgreSQL 16 real en `127.0.0.1:55432`, 109 tests backend, cobertura 80,66 %,
Ruff/formato/Mypy, migración desde base vacía y roundtrip, health/readiness/OpenAPI HTTP 200,
`npm audit` sin vulnerabilidades, `pip-audit` sin vulnerabilidades conocidas auditables, ESLint,
TypeScript y build frontend verdes. Vitest está correctamente escrito pero delegado al PowerShell
externo por el `PermissionError` conocido de esbuild al leer rutas padre de `C:\Users`.

No se hizo commit, push, reset ni se alteraron datos reales. No se inició la Entrega 5.

## Cierre de Entrega 3 - 2026-09-18

La Entrega 3 quedÃ³ implementada y revalidada sin commit ni push. Se reforzaron constraints,
normalizaciÃ³n de cÃ³digos, secuencias PostgreSQL bajo lock, optimistic locking y desactivaciÃ³n
auditable de productos, junto con la API protegida y el panel de catÃ¡logo.

Gates frescos: 103 pruebas backend, cobertura 81,26 %, Ruff/formato/Mypy, migraciÃ³n limpia y
roundtrip PostgreSQL 16 real, health checks, ESLint, TypeScript, build, pip-audit y npm audit.
Vitest queda delegado al PowerShell externo por el PermissionError conocido de esbuild contra
rutas padre de C:\Users. No se iniciÃ³ la Entrega 4.

## Verificación de Entrega 3 - 2026-09-18

La primera entrega pendiente fue la Entrega 3: configuración, terceros y catálogo. Quedó implementada en este working tree sin commit ni push. Incluye la migración `0003_settings_parties_catalog`, modelos PostgreSQL compartidos, reglas PYG/vigencias/numeración, API protegida con sesión/CSRF/RBAC/auditoría y panel de catálogo con búsqueda, formulario y paginación.

Evidencia fresca: PostgreSQL 16 real en `127.0.0.1:55432`, migración limpia y roundtrip; 100 tests backend y cobertura 81.58 %; Ruff, formato y Mypy verdes; ESLint, TypeScript y build frontend verdes; `npm audit` y `pip-audit` sin vulnerabilidades conocidas auditables. Vitest queda delegado al PowerShell externo por el `PermissionError` conocido de esbuild contra rutas padre de `C:\Users`.

No se inició la Entrega 4. `AGENTS.md` no existe en esta raíz. El siguiente paso autorizado es revisión/aceptación externa de esta entrega.

## Verificación de continuidad — 2026-09-18

La primera entrega pendiente fue la Entrega 3 — Configuración, terceros y catálogo. Se añadió
la migración PostgreSQL `0003_settings_parties_catalog`, modelos compartidos, reglas de PYG,
vigencias fiscales, singleton empresarial, secuencias, terceros, catálogo, granjas, galpones y
depósitos, además de la API protegida, auditoría funcional y panel frontend de catálogo.

Gates ejecutados en este worktree: 98 pruebas backend verdes, cobertura 81,30 %, Ruff/Mypy
verdes, migración limpia/upgrade/downgrade y seed idempotente en PostgreSQL 16 real sobre
`127.0.0.1:55432`, health/readiness cubiertos por la suite, ESLint/TypeScript/build verdes,
`npm audit` sin vulnerabilidades y `pip-audit` sin vulnerabilidades conocidas para dependencias
publicadas. Vitest quedó delegado al PowerShell externo por la denegación ambiental conocida de
esbuild al leer rutas padre de `C:\Users`.

No se hizo commit, push, reset ni se inició la Entrega 4.

## Verificación de continuidad — 2026-09-17

La revisión independiente confirmó y se corrigieron los riesgos de revocación al desactivar
usuarios, auditoría de lecturas/denegaciones, snapshots de roles y uso directo de la URL interna
desde el navegador. La superficie administrativa incluye usuarios, roles, permisos y auditoría;
la UI usa un proxy same-origin server-side.

El gate PostgreSQL se completó sobre `127.0.0.1:55432` con PostgreSQL 16 real. No se
sustituyó PostgreSQL por SQLite ni se redujo cobertura o seguridad.

El commit local de este registro también quedó bloqueado porque Git no puede crear
`.git/worktrees/delivery-02-identity-rbac-audit/index.lock` bajo las restricciones de
permisos del entorno; no se forzaron permisos ni se hizo push.

Una sesión futura debe leer, en orden:

1. `PROJECT_CONTEXT.md` y `PROJECT_STATUS.md`.
2. `README.md`, `ARCHITECTURE.md` y sus ADR.
3. `DATABASE.md` y `SECURITY.md`.
4. `TESTING_STRATEGY.md` e `INSTALLATION.md`.
5. La entrega correspondiente de `IMPLEMENTATION_PLAN.md`.
6. `CHANGELOG.md`, ADR adicionales, artefactos de calidad y `git log`.

Si código y documentación difieren, detenerse, documentar la discrepancia y solicitar revisión; no cambiar una decisión oficial silenciosamente.
