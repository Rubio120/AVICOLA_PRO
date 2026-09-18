# Estado de AVÍCOLA PRO

## Última actualización

2026-09-17 — Entrega 2 autorizada; arquitectura de sesión opaca aprobada, rama aislada y línea base verificadas.

## Estado global

**Entrega 2 / Identidad, RBAC y Auditoría en curso.** La Entrega 1 permanece cerrada y
respaldada. La especificación oficial y el plan ejecutable de Entrega 2 están redactados
en `delivery/02-identity-rbac-audit`; todavía no se ha implementado código funcional.

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
- [ ] Entrega 2: Identidad, RBAC y Auditoría (autorizada y en ejecución).

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

**Entrega 2: Identidad, RBAC y Auditoría base.** Arquitectura oficial: sesión opaca
completamente estatal, cookie HttpOnly/SameSite=Lax, Secure configurable, CSRF separado,
rotación con detección de reutilización, revocación inmediata, RBAC backend, auditoría
transaccional y bootstrap idempotente del administrador inicial.

Rama activa: `delivery/02-identity-rbac-audit`. No iniciar Entrega 3 sin aprobación explícita.

Evidencia local fresca del 2026-09-16:

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

## Verificación de continuidad — 2026-09-17

La revisión independiente confirma que la rama contiene autenticación con sesiones opacas,
Argon2id, migración, bootstrap idempotente y eventos de seguridad. La Entrega 2 no queda
cerrada: faltan los endpoints administrativos de RBAC/auditoría (`/api/v1/users`,
`/api/v1/roles`, `/api/v1/permissions` y `/api/v1/audit-events`) y la UI de identidad
descrita en el plan.

El gate PostgreSQL tampoco pudo completarse en este entorno. El servidor local accesible
en `127.0.0.1:5432` no terminó la conexión async y el PostgreSQL 16.14 autocontenido no
pudo iniciar por la restricción de tokens de Windows. No se sustituyó PostgreSQL por SQLite
ni se redujo cobertura o seguridad; la suite de integración y cobertura global quedan
pendientes de un entorno PostgreSQL operativo.

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
