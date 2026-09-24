# Estado de AVÍCOLA PRO

## Estado actual - 2026-09-24

Validacion local del cambio de indicadores: backend 316/316 pruebas aprobadas, cobertura total 80.09%; frontend 56/56, lint, TypeScript y build de produccion aprobados. Los indicadores implementados usan solo hechos confirmados y muestran como no disponibles los datos faltantes. No se calcula costo total por huevo ni margen de canal hasta aprobar sus politicas.

D11 y D12 siguen ABIERTAS: el run `36038140398` del SHA `413dbb6` construyo las imagenes, migro PostgreSQL y paso los gates Windows, PostgreSQL, dependencias, fuente y topologia Compose. Fallo despues porque el smoke ejecuto `alembic current` y el bootstrap directamente, omitiendo el cargador de secretos del contenedor; ambas llamadas ya pasan por el entrypoint y esperan otro CI. Trivy sigue fallando HIGH/CRITICAL en las tres imagenes; backup/restore y bundle de release aun estan bloqueados por el gate. No se desplego el sistema; no esta certificado para produccion.

## Última actualización

2026-09-23 - Entregas 0-10 cerradas. D11/D12 siguen sin cierre certificado: el último run `35890371500` pasó Windows, PostgreSQL, dependencias, código fuente y render Compose, pero `deployment-images` falló en las pruebas upstream de Restic, por lo que scans, Compose runtime, backup/restore y bundle/attestation fueron omitidos. En local, 246/246 pruebas backend pasaron en PostgreSQL 16 con 80,86 % cobertura; Ruff/formato/Mypy y pip-audit pasaron. Frontend lint, TypeScript, build y npm audit pasaron; Vitest local fue bloqueado por acceso de esbuild fuera del workspace, debe confirmarlo CI. Gate D12 ya valida bundle firmado, hashes, SBOM, SARIF, commit/ref/tag y edad. Falta CI fresco del SHA final. Sin despliegue; no hay registry digest, restore off-host ni aprobación RPO/RTO.

## Estado vigente - 2026-09-23

El plan tiene 13 entregas numeradas 0-12: la Entrega 0 es documental y las otras 12 son entregas de producto. Entregas 0-10 están cerradas. Se revalidó la idempotencia de pagos de Entrega 6 y se corrigió el BFF para Tesorería, Costos e Informes.

La Entrega 11 está implementada en la rama de trabajo: imágenes no-root, Caddy/TLS, Compose privado, migración previa, secretos externos, backup/restauración Restic y smoke autenticado. Existe roundtrip local sintético con nueve conciliaciones, clave errónea y corrupción rechazadas. No se debe contar la integración como verificada hasta que un run de `deployment-images` pase construcción, scans, Compose y backup/restore en la misma ejecución. El run `35890371500` falló construyendo Restic; la corrección local está pendiente de nuevo CI. No hay staging ni restore off-host.

La Entrega 12 incorpora bundle determinista, attestation GitHub y gate local autenticado. El gate comprueba timestamp de transparencia, repo/workflow/ref/commit, integridad del tar, tres archivos de imagen e IDs locales, SBOM, SARIF sin hallazgos HIGH/CRITICAL, hashes de reportes, Alembic `0010_costing` y tag local exacto. Localmente pasaron 246/246 pruebas backend (80,86 %), Ruff/formato/Mypy y pip-audit. Frontend lint/TypeScript/build/npm audit pasan; Vitest no pudo iniciar localmente porque esbuild no puede leer fuera del workspace. El estado previsto de RC es `ready_for_user_deployment`; piloto sigue bloqueado por restore off-host, RPO/RTO y responsables aprobados. No se publican imágenes ni se inventan registry digests. CI completo del SHA final, revisión manual RBAC y aceptación externa siguen pendientes.

Validacion local adicional 2026-09-22/23: migracion PostgreSQL 16.14 desde vacio y upgrade `0009_treasury` -> `0010_costing` aprobados en bases sinteticas desechables; smoke del frontend/API construidos localmente: 20 solicitudes, concurrencia 2, 0 errores, p50/p95 caliente 30/75 ms y p95 frio 769 ms. Smoke autenticado separado confirmó bootstrap, cambio de contraseña inicial y BFF login/me/logout sobre una DB temporal, eliminada tras la prueba: 20 solicitudes, 0 errores, p50 29 ms/p95 78 ms. No hay presupuesto aprobado. Auditorias npm/pip sin vulnerabilidades conocidas. Evidencia: `artifacts/quality/delivery-11/local-validation-2026-09-22.md`. La prueba de backup/restore local detallada se conserva aparte; no equivale a aceptacion off-host.

El registro durable de rechazos de permisos se integro localmente para `settings`, `inventory`, `production`, `purchasing`, `sales`, `treasury`, `costing` y `reporting`, con el mismo HTTP 403 y evidencia de actor, permiso, recurso y correlacion. La matriz de permisos por rol aun requiere revision manual del responsable del negocio; no se invento ni se considera aprobada.

## Cierre autoritativo de Entrega 10 - 2026-09-20

La primera entrega pendiente fue Dashboard y reportes. Se implementó el contexto `reporting`
con KPIs operativos de ventas, inventario, aves, AP, AR, caja y costos; rentabilidad paginada
con filtros de fecha; límites de offset/limit; consultas parametrizadas de solo lectura y
exclusión de borradores/reversiones. La exportación CSV está limitada y registra una auditoría
`report.export` con `reports.export`; las consultas requieren `reports.profitability.read`.

La UI añade el panel de dashboard same-origin y estados loading/error. No se creó migración:
reporting no agrega tablas y reutiliza `audit_events`; Alembic permanece en `0010_costing`.

