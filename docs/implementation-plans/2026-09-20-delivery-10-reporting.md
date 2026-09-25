# Entrega 10 — Dashboard y reportes

> Ejecución autónoma: no se hace commit, push ni se inicia la Entrega 11.

**Objetivo:** exponer un dashboard operativo y reportes paginados/exportables que solo lean hechos confirmados, respeten RBAC, tengan límites explícitos y auditen las exportaciones.

**Arquitectura:** el contexto `reporting` usa un adaptador SQL de solo lectura con consultas parametrizadas y tablas neutrales; no importa modelos ni repositorios de otros módulos. La API valida filtros, autoriza con `reports.profitability.read` o `reports.export`, y registra la exportación en la auditoría transaccional. La UI consume el BFF same-origin.

**Entregables:** KPIs de inventario/producción/compras/ventas/caja/costos, listado de rentabilidad con filtros por fecha y paginación, exportación CSV acotada, tests unitarios/integración/seguridad, panel frontend y documentación de estado.

## Plan operativo

- [x] Crear contrato de consulta neutral y adaptador PostgreSQL parametrizado.
- [x] Añadir pruebas RED para KPIs, filtros, límites, confirmados solamente y CSV.
- [x] Implementar API protegida, auditoría de exportaciones y respuestas estables.
- [x] Registrar el router y reutilizar los permisos/seed existentes.
- [x] Añadir panel frontend y tests de estados de carga/error/datos.
- [x] Ejecutar tests focalizados, suite, cobertura, Ruff, formato, Mypy, ESLint, TypeScript, build, migración limpia/roundtrip, health checks y revisión de seguridad.
- [x] Corregir hallazgos y actualizar `PROJECT_STATUS.md` y `PROJECT_CONTEXT.md` sin commit.

## Decisiones

- No se crea migración: reporting es una vista de lectura sobre tablas existentes; la auditoría usa `audit_events` ya existente.
- Los estados aceptados son `CONFIRMED`, `ISSUED`, `APPROVED`, `PARTIALLY_RECEIVED`, `RECEIVED`, `FULFILLED`, `OPEN` y `REOPENED` según el agregado consultado; anulados/revertidos no cuentan.
- Los límites de API son `limit <= 100`, `offset <= 100000`, fechas opcionales y CSV máximo de 1000 filas.
