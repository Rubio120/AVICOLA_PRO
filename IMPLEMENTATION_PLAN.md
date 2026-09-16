# AVÍCOLA PRO Implementation Plan

> **Para agentes ejecutores:** usar `superpowers:subagent-driven-development` (recomendado) o `superpowers:executing-plans`. Cada entrega se implementa con TDD, revisión y commit independiente. Este documento es un roadmap; antes de ejecutar cada fase se crea un plan técnico de tareas y archivos con pruebas concretas.

**Objetivo:** construir AVÍCOLA PRO como sistema empresarial estable para una sola empresa, entregando capacidades verticales pequeñas y verificables.

**Arquitectura:** monolito modular hexagonal, FastAPI y PostgreSQL con frontend Next.js separado. Las operaciones críticas usan transacciones locales, ledgers inmutables, autorización y auditoría.

**Stack:** Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL 16+, Next.js/React/TypeScript, Pytest, Testcontainers, Vitest y Playwright.

**Especificación:** `ARCHITECTURE.md`, `DATABASE.md`, `SECURITY.md` y `TESTING_STRATEGY.md`.

## Restricciones globales

- Una sola empresa; sin `company_id` general ni multiempresa en V1.
- Aves agregadas por lote.
- Stock negativo prohibido.
- Promedio ponderado móvil.
- Confirmados inmutables; correcciones compensatorias.
- Documento comercial interno independiente del fiscal externo.
- Sin integración SIFEN real en V1; usar `DisabledFiscalProvider`.
- Toda mutación crítica exige autorización, auditoría, idempotencia cuando corresponda y transacción.
- Dinero/cantidades usan `Decimal`/`numeric`, no `float`.
- UTC en persistencia y `America/Asuncion` en presentación.
- No cerrar fases con pruebas fallidas ni defectos críticos/altos.

## Flujo de cada entrega

1. Confirmar criterios e invariantes.
2. Crear plan técnico de la entrega y matriz de permisos/pruebas.
3. Escribir pruebas fallidas.
4. Implementar el mínimo vertical backend, migración y UI.
5. Ejecutar pruebas unitarias, integración y negativas.
6. Revisar seguridad, esquema y observabilidad.
7. Corregir fallos y repetir el conjunto completo pertinente.
8. Actualizar documentación, estado y changelog.
9. Revisión integral y commit pequeño.

Antes de comenzar cada entrega, `PROJECT_STATUS.md` registra una persona accountable como Owner y otra como Approver. Los perfiles/agentes indicados en cada sección son obligatorios, pero no sustituyen responsabilidad humana. La evidencia del gate se guarda en `artifacts/quality/delivery-<n>/` o en el artefacto equivalente de CI y se enlaza desde `PROJECT_STATUS.md`.

| Entrega | Owner técnico recomendado | Aprobador del gate |
|---|---|---|
| 0-1 | Backend/Platform lead | Architect reviewer |
| 2 | Identity/Security lead | Security auditor |
| 3 | Backend/Data lead | Architect reviewer |
| 4 | Inventory/Data lead | Security + test reviewer |
| 5 | Production domain lead | Comprehensive reviewer |
| 6 | Purchasing domain lead | Security + test reviewer |
| 7 | Sales domain lead | Security + architect reviewer |
| 8 | Treasury domain lead | Security + comprehensive reviewer |
| 9 | Costing domain lead | Data/performance reviewer |
| 10 | Reporting/UI lead | Performance + security reviewer |
| 11 | Deployment lead | Security + comprehensive reviewer |
| 12 | Release lead | Product owner + comprehensive reviewer |

## Entrega 0 — Base documental

**Alcance:** documentación de arquitectura, datos, seguridad, instalación, testing, plan y estado.

**Criterios de aceptación:**

- Decisiones oficiales y ADR consistentes.
- Todos los módulos, relaciones e invariantes identificados.
- Fases con gates, pruebas y responsables.
- Revisión arquitectónica sin hallazgos críticos/altos.

**Pruebas/evidencia:** enlaces Markdown válidos, ausencia de placeholders, revisión cruzada de requisitos y `git diff --check`.

**Especialistas:** backend architect, database architect, security auditor, test architect, comprehensive/architect reviewer.

## Entrega 1 — Base técnica reproducible