Evidencia fresca: 157 pruebas backend verdes con 80,02 % de cobertura, PostgreSQL 16 real en
`127.0.0.1:55432`, 22 pruebas de migración/health verdes y head `0010_costing`; Ruff, formato,
Mypy sobre `src`, ESLint, TypeScript y build frontend verdes. Vitest está correctamente escrito
pero queda delegado al PowerShell externo por el `PermissionError` ambiental de esbuild al leer
rutas padre de `C:\Users`.

No se inició la Entrega 11. La siguiente entrega pendiente es Preparación del piloto.

## Cierre autoritativo de Entrega 9 — 2026-09-20

La primera entrega pendiente fue Costos y rentabilidad. Se implementó `costing` con eventos
confirmados e idempotentes, centros de costo, asignaciones exactas con residual de redondeo,
corridas versionadas, snapshots por lote/unidad, rentabilidad basada solo en hechos confirmados
y reversiones append-only mediante eventos compensatorios.
Las corridas cerradas y sus evidencias son inmutables mediante servicio y triggers PostgreSQL.

Se añadió la migración `0010_costing`, modelos al metadata central, endpoints protegidos por
sesión/CSRF/RBAC/auditoría y panel frontend same-origin. No hay imports desde Costing hacia
Compras, Ventas, Producción ni Tesorería; se consumen referencias neutrales tipo/UUID.

Evidencia fresca: 150 pruebas backend verdes, cobertura 80,04 %, PostgreSQL 16 real en
`127.0.0.1:55432`, migración limpia/roundtrip y 19 pruebas de migración verdes; Ruff, formato,
mypy sobre `src`, ESLint, TypeScript y build frontend verdes. `pip-audit` no encontró
vulnerabilidades publicadas auditables y `npm audit --audit-level=high` no encontró vulnerabilidades.
Vitest está escrito correctamente pero queda delegado al PowerShell externo por el `PermissionError`
ambiental de esbuild al leer rutas padre de `C:\Users`.

No se inició la Entrega 10. La siguiente entrega pendiente es Dashboard + reportes.

## Cierre autoritativo de Entrega 8 — 2026-09-20

La primera entrega pendiente fue Caja y cierres. Se implementaron cuentas de caja, sesiones
con única apertura activa por cuenta, ingresos/egresos, transferencias atómicas, cierres con
esperado/contado/diferencia, reapertura autorizada y reversión compensatoria append-only.
Los egresos y transferencias se bloquean si dejarían saldo negativo.
La API usa sesión opaca, CSRF, RBAC y auditoría; la UI incorpora el panel seguro de Tesorería.

Se añadió la migración PostgreSQL `0009_treasury` y los modelos se registran en el metadata
central. La jornada se probó sobre PostgreSQL real con apertura, movimiento, transferencia,
cierre, reapertura, idempotencia y reversión.

Evidencia fresca: 123 pruebas backend del gate funcional con cobertura 80,07 %, migraciones
limpias/roundtrip aisladas con 18 pruebas verdes, Ruff y formato verdes, mypy verde sobre
`src`, ESLint, TypeScript y build frontend verdes. Vitest está correctamente escrito, pero
su ejecución queda delegada al PowerShell externo por el `PermissionError` de esbuild al leer
rutas padre de `C:\Users`. No se inició la Entrega 9.

## Cierre autoritativo de Entrega 7 — 2026-09-19

La primera entrega pendiente fue Ventas y cuentas por cobrar. Se implementaron pedidos,
entregas parciales con salida atómica de inventario, comprobantes comerciales internos no
fiscales/no electrónicos, snapshots de cliente, numeración PostgreSQL bajo lock, desglose
exento/IVA 5%/IVA 10%, cuentas por cobrar, cobros idempotentes y notas de crédito con límite
acumulado y compensación de AR. `DisabledFiscalProvider` no realiza red, DNS ni persistencia.

Se añadió la migración PostgreSQL `0008_sales`, modelos compartidos, API protegida con sesión,
CSRF, RBAC y auditoría, BFF same-origin y panel frontend de Ventas. No se inició la Entrega 8.

Evidencia fresca: PostgreSQL 16 real en `127.0.0.1:55432`, migración desde base vacía y
roundtrip hasta `0008_sales (head)`, 133 pruebas backend verdes, cobertura 80,03 %, Ruff,
formato, Mypy y arquitectura verdes; npm audit sin vulnerabilidades, pip-audit sin
vulnerabilidades auditables y ESLint, TypeScript y build frontend verdes. Vitest está escrito
correctamente pero su ejecución queda delegada al PowerShell externo por el `PermissionError`
ambiental de esbuild al leer rutas padre de `C:\Users`.

## Estado global

**Estado histórico al 2026-09-20:** Entrega 9 completada y la primera pendiente era la Entrega 10. Queda supersedido por el estado vigente de 2026-09-22: Entrega 11 activa, Entrega 12 en curso.

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

## Estado histórico al cierre de Entrega 6 - 2026-09-19

Al cierre de esta fecha, Entrega 6 estaba completada y la primera pendiente era Entrega 7. Esta
sección y las notas de Entrega 2 que siguen debajo son históricas; el estado vigente al
2026-09-22 aparece al inicio del documento y supersede estas referencias.

**Entrega 2: Identidad, RBAC y Auditoría base.** Arquitectura oficial: sesión opaca
completamente estatal, cookie HttpOnly/SameSite=Lax, Secure configurable, CSRF separado,
rotación con detección de reutilización, revocación inmediata, RBAC backend, auditoría
transaccional y bootstrap idempotente del administrador inicial.

Rama activa en aquella continuidad: `delivery/02-identity-rbac-audit`. La restricción de no
iniciar Entrega 3 correspondía a esa sesión y ya no aplica al estado vigente.

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
