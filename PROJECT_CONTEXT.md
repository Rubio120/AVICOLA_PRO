# Contexto maestro de continuidad de AVÍCOLA PRO

## Propósito y reglas de uso

Este archivo es el registro maestro de continuidad de AVÍCOLA PRO. Toda sesión o agente debe leerlo antes de modificar el proyecto y contrastarlo con `PROJECT_STATUS.md`, el plan de la entrega activa y `git log`.

- Actualizar `PROJECT_CONTEXT.md` y `PROJECT_STATUS.md` después de cada entrega importante y antes de terminar una sesión.
- Después de actualizar ambos documentos, crear un commit verificable y hacer push a GitHub.
- Nunca registrar secretos, contraseñas, tokens, certificados, cookies ni valores reales de producción.
- Si el código, este contexto y las especificaciones oficiales difieren, detener el avance, documentar la discrepancia y solicitar revisión. No cambiar decisiones oficiales silenciosamente.
- No iniciar una entrega posterior sin cerrar el gate de la actual y obtener la aprobación requerida. La Entrega 2 está autorizada; no iniciar la Entrega 3 sin aprobación explícita del usuario.

## Objetivo y alcance de V1

AVÍCOLA PRO será un sistema empresarial estable, auditable y trazable para administrar integralmente una empresa avícola: configuración, terceros, catálogo, inventario, producción por lotes, compras, ventas, cuentas por pagar/cobrar, caja, costos, rentabilidad y reportes.

V1 es para **una sola empresa**. `company_profile` es singleton; no existe aislamiento multiempresa ni se añade `company_id` general a las tablas. La evolución a multiempresa requerirá un ADR y una migración explícita.

## Arquitectura aprobada

- Monolito modular con arquitectura hexagonal/clean por contexto.
- Frontend Next.js separado que consume una API REST versionada en `/api/v1`.
- Backend FastAPI y una única base PostgreSQL con propiedad modular de tablas.
- Capas por módulo: `domain`, `application`, `infrastructure` y `api`.
- Dominio sin dependencias de FastAPI, SQLAlchemy ni infraestructura; aplicación depende de dominio y puertos; infraestructura implementa adaptadores; API valida transporte, autoriza y llama casos de uso.
- Ningún módulo consulta directamente tablas o repositorios de otro módulo. La integración usa puertos públicos.
- Los casos de uso iniciadores coordinan una única Unit of Work SQLAlchemy; los puertos participantes no hacen `commit`.
- Operaciones críticas síncronas y atómicas; efectos no críticos mediante outbox transaccional e idempotencia.
- `READ COMMITTED`, locks explícitos, orden global de locks, restricciones únicas, reintentos acotados para deadlock/serialización y bloqueo optimista en borradores/maestros.
- No se adoptan microservicios, event sourcing ni CQRS completo en V1.

## Tecnologías elegidas

- Backend: Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2.x, Psycopg 3 y Structlog.
- Base de datos: PostgreSQL 16+; migraciones Alembic.
- Dependencias Python: `uv` y `uv.lock`.
- Frontend: Next.js App Router, React, TypeScript, Tailwind CSS, Zod; se prevén TanStack Query y React Hook Form cuando los módulos funcionales los requieran.
- Pruebas: Pytest, pytest-asyncio, coverage, PostgreSQL real/Testcontainers, Vitest y Playwright para los flujos E2E futuros.
- Calidad: Ruff, mypy estricto, ESLint, TypeScript y auditorías de dependencias.
- Operación: Docker Compose, CI de GitHub Actions, logs estructurados, health/readiness y backups PostgreSQL verificables.
- Toolchain fijado en Entrega 1: Python 3.13.15, `uv` 0.12.15, Node.js 22.23.2, npm 10.9.8 y PostgreSQL 16.14; las dependencias exactas viven en los lockfiles.

## Modelo de datos y reglas transversales