**Alcance:** estructura backend/frontend, toolchains y lockfiles, configuración tipada, Docker Compose con PostgreSQL, Alembic inicial, CI, logging, Problem Details, health/readiness y pruebas arquitectónicas.

**Criterios de aceptación:**

- Instalación limpia reproducible desde README/INSTALLATION.
- Backend y frontend arrancan; health/readiness reflejan estado real de BD.
- Migraciones aplican desde base vacía.
- Configuración insegura o incompleta falla al inicio.
- Límites de importación modular se verifican automáticamente.
- Versiones exactas, gestor Node y matriz de compatibilidad quedan fijados en lockfiles y documentación.

**Pruebas obligatorias:** lint, tipos, unitarias de configuración/errores, integración health+PostgreSQL, migración limpia, builds backend/frontend y smoke test.

**Especialistas:** Python/FastAPI, frontend, deployment engineer, test automator, architect reviewer.

**Commit sugerido:** `build: establish reproducible application foundation`.

## Entrega 2 — Identidad, RBAC y auditoría base

**Alcance:** usuarios, roles, permisos, sesiones rotatorias, login/logout, bootstrap admin, policy service, eventos de seguridad y auditoría append-only.

**Criterios de aceptación:**

- Contraseñas Argon2id y cookies seguras configurables.
- Backend deniega por defecto y comprueba permisos concretos.
- Sesiones expiran, rotan y se revocan correctamente.
- Login, denegaciones y cambios de permisos quedan auditados.
- Seed de permisos y bootstrap son idempotentes.

**Pruebas obligatorias:** hash/verify, login válido/inválido, rate limit, refresh/reutilización, logout, usuario deshabilitado, CSRF, matriz 401/403, cambios RBAC, auditoría atómica e integración PostgreSQL.

**Especialistas:** FastAPI, security auditor, threat-modeling expert, test automator, frontend.

**Commit sugerido:** `feat: add identity access control and audit foundation`.

## Entrega 3 — Configuración, terceros y catálogo

**Alcance:** perfil singleton, monedas, unidades, impuestos versionados, timbrados, secuencias, clientes, proveedores, categorías, productos, granjas, galpones y depósitos.

**Criterios de aceptación:**

- Solo existe un perfil empresarial incluso ante creación concurrente; V1 rechaza moneda transaccional distinta de PYG.
- Tasas conservan vigencia histórica.
- Secuencias asignan números únicos sin reciclarlos.
- Maestros usados se desactivan, no se borran.
- UI ofrece tablas, formularios, filtros, paginación y estados consistentes.

**Pruebas obligatorias:** singleton concurrente, rechazo multimoneda, constraints, vigencias, secuencia concurrente, optimistic locking, permisos CRUD, búsqueda/paginación, desactivación y auditoría.

**Especialistas:** backend/database, frontend, test automator, security auditor.

**Commit sugerido:** `feat: add company settings parties and catalog`.

## Entrega 4 — Inventario transaccional

**Alcance:** lotes de inventario, documentos, movimientos, balances, entrada, salida, transferencia, ajuste, promedio ponderado, idempotencia y reversión.

**Criterios de aceptación:**

- Ninguna confirmación produce stock negativo.
- Ledger y balances se reconcilian siempre.
- Transferencia registra ambos lados atómicamente.
- Promedio ponderado produce resultados reproducibles.
- Cantidad y valor del bucket depósito-producto-lote reconcilian; reversiones conservan costo histórico.
- Confirmados no pueden editarse/borrarse.
- Ajustes/reversiones requieren permiso y motivo.

**Pruebas obligatorias:** promedio/precisión, saldo cero, entrada gratuita, transferencia, devolución, ejemplo `+10@10,+10@20,-10@15,reversión`, variación de costo, reconciliación cantidad/valor, UPDATE/DELETE directo, rollback, constraints, dos salidas concurrentes, deadlock/reintento, idempotencia, doble reversión, permisos, auditoría y E2E básico.

**Especialistas:** database/backend architect, Python/FastAPI, test/concurrency automator, security auditor, performance engineer.

**Commit sugerido:** `feat: implement auditable inventory ledger`.

## Entrega 5 — Producción avícola

