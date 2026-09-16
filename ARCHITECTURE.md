# Arquitectura de AVÍCOLA PRO

## Estado y alcance

Este documento es la especificación arquitectónica oficial de V1. Cambiar una decisión marcada como oficial exige un ADR nuevo, revisión arquitectónica, análisis de migración y aprobación explícita.

## Decisiones oficiales de V1

1. Una sola empresa. `company_profile` será singleton y no se añadirá `company_id` a todas las tablas.
2. Aves gestionadas como cantidades por lote, no como individuos.
3. Stock negativo prohibido.
4. Valoración por promedio ponderado móvil.
5. Documentos confirmados inmutables.
6. Correcciones mediante anulaciones, notas o movimientos compensatorios enlazados al original.
7. Documento comercial interno y documento fiscal externo son agregados distintos.
8. V1 no integra SIFEN ni otro proveedor fiscal.
9. La integración fiscal futura usará un puerto propio y una capa anticorrupción.
10. V1 no es multiempresa.
11. Seguridad, autorización, auditoría y trazabilidad son obligatorias.
12. El piloto requiere backup y restauración verificada.

## Estilo arquitectónico

Se adopta un monolito modular con arquitectura hexagonal/clean por módulo:

```text
Next.js/React -> HTTPS JSON -> FastAPI /api/v1
                                  |
             API -> Aplicación -> Dominio -> Puertos
                                             |-- PostgreSQL
                                             |-- auditoría/outbox
                                             `-- proveedor fiscal