- UUIDv7 generado por la aplicación para claves primarias.
- `date` para fecha de negocio y `timestamptz` UTC para instantes; presentación y cortes en `America/Asuncion`.
- `numeric(18,2)` para importes, `numeric(18,4)` para cantidades y `numeric(9,6)` para tasas; nunca `float` para dinero o cantidades críticas.
- V1 opera transaccionalmente solo en moneda base PYG.
- Estados evolutivos como `varchar` con `CHECK`; FKs indexadas y sin cascadas destructivas en transacciones.
- Maestros utilizados se desactivan, no se borran. Totales, impuestos, moneda, numeración y demás datos económicos se guardan como snapshots.
- Contrato común confirmable: `DRAFT -> CONFIRMED -> REVERSED`, con actor/instante de confirmación y reversión, referencia al original, motivo y versión cuando aplique.
- Los documentos confirmados son inmutables: no se edita ni elimina su contenido.
- Las correcciones se realizan mediante anulaciones, notas o movimientos compensatorios enlazados al original. Nunca se reescribe la historia.
- Una reversión total efectiva por original; las notas parciales usan relación N:1 y validan bajo lock que no excedan el neto original.
- Períodos o sesiones cerrados impiden retrofechas; la corrección se registra en un período abierto y referencia el original.
- `Idempotency-Key` en confirmaciones y pagos.

## Módulos planificados

| Módulo | Responsabilidad principal |
|---|---|
| `identity` | Usuarios, sesiones, roles y permisos |
| `settings` | Empresa singleton, impuestos, monedas, secuencias y timbrados |
| `parties` | Clientes y proveedores |
| `catalog` | Productos, insumos, unidades y categorías |
| `inventory` | Depósitos, lotes, documentos, movimientos y saldos |
| `production` | Granjas, galpones, lotes avícolas, aves, mortalidad y alimentación |
| `purchasing` | Órdenes, recepciones, documentos, AP y aplicación de pagos |
| `sales` | Pedidos, entregas, documentos comerciales, AR y aplicación de cobros |
| `treasury` | Cuentas/cajas, sesiones y movimientos monetarios |
| `costing` | Eventos, asignaciones, corridas, costos y rentabilidad |
| `reporting` | Dashboard, consultas, reportes y exportaciones |
| `audit` | Auditoría funcional, eventos de seguridad y outbox |

## Las 13 entregas

0. Base documental: arquitectura, datos, seguridad, testing, instalación, roadmap y estado.
1. Base técnica reproducible: toolchains, backend/frontend, PostgreSQL, Alembic, CI, observabilidad técnica y pruebas de arquitectura.
2. Identidad, RBAC y auditoría base.
3. Configuración, terceros y catálogo.
4. Inventario transaccional.
5. Producción avícola.
6. Compras y cuentas por pagar.
7. Ventas y cuentas por cobrar.
8. Caja y cierres.
9. Costos y rentabilidad.
10. Dashboard y reportes.
11. Preparación de piloto.
12. Gate final y piloto.

## Estado exacto de la Entrega 1

Estado al 2026-09-16: **completada, revalidada y respaldada**. Rama activa `delivery/01-foundation`; checkpoint técnico publicado `ee294d6` (`fix: harden delivery 1 foundation checks`).

Implementado y versionado en el checkpoint:

- estructura de monolito modular y reglas automáticas de dependencias;
- manifiestos, toolchains fijados y lockfiles de backend/frontend;
- configuración Pydantic tipada y validación de producción;
- factory FastAPI, CORS, logging estructurado y correlation ID;
- respuestas Problem Details y manejo seguro de errores;
- PostgreSQL async, liveness/readiness y baseline Alembic vacío;
- UI técnica mínima Next.js con estado degradado seguro;
- Docker Compose de PostgreSQL, scripts PowerShell y workflow CI;
- pruebas unitarias, de integración, arquitectura y frontend correspondientes.

Gate ejecutado:

- instalación limpia reproducible desde `uv.lock` y `package-lock.json`;
- PostgreSQL 16.14 local, baseline Alembic desde vacío y roundtrip de migración;
- Ruff, mypy, 36 pruebas backend y cobertura 92,09 %;
- ESLint, TypeScript, 10 pruebas frontend, cobertura 100 % y build Next.js;
- `pip-audit` y `npm audit --audit-level=high` sin vulnerabilidades conocidas;
- smoke HTTP 200 para `/health/live`, `/health/ready`, `/openapi.json` y `/`;
- compatibilidad Psycopg async en Windows mediante un Selector event loop explícito.
- Alembic invocado de forma multiplataforma mediante el intérprete activo;
- reglas hexagonales completas por capa y detección automática de ciclos;
- URL PostgreSQL de staging/producción obligatoriamente completa;
- correlation ID enlazado al contexto estructurado y errores inesperados registrados sin filtrar su mensaje.