**Alcance:** lotes productivos, asignación a galpones, saldo de aves, mortalidad, ajustes, alimentación y registros diarios.

**Criterios de aceptación:**

- Aves vivas nunca son negativas.
- Ocupación respeta capacidad y períodos.
- Mortalidad y ajustes confirmados son inmutables/reversibles.
- Entrada, traslado, venta, faena y salida de aves usan eventos tipados; el registro diario es solo observación.
- Activar un lote genera un único evento INITIAL; cierre exige saldo cero o ajuste autorizado.
- Alimentación descuenta inventario y genera costo en una transacción.
- Indicadores se reconstruyen desde eventos.

**Pruebas obligatorias:** cálculo/reconciliación de aves, entrada/salida/traslado/faena/cierre, capacidad y asignación concurrente, mortalidad concurrente, reversión/doble reversión, UPDATE/DELETE directo, consumo sin stock, integración inventario/costos, permisos, auditoría y E2E de alimentación.

**Especialistas:** domain/backend architect, database, test automator, frontend, comprehensive reviewer.

**Commit sugerido:** `feat: add flock production and feed tracking`.

## Entrega 6 — Compras y cuentas por pagar

**Alcance:** órdenes, aprobación, recepciones parciales, documentos de proveedor, AP, pagos y reversiones.

**Criterios de aceptación:**

- No hay sobre-recepción en V1.
- Recepción actualiza orden y stock atómicamente.
- Obligación y pagos conservan saldo exacto.
- No se sobreaplica un pago.
- Pago confirmado genera caja y su reversión compensa todo el flujo.

**Pruebas obligatorias:** máquina de estados, recepción parcial/completa, recepción concurrente, stock/costo, AP, pagos parciales/N:M, sobreaplicación, idempotencia, reversión, autorización y E2E completo.

**Especialistas:** backend/database, FastAPI, frontend, test automator, security auditor.

**Commit sugerido:** `feat: implement purchasing and accounts payable`.

## Entrega 7 — Ventas y cuentas por cobrar

**Alcance:** pedidos, entregas, documento comercial interno, numeración/timbrado snapshot, IVA, AR, cobros, notas de crédito, anulaciones y puerto fiscal deshabilitado.

**Criterios de aceptación:**

- Backend recalcula exentas, bases 5/10, IVA y total.
- Pedido/entrega/documento soportan relaciones parciales controladas.
- Emisión asigna numeración única y genera AR.
- NC acumuladas no exceden el documento original.
- Devoluciones generan inventario/caja relacionados según caso.
- No se realizan llamadas fiscales externas.
- Estado fiscal no condiciona stock, AR o caja.
- La UI identifica claramente el comprobante como interno y no fiscal/electrónico.

**Pruebas obligatorias:** golden tests de IVA/redondeo, payload adulterado, numeración concurrente, emisión idempotente, entrega/stock, AR/cobros, NC total/parcial y concurrente, anulación/reversión, UPDATE/DELETE directo, `DisabledFiscalProvider` sin red/DNS/persistencia, permisos, auditoría y E2E completo.

**Especialistas:** backend architect, FastAPI/Python, frontend, database, test automator, security auditor, future-integration reviewer.

**Commit sugerido:** `feat: add internal sales documents and receivables`.

## Entrega 8 — Caja y cierres

**Alcance:** cuentas, sesiones, apertura, ingresos, egresos, transferencias, cierre, diferencia, reapertura autorizada y reversión.

**Criterios de aceptación:**

- Solo una sesión abierta por caja.
- Transferencias tienen ambos movimientos atómicos.
- Cierre registra esperado, contado y diferencia sin reescribir movimientos.
- Movimientos posteriores al cierre siguen política explícita.
- Reversiones conservan enlace, motivo y auditoría.

**Pruebas obligatorias:** unique sesión abierta, conciliación, transferencia/rollback, cierre frente a movimiento concurrente, reapertura autorizada, reversión, permisos y E2E de jornada.

**Especialistas:** backend/database, test concurrency, security auditor, frontend, comprehensive reviewer.

**Commit sugerido:** `feat: implement auditable cash operations and closing`.

## Entrega 9 — Costos y rentabilidad

**Alcance:** eventos, centros, asignaciones, corridas versionadas, snapshots por lote/ave y márgenes.

