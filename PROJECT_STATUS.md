# Estado de AVÍCOLA PRO

## Última actualización

2026-09-16 — Entrega 1 en progreso; checkpoint de la base técnica reproducible.

## Estado global

**Entrega 1 / Base técnica reproducible en progreso.** La estructura inicial de backend,
frontend, PostgreSQL, migraciones, automatización y calidad está creada, pero la entrega
no está cerrada: falta completar la instalación limpia interrumpida, los smoke tests y
la revisión final antes del commit definitivo.

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
- [x] Primera revisión arquitectónica independiente y corrección de hallazgos.
- [x] Segunda/tercera revisión arquitectónica sin hallazgos críticos/altos (architect reviewer, 2026-09-16).
- [ ] Base técnica (Entrega 1 en progreso; checkpoint WIP creado antes de la verificación final).
- [ ] Código funcional.

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

**Completar Entrega 1: Base técnica reproducible**, seguida —solo con aprobación explícita— de
**Entrega 2: Identidad, RBAC y Auditoría base**.

La Entrega 1 fue aprobada y está en desarrollo en `delivery/01-foundation`. No iniciar la
Entrega 2 sin aprobación explícita del usuario.

Evidencia documental actual: los nueve archivos requeridos, verificación local de enlaces/whitespace/placeholders y tercera revisión arquitectónica independiente sin hallazgos Critical/Important. Los artefactos automatizados bajo `artifacts/quality/` comenzarán con la Entrega 1.

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

1. `README.md` y `PROJECT_STATUS.md`.
2. `ARCHITECTURE.md` y sus ADR.
3. `DATABASE.md` y `SECURITY.md`.
4. `TESTING_STRATEGY.md` e `INSTALLATION.md`.
5. La entrega correspondiente de `IMPLEMENTATION_PLAN.md`.
6. `CHANGELOG.md`, ADR adicionales, artefactos de calidad y `git log`.

Si código y documentación difieren, detenerse, documentar la discrepancia y solicitar revisión; no cambiar una decisión oficial silenciosamente.