La Entrega 2 fue autorizada el 2026-09-17. Su diseño oficial y plan están en
`docs/superpowers/specs/2026-09-17-delivery-02-identity-rbac-audit-design.md` y
`docs/implementation-plans/2026-09-17-delivery-02-identity-rbac-audit.md`.

Arquitectura de autenticación aprobada: sesión opaca completamente estatal; identificador
aleatorio en cookie HttpOnly/SameSite=Lax con Secure configurable; PostgreSQL conserva solo
su hash; CSRF separado; rotación con detección de reutilización; revocación inmediata;
RBAC exclusivamente backend; auditoría transaccional y bootstrap idempotente del primer
administrador. La contraseña temporal se genera criptográficamente, se muestra una sola vez,
solo se persiste su hash y el primer acceso obliga a reemplazarla.

Estado de la Entrega 2 al 2026-09-18: **completada y verificada localmente**. Incluye
administración protegida de usuarios, roles, permisos y auditoría; revocación de sesiones al
desactivar cuentas; eventos de seguridad para denegaciones RBAC; auditoría transaccional de
lecturas; y BFF same-origin de Next.js para login, restauración de sesión, cambio obligatorio
de contraseña y logout. PostgreSQL 16 real en `127.0.0.1:55432` pasó migración limpia,
roundtrip y health checks. La suite backend pasó 95 pruebas con 86,24 % de cobertura,
Ruff/formato/Mypy, y el frontend pasó ESLint, TypeScript y build. Vitest está correctamente
escrito pero su ejecución queda delegada al PowerShell externo por la denegación ambiental de
esbuild al leer rutas padre de `C:\Users`.

## Decisiones funcionales consolidadas

### Inventario

- Ledger de movimientos inmutable más proyección de saldos.
- Stock negativo estrictamente prohibido, validado transaccionalmente con locks.
- Valoración única por promedio ponderado móvil.
- Bucket de cantidad y costo por depósito-producto-lote.
- Transferencias registran salida y entrada enlazadas en la misma transacción.
- Reversiones conservan costo/valor original como evidencia, compensan al promedio vigente y registran la variación de costo enlazada; cantidad y valor deben reconciliar, incluido saldo cero.

### Producción avícola

- Las aves se gestionan como cantidades por lote, nunca como individuos.
- Ledger tipado para entrada inicial, traslado, mortalidad, ajuste, venta, faena y otras salidas; el registro diario es observacional.
- Aves vivas nunca negativas; capacidad de galpones y períodos de ocupación validados bajo lock.
- Activar un lote crea un único evento inicial; cerrarlo exige saldo cero o ajuste autorizado.
- Mortalidad y ajustes confirmados son inmutables y reversibles mediante compensación.
- La alimentación descuenta inventario y genera costo dentro de una única transacción.

### Ventas, caja, compras y costos

- Compras posee órdenes, recepciones, documentos de proveedor, obligaciones AP y asignaciones de pagos; Tesorería posee el movimiento monetario.
- Recepción, stock, avance de orden y AP son atómicos; no se permite sobre-recepción ni sobreaplicación.
- Ventas posee pedidos, entregas, documentos comerciales internos, AR y asignaciones de cobros; entrega/stock y emisión/AR son flujos atómicos según el caso.
- Documento comercial y documento fiscal son agregados separados. En V1 los comprobantes son internos y deben rotularse como no fiscales/no electrónicos.
- No hay SIFEN real en V1. `DisabledFiscalProvider` no realiza red, DNS ni persistencia de envío; el puerto `FiscalDocumentProvider` y una futura capa anticorrupción dejan preparada la integración.
- Caja usa sesiones, apertura, movimientos, transferencias y cierres auditables. Cerrar fija esperado/contado/diferencia; reabrir requiere permiso y motivo y no reescribe movimientos.
- Compras/Ventas actualizan AP/AR; Tesorería no modifica esas cuentas y solo aporta el `cash_movement_id`.
- Costos consume contratos neutrales/eventos y snapshots; los productores no importan ni llaman al módulo `costing`.
- Corridas de costos cerradas son versionadas, reproducibles e inmutables; rentabilidad usa solo documentos y costos confirmados.

## Seguridad