```

Reglas de dependencia:

- Dominio no importa FastAPI, SQLAlchemy ni componentes de infraestructura.
- Aplicación depende del dominio y de puertos, nunca de adaptadores concretos.
- Infraestructura implementa puertos y realiza mapeo ORM-dominio.
- API valida el transporte, autoriza y llama casos de uso; no contiene reglas de negocio.
- Un módulo no consulta tablas ni repositorios de otro módulo.
- La coordinación crítica es síncrona y transaccional mediante servicios de aplicación.
- Efectos no críticos se publican mediante outbox transaccional e idempotencia.
- No se adoptan microservicios, event sourcing o CQRS completo en V1.

## Tecnologías seleccionadas

| Área | Tecnología | Motivo |
|---|---|---|
| Backend | Python 3.13, FastAPI | API tipada, OpenAPI y ecosistema Python |
| Validación | Pydantic v2 | DTO y configuración estricta |
| Persistencia | SQLAlchemy 2.x, Psycopg 3 | Transacciones y PostgreSQL explícitos |
| Migraciones | Alembic | Esquema versionado y reproducible |
| Base de datos | PostgreSQL 16+ | Integridad, locks, índices y `numeric` |
| Frontend | Next.js, React, TypeScript | UI empresarial separada y cliente tipado |
| Estado remoto | TanStack Query | Caché, invalidación y estados de red |
| Formularios | React Hook Form, Zod | Validación consistente en UI |
| Estilos | Tailwind CSS, primitivas accesibles | Sistema visual consistente |
| Dependencias Python | uv | Entornos y lockfile reproducibles |
| Pruebas | Pytest, Testcontainers, Vitest, Playwright | Cobertura por capas con PostgreSQL real |
| Operación | Docker Compose | Despliegue inicial reproducible |

Las versiones exactas se fijarán en lockfiles durante la base técnica y se registrarán en `CHANGELOG.md`.

## Módulos y responsabilidades

| Módulo | Responsabilidad | Dependencias permitidas |
|---|---|---|
| `identity` | Usuarios, sesiones, roles y permisos | audit, settings |
| `settings` | Empresa, impuestos, secuencias, timbrados, monedas | audit |
| `parties` | Clientes y proveedores | settings, audit |
| `catalog` | Productos, insumos, unidades y categorías | settings, audit |
| `inventory` | Depósitos, lotes, documentos, movimientos y saldos | catalog, identity, audit |
| `production` | Granjas, galpones, lotes, aves, mortalidad y alimentación | catalog, inventory, audit |
| `purchasing` | Órdenes, recepciones, documentos, obligaciones y asignación de pagos a AP | parties, catalog, inventory ports, treasury ports, audit |
| `sales` | Pedidos, entregas, documentos internos, derechos de cobro y asignación de cobros a AR | parties, catalog, inventory ports, treasury ports, settings, audit |
| `treasury` | Cuentas/cajas, sesiones, movimientos monetarios, instrumentos, transferencias y cierres | identity, settings, audit |
| `costing` | Eventos, asignaciones, corridas y rentabilidad | contratos neutrales de eventos/snapshots, audit |
| `reporting` | Dashboard, consultas y exportaciones | interfaces de consulta de todos los módulos |
| `audit` | Auditoría funcional, seguridad y outbox | infraestructura transversal |

Propiedad de agregados: `purchasing` posee `supplier_payments` y sus asignaciones contables a AP; `sales` posee `customer_payments` y asignaciones a AR; `treasury` posee exclusivamente el movimiento monetario y la sesión/cuenta. Un pago confirmado referencia un `cash_movement_id`, pero Tesorería no modifica AP/AR.

Mapa de dependencias; `A --> B` significa que A consume un puerto público de B:

```text
purchasing --> inventory command port
purchasing --> treasury command port
sales ------> inventory command port
sales ------> treasury command port
production -> inventory command port
inventory/purchasing/sales/production --> contratos neutrales de eventos en shared/outbox
costing --> consume contratos neutrales; nunca importa módulos productores
reporting --> query ports de cada módulo
todos ------> audit transaction/security ports
sales ------> FiscalDocumentProvider --> Disabled(V1)/SIFEN(futuro)
```

Los casos de uso iniciadores —por ejemplo `ConfirmPurchaseReceipt`— son dueños de una única `UnitOfWork` SQLAlchemy compartida y llaman puertos de comando de módulos participantes dentro de esa transacción. Un puerto no hace `commit`; solo la UoW coordinadora confirma. No hay llamadas inversas, eventos síncronos recursivos ni dependencia de `inventory`/`treasury` hacia compras o ventas. Se comprobarán el grafo acíclico y estas importaciones con pruebas arquitectónicas. `reporting` solo consume puertos de consulta.

## Estructura final de carpetas

```text
AVICOLA_PRO/
|-- backend/
|   |-- pyproject.toml
|   |-- alembic.ini
|   |-- migrations/
|   |-- src/avicola_pro/
|   |   |-- main.py
|   |   |-- bootstrap/{app.py,container.py}
|   |   |-- shared/{domain,application,infrastructure,api}/
|   |   `-- modules/
|   |       |-- identity/       |-- settings/
|   |       |-- parties/        |-- catalog/
|   |       |-- inventory/      |-- production/
|   |       |-- purchasing/     |-- sales/
|   |       |-- treasury/       |-- costing/
|   |       |-- reporting/      `-- audit/
|   `-- tests/{unit,integration,contract,migration,e2e}/
|-- frontend/
|   |-- src/app/
|   |-- src/features/
|   |-- src/components/
|   |-- src/lib/
|   `-- tests/
|-- deploy/{docker,compose,backup,runbooks}/
|-- docs/{adr,specifications,implementation-plans}/
|-- README.md
|-- ARCHITECTURE.md
|-- DATABASE.md
|-- SECURITY.md
|-- INSTALLATION.md
|-- TESTING_STRATEGY.md
|-- IMPLEMENTATION_PLAN.md
|-- PROJECT_STATUS.md
`-- CHANGELOG.md
```

Cada módulo backend contiene `domain`, `application`, `infrastructure` y `api`. Se evitarán archivos agregadores gigantes y repositorios genéricos universales.

## Transacciones y consistencia

Una unidad de trabajo delimita cada comando. Son atómicos:

- recepción + entrada de stock + avance de orden + cuenta por pagar + auditoría/outbox;
- entrega + salida de stock + avance del pedido + auditoría/outbox;
- emisión + numeración + impuestos + cuenta por cobrar + auditoría/outbox;
- alimentación + salida de inventario + costo de producción;
- cobro/pago + aplicación + caja + actualización de deuda;
- transferencias: ambos lados en la misma transacción;
- reversión: compensación, enlace y auditoría.

