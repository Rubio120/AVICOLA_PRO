# Changelog

Todos los cambios relevantes se documentan siguiendo categorías Added, Changed, Fixed, Security y Removed.

## [Unreleased]

### Added

- Base técnica reproducible de Entrega 1: FastAPI, PostgreSQL/Alembic, Next.js, CI, health/readiness, logging, Problem Details y límites arquitectónicos.
- Contexto maestro de continuidad en `PROJECT_CONTEXT.md`.
- Selector event loop explícito para compatibilidad de Psycopg async con Windows.

- Especificación arquitectónica de V1.
- Modelo lógico inicial de PostgreSQL.
- Estrategia de seguridad, auditoría y permisos.
- Estrategia de pruebas y gates de calidad.
- Plan incremental de implementación.
- Contrato de instalación, backups y restauración.
- Registro de estado para continuidad entre sesiones.
- Contratos explícitos de UoW multi-módulo, ownership de pagos y grafo acíclico.
- Lifecycle común de confirmación/reversión y defensas de inmutabilidad.
- Reglas reproducibles de promedio ponderado, valor de inventario y costo histórico.
- Ledger tipado de entradas, traslados y salidas de aves.
- Separación entre auditoría transaccional y eventos de seguridad fallidos.

### Decisions

- Monolito modular con FastAPI, Next.js y PostgreSQL.
- Una sola empresa y aves gestionadas por lote.
- Ledger inmutable, stock no negativo y promedio ponderado móvil.
- Documento comercial interno separado del documento fiscal externo.
- SIFEN y multiempresa fuera de V1.
- UoW coordinada por el caso de uso iniciador y propiedad explícita de pagos.
- Bucket de costo por depósito/producto/lote y variación de costo en reversiones.
- Operación V1 exclusivamente en moneda base PYG.
- Auditoría inmutable separada del lifecycle mutable de outbox.
- Contratos neutrales de eventos para evitar dependencia Producción-Costos.

### Fixed

- El gate PowerShell ahora falla inmediatamente cuando un comando nativo devuelve código distinto de cero.
- El gate local configura la base PostgreSQL de integración preparada por los scripts.
- Las pruebas de configuración validan de forma aislada credenciales placeholder y CORS wildcard.
- El lint frontend ya no emite advertencias por exportación anónima.
- Alembic se ejecuta desde el intérprete Python activo para funcionar en Windows y Linux CI.
- La validación de producción rechaza URLs PostgreSQL incompletas.
- Las pruebas arquitectónicas detectan dependencias inversas y ciclos internos.
- Los logs estructurados reciben correlation ID y registran errores inesperados sin exponer mensajes sensibles.
- Se normalizó el final de archivo para que el gate histórico de whitespace quede limpio.