- Autenticación y autorización en backend; denegación por defecto y permisos granulares por caso de uso.
- Contraseñas Argon2id, sesiones rotatorias/revocables, cookies seguras configurables, CSRF, CORS explícito y rate limiting para autenticación.
- Configuración tipada con fallo temprano; secretos exclusivamente fuera de Git y de `app_settings`.
- Auditoría de negocio exitosa en la misma transacción que la mutación; fallos, 401/403 e intentos de login por canal durable independiente.
- Auditoría append-only: el rol runtime puede insertar, pero no actualizar ni borrar; lectura/exportación requiere permiso dedicado y también se audita.
- Logs estructurados con redacción, correlation ID y sin trazas ni secretos en respuestas.
- TLS, base de datos privada, contenedores no-root, mínimos privilegios, escaneo de dependencias/SAST/secretos/imágenes y backups cifrados antes del piloto.

## Testing y gates

- TDD/RED-GREEN-REFACTOR para comportamiento; cada entrega incluye unitarias, integración PostgreSQL real, contratos, seguridad negativa, concurrencia, migraciones y E2E según riesgo.
- Cobertura orientativa: 80 % global y 90 % en reglas críticas, incluyendo ramas y casos negativos.
- SQLite está prohibido como sustituto de PostgreSQL en integración.
- Se verifican invariantes, idempotencia, locks, reversiones, inmutabilidad mediante SQL directo, precisión decimal, UTC/zona local y reconstrucción de ledgers.
- CI ejecuta formato, lint, tipos, tests, cobertura, build, migraciones y auditorías. No se cierra una entrega con pruebas fallidas ni defectos críticos/altos.
- La evidencia del gate se guarda bajo `artifacts/quality/delivery-<n>/` o en el artefacto CI equivalente.
- Antes del piloto es obligatorio un restore drill real, reconciliación de stock/aves/caja/AP/AR/auditoría y smoke/E2E sobre la restauración.

## Agentes, skills y plugins disponibles

Inventario conocido del entorno Codex al 2026-09-16:

- perfiles de trabajo: backend/platform architect, FastAPI/Python, frontend, deployment, database/performance, test automator/TDD, security/threat modeling, debugger y reviewers architect/code/comprehensive;
- skills de Superpowers para brainstorming, planes, TDD, debugging sistemático, ejecución/revisión y verificación antes de completar;
- plugins/skills de backend development, Python development, frontend/mobile development, security scanning y utilidades OpenAI para documentos, PDF, presentaciones, hojas de cálculo, visualización, plugins y creación/instalación de skills.

Estos recursos ayudan a ejecutar y revisar; no reemplazan la aprobación humana ni autorizan ampliar el alcance. La Entrega 2 puede usar especialistas de Python/FastAPI, frontend, despliegue, testing, seguridad y arquitectura. No se debe iniciar la Entrega 3.

## Autonomía segura

- Trabajar solo dentro del workspace y del alcance de la entrega autorizada.
- Preferir inspecciones y validaciones no destructivas; preservar cambios ajenos y archivos no relacionados.
- Solicitar aprobación para acceso fuera del sandbox, red restringida o acciones destructivas/materialmente externas.
- No borrar, sobrescribir, hacer `reset --hard`, reescribir historial ni cambiar decisiones oficiales sin autorización explícita.
- Usar variables de entorno y ejemplos ficticios; revisar staged diff y escanear secretos antes de cada commit.
- Ejecutar verificaciones frescas antes de afirmar que una tarea o entrega está completa.
- Los fallos se investigan antes de cambiar código; no se deshabilitan pruebas ni controles para forzar un resultado verde.

## Política de Git y checkpoints

- Rama aislada por entrega; rama actual: `delivery/02-identity-rbac-audit`, worktree local `.worktrees/delivery-02-identity-rbac-audit`.
- Commits pequeños y verificables con Conventional Commits; un commit por entrega o subentrega revisable.
- No mezclar cambios ajenos, artefactos locales o secretos. No hacer commit con pruebas rotas salvo un checkpoint WIP explícito por continuidad de emergencia.
- No reescribir historia compartida. Tags solo después del gate de release.
- Después de una entrega importante y antes de terminar sesión: actualizar `PROJECT_CONTEXT.md`, `PROJECT_STATUS.md` y `CHANGELOG.md` cuando corresponda; ejecutar `git diff --check` y las pruebas pertinentes; revisar staged diff; commit; push; confirmar que rama local y remota coinciden.
- Ante riesgo de corte de energía, crear un checkpoint WIP claramente rotulado y hacer push; al reanudar, no confundirlo con el cierre del gate.