**Criterios de aceptación:**

- Asignaciones suman exactamente el costo origen.
- Corridas cerradas son reproducibles e inmutables.
- Costo por ave gestiona divisor cero explícitamente.
- Alimentación, compras y ajustes llegan por contratos definidos.
- Rentabilidad usa solo documentos/costos confirmados.

**Pruebas obligatorias:** promedio ponderado, asignaciones y redondeo, versiones, reversión, costo por lote/ave, datos tardíos, permisos, integración y golden datasets.

**Especialistas:** domain/backend, database/performance, test automator, frontend/reporting reviewer.

**Commit sugerido:** `feat: add versioned production costing and profitability`.

## Entrega 10 — Dashboard y reportes

**Alcance:** KPI, producción, inventario, compras, ventas, cuentas, caja, costos, rentabilidad y exportaciones auditadas.

**Criterios de aceptación:**

- Cada KPI tiene definición y fuente documentada.
- Filtros/paginación/límites impiden consultas sin control.
- Reportes respetan permisos y solo muestran confirmados.
- Exportaciones quedan auditadas.
- Consultas críticas cumplen presupuesto acordado.

**Pruebas obligatorias:** datasets dorados, reconciliación con ledgers, permisos/fuga de datos, paginación/filtros, exportación, N+1, explain/analyze y E2E de dashboard.

**Especialistas:** reporting/database, frontend, performance engineer, security auditor, test automator.

**Commit sugerido:** `feat: add operational dashboards and reports`.

## Entrega 11 — Preparación de piloto

**Alcance:** imágenes productivas, proxy/TLS, CI/CD, alertas, backup, restore, runbooks, hardening y pruebas de carga básicas.

**Criterios de aceptación:**

- Instalación limpia documentada y repetible.
- Backup cifrado y copia externa configurados.
- Restauración verificada con conciliación y arranque.
- RPO, RTO, retención, owner y aprobador están definidos; la evidencia procede de un artefacto off-host.
- Secretos externos, TLS, contenedores no-root y BD privada.
- Runbooks de despliegue, rollback, incidente y restore ensayados.
- Cero hallazgos críticos/altos.

**Pruebas obligatorias:** build reproducible, smoke staging, migración desde versión anterior, backup/restore off-host, copia corrupta/clave errónea, E2E crítico, SAST/dependencias/secretos/imagen, carga básica y rollback ensayado.

**Evidencia/owner:** deployment engineer produce `artifacts/quality/<release>/`; security auditor y comprehensive reviewer aprueban.

**Especialistas:** deployment engineer, security auditor, performance engineer, test automator, comprehensive reviewer.

**Commit sugerido:** `ops: prepare verified pilot deployment`.

## Entrega 12 — Gate final y piloto

**Alcance:** revisión integral, corrección de defectos, aprobación operativa y release candidate.

**Criterios de aceptación:**

- Suite completa verde con evidencia fresca.
- Migraciones limpia y upgrade verificadas.
- Restore drill aprobado y RPO/RTO registrados.
- Matriz RBAC y auditoría revisadas manualmente.
- No hay errores críticos/altos conocidos; medios tienen responsable y fecha.
- Documentación y `PROJECT_STATUS.md` reflejan el release exacto.

**Pruebas obligatorias:** toda la matriz de `TESTING_STRATEGY.md`, revisión de seguridad, rendimiento, migraciones, instalación limpia, backup/restore y comprehensive review.

**Especialistas:** todos; cierre coordinado por comprehensive reviewer y deployment engineer.

**Commit sugerido:** `release: prepare avicola pro pilot`.

## Estrategia Git

- La implementación se realizará en rama de trabajo aislada cuando comience.
- Un commit por entrega verificable o subentrega revisable.
- Mensajes Conventional Commits.
- No reescribir cambios ajenos ni hacer commits con pruebas rotas.
- Tags solo después del gate de release.
- Cada commit funcional actualiza pruebas; cada fase actualiza documentación, changelog y estado.

## Primer módulo recomendado

Tras la base técnica, implementar **Identidad, RBAC y Auditoría base**. Es el primer módulo de negocio porque todos los demás necesitan actor autenticado, autorización granular, correlación y evidencia transaccional; añadirlo después obligaría a rehacer endpoints y pruebas.