Concurrencia:

- `READ COMMITTED` con locks explícitos por defecto.
- `SELECT FOR UPDATE` para saldo, deuda y secuencias.
- Orden global de locks para prevenir deadlocks.
- Restricciones únicas como última defensa.
- Reintentos acotados para `40P01` y `40001`.
- Versionado optimista para borradores y maestros.
- `Idempotency-Key` para confirmaciones y pagos.

### Contrato común de documentos confirmables

Todo agregado transaccional confirmable —inventario, mortalidad/aves, recepción, entrega, documento comercial, pago, caja y costo— posee como mínimo `status`, `confirmed_at`, `confirmed_by`, `reversed_at`, `reversed_by`, `reversal_of_id`, `reversal_reason` y `version` cuando aplique. Estados comunes: `DRAFT -> CONFIRMED -> REVERSED`; cada módulo puede añadir estados previos, pero no saltar estados terminales.

- Confirmar asigna identidad/numeración y congela campos económicos.
- Un confirmado no admite `UPDATE` de contenido ni `DELETE`.
- Revertir crea un agregado/movimiento compensatorio con snapshots del costo e importe originales.
- Índice único parcial impide más de una reversión total efectiva del mismo original. No aplica a notas de crédito parciales: estas usan relaciones de ajuste N:1 y un lock del original para validar que la suma confirmada no exceda su neto.
- Nota de crédito es documento comercial nuevo; anulación es transición registrada y, si tuvo efectos, exige compensaciones explícitas.
- Reapertura de caja no edita movimientos: crea evento autorizado y nuevo estado de sesión.
- La defensa combina servicio de dominio, constraints/trigger o privilegios DB y pruebas SQL directas.

### Tiempo y períodos

Cada agregado distingue `effective_date`/fecha de negocio de `occurred_at`/instante real. Instantes se guardan UTC; la fecha operativa y cortes se interpretan en `America/Asuncion`. No se admiten movimientos retroactivos dentro de sesiones/períodos cerrados; una corrección se registra en el período abierto y referencia el original. Cada máquina de estados define transición, permiso, efectos, idempotencia y política temporal antes de implementarse.

### Capacidad de galpones

Las asignaciones bloquean el galpón y el saldo del lote. Dentro de la transacción se suman asignaciones activas que intersectan el período; la suma no puede superar capacidad ni aves disponibles. Un traslado confirma salida y entrada enlazadas atómicamente. Las pruebas concurrentes verifican que dos asignaciones simultáneas no excedan capacidad.

## API y errores

- Base `/api/v1` y recursos plurales.
- DTO públicos independientes del ORM.
- Listados paginados, filtros permitidos y tamaño máximo.
- Acciones de dominio como subrecursos: `/ventas/{id}/confirmaciones`.
- Nunca cambiar un estado crítico mediante `PATCH status` genérico.
- Errores `application/problem+json` con `code`, `detail`, `field_errors` y `correlation_id`.
- OpenAPI es contrato y se verifica en CI.
- Autorización obligatoria en backend para endpoint y caso de uso.

## Documento comercial y documento fiscal

`CommercialDocument` es la fuente comercial interna. Contiene identidad, numeración, snapshots, impuestos, total, estado, cuenta por cobrar y relaciones con inventario/caja. Su número y timbrado son metadatos configurables internos: **no constituyen factura electrónica, CDC, aprobación tributaria ni constancia de SIFEN**. La UI y reportes deben rotularlos como comprobantes comerciales internos durante V1.

`FiscalSubmission` representa exclusivamente interacción externa: proveedor, ambiente, versión, identificador externo, hash, estado, intentos y errores. Inventario, caja y cuentas no dependen de su estado.

Puerto estable:

```python
class FiscalDocumentProvider(Protocol):
    async def submit(self, document: FiscalDocumentPayload) -> FiscalSubmissionResult: ...
    async def query_status(self, external_id: str) -> FiscalStatusResult: ...
    async def cancel(self, request: FiscalCancellation) -> FiscalCancellationResult: ...
```