Repositorio remoto: `origin` apunta a `https://github.com/Rubio120/AVICOLA_PRO.git`. Rama remota activa de trabajo: `origin/delivery/02-identity-rbac-audit` después del primer push.

Último checkpoint remoto de Entrega 1: `73ab758` — `chore: ignore local worktrees`. El último checkpoint funcional de Entrega 1 es `ee294d6` — `fix: harden delivery 1 foundation checks`.

## Recuperación tras corte de energía o interrupción

## Continuidad posterior — Entrega 8 — 2026-09-20

En `AVICOLA_PRO_WEEKEND` se implementó la Entrega 8, Caja y cierres, sin commit ni push por
instrucción expresa del usuario. El head Alembic es `0009_treasury`; la migración fue probada
aisladamente desde base PostgreSQL vacía y en roundtrip.

Tesorería posee cuentas, sesiones, movimientos y transferencias. Se aplican locks PostgreSQL,
índice único parcial para una sola sesión `OPEN/REOPENED`, conciliación de esperado/contado,
reapertura con motivo y reversión append-only enlazada. La API exige sesión, CSRF, RBAC y
auditoría; la UI añade consulta segura de cuentas.
Los egresos y transferencias validan saldo disponible bajo lock y no permiten saldo negativo.

Gate fresco: 123 pruebas backend verdes con 80,07 % de cobertura en el gate funcional; 18
pruebas de migración limpia/roundtrip verdes; Ruff/formato y mypy de producción verdes;
ESLint, TypeScript y build frontend verdes. Vitest queda delegado al PowerShell externo por
la restricción ambiental conocida de esbuild. No se inició la Entrega 9. `AGENTS.md` no existe
en esta raíz.

## Continuidad posterior — Entrega 6 — 2026-09-19

En `AVICOLA_PRO_WEEKEND` se implementó la Entrega 6, Compras + cuentas por pagar, sin commit
ni push por instrucción expresa del usuario. El head Alembic es
`0007_supplier_document_lines`; las migraciones `0006_purchasing` y `0007_supplier_document_lines`
fueron probadas desde base PostgreSQL vacía y en roundtrip.

El módulo `purchasing` posee órdenes, líneas, aprobación, recepciones parciales con lotes,
documentos de proveedor, líneas snapshot, cuentas por pagar, pagos y asignaciones N:M.
`ConfirmPurchaseReceipt` coordina inventario y avance de la orden dentro de la misma sesión;
los pagos generan el identificador neutral `cash_movement_id` para la futura Tesorería y sus
reversiones restauran AP sin reescribir el historial. Se mantuvieron RBAC, CSRF, auditoría,
restricciones PostgreSQL e idempotencia.

La suite backend terminó con 125 pruebas y 80,02 % de cobertura; Ruff, formato, Mypy,
arquitectura, migraciones y health checks pasaron. ESLint, TypeScript y build frontend pasaron.
Vitest permanece delegado al gate PowerShell externo por la restricción ambiental conocida de
esbuild contra rutas padre de `C:\Users`; las pruebas frontend quedaron escritas.

La Entrega 7 es la siguiente pendiente. No comenzar Compras de nuevo ni avanzar a Ventas sin
un nuevo ciclo explícito de continuidad.

## Continuidad posterior — Entrega 7 — 2026-09-19

En `AVICOLA_PRO_WEEKEND` se implementó la Entrega 7, Ventas + cuentas por cobrar, sin commit
ni push por instrucción expresa del usuario. El head Alembic es `0008_sales`; las tablas de
pedidos, entregas, documentos internos, relaciones, AR, cobros y asignaciones se probaron
desde base PostgreSQL vacía y en roundtrip.

Ventas recalcula en backend importes exentos, bases/IVA 5% y 10%, descuentos y total con
redondeo monetario; la emisión toma una secuencia bajo lock y conserva snapshots del cliente.
Las entregas bloquean líneas, no permiten sobreentrega y confirman la salida de inventario en
la misma UoW. Los cobros bloquean AR, no sobreaplican, producen `cash_movement_id` neutral y
las notas de crédito validan el tope acumulado y compensan el saldo original. El adaptador
fiscal V1 está deshabilitado y no realiza red, DNS ni persistencia.

La suite backend terminó con 133 pruebas y 80,03 % de cobertura. Ruff, formato, Mypy,
arquitectura, migraciones y health checks pasaron. ESLint, TypeScript y build frontend
pasaron; Vitest permanece delegado al gate PowerShell externo por la restricción ambiental
conocida de esbuild. La Entrega 8 es la siguiente pendiente; no comenzar Caja en esta
ejecución.

