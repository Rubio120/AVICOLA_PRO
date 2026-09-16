# Estado de AVÍCOLA PRO

## Última actualización

2026-09-16 — Entrega 1 revalidada y endurecida; gate local completo verde, pendiente de aprobación para iniciar Entrega 2.

## Estado global

**Entrega 1 / Base técnica reproducible completada.** Instalación limpia desde lockfiles,
migraciones PostgreSQL 16, checks de backend/frontend, auditorías y smoke tests fueron
ejecutados con resultados verdes. No se inició ningún alcance de Entrega 2.

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
- [ ] Módulos funcionales de negocio (comienzan en Entrega 2, aún no autorizada).

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

## Próxima entrega

**Esperar aprobación explícita del usuario** antes de iniciar la **Entrega 2: Identidad,
RBAC y Auditoría base**.

La Entrega 1 tiene como último checkpoint publicado `2fb0aa4` en
`origin/delivery/01-foundation`. El bloque final de endurecimiento descrito abajo está
verificado localmente y pendiente de commit/push. No iniciar la Entrega 2 sin aprobación explícita del usuario.

Evidencia local fresca del 2026-09-16:

- clean install: CPython 3.13.15/79 paquetes y npm/471 paquetes desde lockfiles;
- Alembic: base vacía a `0001_baseline (head)` y roundtrip validado;
- backend: Ruff y mypy verdes; 36 pruebas, cobertura 92,09 %;
- frontend: ESLint y TypeScript verdes; 10 pruebas, cobertura 100 %; build Next.js verde;
- dependencias: `pip-audit` y `npm audit --audit-level=high`, cero vulnerabilidades conocidas;
- smoke: `/health/live`, `/health/ready`, `/openapi.json` y `/` respondieron HTTP 200.

El bloque local verificado de revisión final corrige portabilidad Alembic en Linux, validación de
URL PostgreSQL productiva, matriz/ciclos de dependencias hexagonales, correlación de logs
y whitespace histórico. La revisión no dejó hallazgos críticos/importantes de código pendientes.

Evidencia documental actual: documentos de arquitectura y continuidad, verificación local de enlaces/whitespace/placeholders y revisión independiente. La evidencia local de Entrega 1 se resume arriba; GitHub Actions conservará los artefactos CI después del próximo push. `artifacts/quality/` mantiene por ahora solo su marcador versionado.

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

Una sesión futura debe leer, en orden:

1. `PROJECT_CONTEXT.md` y `PROJECT_STATUS.md`.
2. `README.md`, `ARCHITECTURE.md` y sus ADR.
3. `DATABASE.md` y `SECURITY.md`.
4. `TESTING_STRATEGY.md` e `INSTALLATION.md`.
5. La entrega correspondiente de `IMPLEMENTATION_PLAN.md`.
6. `CHANGELOG.md`, ADR adicionales, artefactos de calidad y `git log`.

Si código y documentación difieren, detenerse, documentar la discrepancia y solicitar revisión; no cambiar una decisión oficial silenciosamente.