V1 usa `DisabledFiscalProvider`, que devuelve estado deshabilitado sin DNS, red ni persistir un envío. Un futuro `SifenFiscalProvider` se conectará mediante mapper/anticorruption layer y outbox sin alterar Ventas, Caja o Inventario.

## Auditoría funcional y eventos de seguridad

- Auditoría de negocio exitosa se escribe dentro de la misma UoW que la mutación; si la operación revierte, ambos revierten.
- Intentos fallidos, 401/403, login fallido y errores se escriben después del resultado en un canal durable separado y no participan de la transacción fallida.
- El rol runtime puede insertar, pero no actualizar/borrar auditoría. Lectura/exportación requiere `audit.read`/permiso dedicado.
- Retención, archivo y evidencia de integridad se fijarán antes del piloto; accesos y exportaciones también se auditan.

## Observabilidad, backups y evolución

- Logging JSON a stdout con request ID, duración, módulo y resultado.
- Auditoría funcional append-only separada del log técnico.
- Health/readiness checks y métricas de errores, latencia y pool.
- Backups cifrados, externos y restaurados periódicamente.
- Outbox permite añadir workers cuando existan tareas reales.
- La multiempresa futura requerirá ADR y migración explícita; no se simula en V1.

## Registro de decisiones arquitectónicas (ADR)

| ID | Decisión | Estado | Consecuencia |
|---|---|---|---|
| ADR-001 | Monolito modular hexagonal | Aceptada | Transacciones locales y despliegue simple |
| ADR-002 | PostgreSQL único con propiedad modular de tablas | Aceptada | Integridad fuerte sin acceso cruzado directo |
| ADR-003 | Empresa singleton, sin `company_id` general | Aceptada | Menor complejidad; multiempresa exige migración futura |
| ADR-004 | Aves agregadas por lote | Aceptada | V1 no rastrea individuos |
| ADR-005 | Ledger inmutable + proyección de saldo | Aceptada | Trazabilidad y reconstrucción |
| ADR-006 | Stock negativo prohibido | Aceptada | Confirmación usa lock y validación transaccional |
| ADR-007 | Promedio ponderado móvil | Aceptada | Método único y reproducible en V1 |
| ADR-008 | Correcciones compensatorias | Aceptada | No se borran documentos confirmados |
| ADR-009 | Comercial interno separado de fiscal externo | Aceptada | SIFEN futuro no contamina el dominio comercial |
| ADR-010 | REST versionada y OpenAPI contractual | Aceptada | Cliente tipado y compatibilidad explícita |
| ADR-011 | Outbox transaccional, sin broker inicial | Aceptada | Eventos confiables con operación simple |
| ADR-012 | Seguridad y auditoría dentro de Definition of Done | Aceptada | Ninguna función crítica se entrega sin controles |
| ADR-013 | Backup válido solo tras restauración | Aceptada | Restore drill obligatorio antes del piloto |
| ADR-014 | Propiedad dividida de pagos | Aceptada | Compras/Ventas poseen aplicación AP/AR; Tesorería posee movimiento monetario |
| ADR-015 | UoW coordinada por caso de uso iniciador | Aceptada | Puertos multi-módulo participan sin commit propio |
| ADR-016 | Bucket de costo por depósito-producto-lote | Aceptada | Cantidad y valor se reconcilian por la misma clave |
| ADR-017 | Reversión bajo promedio móvil | Aceptada | Conserva costo original como evidencia; valora la compensación al promedio vigente y registra variación enlazada |
| ADR-018 | V1 opera solo en moneda base PYG | Aceptada | Catálogo preparado; FX y multimoneda transaccional quedan fuera de V1 |
| ADR-019 | Costos consumen contratos neutrales | Aceptada | Productores emiten eventos; no importan ni llaman al módulo costing |
| ADR-020 | Auditoría y outbox tienen políticas distintas | Aceptada | Auditoría no muta; worker outbox puede reclamar/actualizar estado con privilegio mínimo |