## Continuidad posterior — 2026-09-18

La Entrega 3 quedó implementada en el working tree del worktree `AVICOLA_PRO_WEEKEND`.
El head de Alembic es `0003_settings_parties_catalog`; la migración fue probada desde base
vacía y en roundtrip sobre PostgreSQL 16 real. Se incorporaron `company_profile`, monedas,
unidades, impuestos, timbrados, secuencias, métodos de pago, clientes, proveedores, categorías,
productos, granjas, galpones y depósitos, junto con sus modelos, restricciones e índices.

La API de settings/parties/catalog aplica sesión, CSRF, RBAC, paginación y auditoría; la UI
incluye consulta filtrable de productos mediante BFF same-origin. La suite backend completa pasó
98 pruebas con cobertura 81,30 %, Ruff y Mypy; frontend pasó ESLint, TypeScript y build. Vitest
está escrito y queda delegado al PowerShell externo por el PermissionError conocido de esbuild
contra rutas padre de `C:\Users`. No se hizo commit ni push por instrucción expresa del usuario.

1. No borrar ni limpiar archivos al iniciar.
2. Abrir la raíz del repositorio y leer `PROJECT_CONTEXT.md`, `PROJECT_STATUS.md`, el diseño/plan de la Entrega 2 y `git log -10 --oneline --decorate`.
3. Ejecutar `git status --short --branch`, `git remote -v` y `git branch -vv` para identificar rama, cambios locales y sincronización remota.
4. Confirmar que la rama es `delivery/02-identity-rbac-audit` y que el checkpoint remoto esperado está disponible. No cambiar de rama si hay cambios sin identificar.
5. Inspeccionar cada archivo modificado/no rastreado; asumir que pertenece al usuario hasta demostrar lo contrario. No usar comandos destructivos.
6. Comparar el trabajo con `docs/implementation-plans/2026-09-17-delivery-02-identity-rbac-audit.md` y continuar desde la primera verificación pendiente.
7. Restaurar herramientas solo desde lockfiles: backend con `uv sync --frozen --all-groups`; frontend con `npm.cmd ci` en Windows.
8. Levantar PostgreSQL 16, migrar desde base vacía, ejecutar gates y smoke tests. Registrar resultados reales; no declarar cerrada la entrega por la mera existencia del checkpoint.
9. Actualizar contexto/estado, revisar que no haya secretos, hacer commit y push al terminar.

## Problemas técnicos encontrados y soluciones

| Problema observado | Estado/solución aplicada |
|---|---|
| Una instalación/verificación limpia fue interrumpida antes del gate final. | Se creó y publicó el checkpoint WIP `2ca101c`; posteriormente el clean install y el gate se completaron en `b276cfb`. |
| `python.exe` global no es accesible desde la sesión actual. | Usar el Python administrado por `uv`: `uv run python`, `uv run pytest`, etc.; la versión objetivo está fijada en CI/`.python-version`. |
| PowerShell bloquea scripts `.ps1` y `npm.ps1` por la política de ejecución. | Invocar `npm.cmd` y ejecutar scripts propios con `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ...`; el bypass es solo del proceso y no cambia la política global. |
| Docker/Docker Compose no está instalado o no está en `PATH` en esta máquina. | El Compose y CI ya están definidos; para evidencia local se requiere habilitar Docker o usar un PostgreSQL 16 accesible mediante variables de entorno. No sustituir con SQLite. |
| Uvicorn usa `ProactorEventLoop` por defecto en Windows y Psycopg async lo rechaza. | Se añadió un Selector loop factory probado y `dev-backend.ps1` lo pasa mediante `--loop`; readiness contra PostgreSQL real responde 200. |
| `check.ps1` continuaba tras fallos de comandos nativos y no configuraba la URL de la base de pruebas. | Se añadió `Invoke-Checked` con validación de `$LASTEXITCODE` y valores locales por defecto para las URLs de integración. |
| El roundtrip Alembic local podía usar la misma base que la aplicación. | `db-up.ps1` provisiona `avicola_pro` y `avicola_pro_test`; `check.ps1` reserva la segunda para integración y falla temprano si ambas URLs son iguales. |
| La prueba Alembic usaba la ruta Windows `.venv/Scripts/alembic.exe`. | Ahora usa `sys.executable -m alembic`, compatible con Windows y Linux CI. |
| Las reglas arquitectónicas no cubrían imports inversos dentro del módulo ni ciclos. | Se añadió matriz de dependencias por capa, restricciones intermodulares y detección DFS de ciclos con fixtures negativos. |
| Producción aceptaba URLs PostgreSQL sin host, base, usuario o contraseña. | La URL se parsea con SQLAlchemy y staging/producción exigen las cuatro coordenadas. |
| Correlation ID no estaba enlazado a Structlog y los 500 no producían evento seguro. | Middleware enlaza/restaura contextvars y el handler registra tipo, ruta y correlación sin mensaje sensible. |
| El archivo no rastreado `tatus` era una captura accidental de nombres de archivos, sin contenido único. | Se inspeccionó y eliminó con la autorización previa del usuario; el árbol quedó limpio. |
| PowerShell/Pytest/esbuild reciben denegaciones del sandbox al iniciar procesos o inspeccionar ancestros del worktree. | Usar TEMP/TMP dentro de `.cache` y ejecutar los gates con la escalación mínima cuando la restricción del sandbox sea la causa demostrada. |
| El output de algunas herramientas muestra mojibake de UTF-8 en la consola PowerShell. | Los archivos se mantienen en UTF-8 mediante `.editorconfig`/`.gitattributes`; validar contenido con herramientas que respeten UTF-8 y no recodificar masivamente sin necesidad. |

## Comandos importantes

```powershell
# Estado y continuidad

## Continuidad autoritativa — 2026-09-19

La primera entrega pendiente identificada fue la Entrega 4 — Inventario transaccional, porque las
Entregas 2 y 3 ya estaban implementadas en el estado actual del worktree. La Entrega 4 quedó
implementada sin commit ni push.

Se añadió la migración PostgreSQL `0004_inventory`, modelos de lotes/documentos/movimientos/
saldos/variaciones, reglas Decimal de promedio ponderado móvil, servicio de confirmación y
reversión, endpoints protegidos por sesión/CSRF/RBAC/auditoría y un panel frontend de
saldos/entradas. El ledger de movimientos tiene trigger append-only y los balances usan locks
explícitos con índice único PostgreSQL `NULLS NOT DISTINCT` para buckets con lote nulo.

Gates frescos: PostgreSQL 16 real en `127.0.0.1:55432`, migración limpia/roundtrip y head
`0004_inventory`; suite backend 109 pruebas con cobertura 80,66 %, Ruff/formato/Mypy, smoke de
`/health/live`, `/health/ready` y `/openapi.json` en 200; `npm audit` y `pip-audit` sin hallazgos
conocidos; ESLint, TypeScript y build frontend verdes. Vitest está escrito y se delega al
PowerShell externo únicamente por el `PermissionError` ambiental de esbuild contra rutas padre de
`C:\Users`.

`AGENTS.md` no existe en esta raíz. No se inició la Entrega 5 ni se alteraron datos reales.
git status --short --branch
git log -10 --oneline --decorate
git branch -vv
git remote -v
git diff --check

# Instalación reproducible
Set-Location backend
uv sync --frozen --all-groups
uv lock --check
Set-Location ..\frontend
npm.cmd ci

# Gate backend
Set-Location ..\backend
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
uv run pip-audit

# Migraciones
uv run alembic upgrade head
uv run alembic current
uv run alembic downgrade base
uv run alembic upgrade head

# Gate frontend
Set-Location ..\frontend
npm.cmd run lint
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
npm.cmd audit

# Scripts desde la raíz
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\db-up.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\migrate.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev-backend.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev-frontend.ps1
```

Las variables de conexión y secretos se proporcionan por el entorno local/CI y nunca se copian a este documento.

## Pendientes y riesgos abiertos

Pendiente inmediato: cerrar los gates restantes de Entrega 2, especialmente Vitest/cobertura frontend y revisión independiente. No avanzar a Entrega 3 sin aprobación explícita.

Riesgos que no bloquean la base técnica, pero deben resolverse antes de sus módulos:

1. Reglas paraguayas exactas de redondeo y representación de IVA antes de Ventas.
2. Momento de reconocimiento del costo de compra: recepción o documento del proveedor.
3. Política entrega-facturación para entregas parciales y consolidadas.
4. RPO, RTO y retención final antes del piloto.
5. Volumen y concurrencia objetivo para presupuestos de rendimiento.
6. Política funcional de reapertura de caja y autorizaciones de alto impacto.
7. Métricas productivas adicionales antes de ampliar `production_events`.

## Verificación de continuidad — 2026-09-17

La Entrega 2 sigue en ejecución y no debe avanzar a Entrega 3. Esta sesión añadió endpoints
administrativos protegidos de usuarios, roles, permisos y auditoría, auditoría funcional dentro
de la transacción de mutación, prueba de integración PostgreSQL y una UI inicial de identidad.
El gate frontend de Vitest sigue bloqueado por una denegación de lectura de esbuild fuera del
workspace; ESLint, TypeScript y build sí terminaron correctamente.

La integración PostgreSQL y la cobertura global no pudieron cerrarse en esta máquina: el
servidor accesible en `127.0.0.1:5432` no completó la conexión async y el PostgreSQL 16.14
autocontenido no pudo arrancar por la restricción de tokens de Windows. No se utilizó SQLite,
no se redujeron gates y no se alteraron datos reales.

## Continuidad posterior — 2026-09-19

La primera entrega pendiente fue la Entrega 5 — Producción avícola, porque las Entregas 2, 3 y 4
ya estaban implementadas y cerradas en el working tree. La Entrega 5 quedó implementada sin
commit ni push.

Se añadió la migración `0005_production` y modelos para lotes, asignaciones, saldos, eventos de
movimiento, mortalidad, ajustes, observaciones diarias y consumo de alimento. El servicio usa
locks PostgreSQL, activación idempotente con un único INITIAL, invariantes de aves no negativas,
capacidad de galpones, cierre condicionado a saldo cero y consumo de alimento dentro de la misma
UoW que la salida de inventario. La API queda protegida por sesión opaca, CSRF y RBAC; la UI
incluye consulta de saldos y estados seguros.

Gate local fresco: PostgreSQL 16 real en `127.0.0.1:55432`, migración desde base vacía y
roundtrip, 118 pruebas backend con cobertura 80,05 %, Ruff/formato/Mypy y reglas arquitectónicas
verdes; ESLint, TypeScript y build frontend verdes. Vitest queda delegado al PowerShell externo
por el PermissionError ambiental conocido de esbuild contra rutas padre de `C:\Users`.
No se hizo commit, push, reset ni se alteraron datos reales. No se inició la Entrega 6.

## Fuentes oficiales relacionadas

## Continuidad - cierre Entrega 3, 2026-09-18

La Entrega 3 fue revalidada en el working tree. La suite fresca pasÃ³ 103 pruebas con 81,26 %
de cobertura sobre PostgreSQL real; Ruff, Mypy, frontend y build quedaron verdes. Vitest queda
delegado al PowerShell externo por la restricciÃ³n ambiental conocida. No se hizo commit, push ni
se iniciÃ³ la Entrega 4.

## Continuidad autoritativa - 2026-09-18

La Entrega 3 es la entrega trabajada en este checkpoint del working tree. La migración `0003_settings_parties_catalog` y sus modelos cubren configuración, terceros, catálogo, granjas, galpones y depósitos sobre PostgreSQL real. La API exige sesión, CSRF, RBAC y auditoría; la UI usa el BFF same-origin. La suite backend pasó 100 tests con 81.58 % de cobertura; Ruff, formato, Mypy, ESLint, TypeScript y build pasaron. Vitest queda delegado al PowerShell externo únicamente por el `PermissionError` ambiental de esbuild al leer rutas padre de `C:\Users`.

No se inició la Entrega 4, no se hizo commit/push/reset y no se alteraron datos reales. `AGENTS.md` no está presente en esta raíz.

- `ARCHITECTURE.md`: arquitectura y ADR oficiales.
- `DATABASE.md`: entidades, invariantes, estados y conciliaciones.
- `SECURITY.md`: controles y modelo de amenazas.
- `TESTING_STRATEGY.md`: matriz y gates de calidad.
- `IMPLEMENTATION_PLAN.md`: roadmap de 13 entregas.
- `docs/implementation-plans/2026-09-16-delivery-01-foundation.md`: plan ejecutable vigente.
- `PROJECT_STATUS.md`: estado operativo resumido y siguiente acción.
- `INSTALLATION.md`, `README.md` y `CHANGELOG.md`: operación, entrada al proyecto e historial.
