# Changelog

Todos los cambios relevantes se documentan siguiendo categorías Added, Changed, Fixed, Security y Removed.

## [Unreleased]

### Added

- Validacion local adicional D11/D12 en PostgreSQL sintetico: migracion limpia, upgrade, smoke local y evidencia en `artifacts/quality/delivery-11/local-validation-2026-09-22.md`; no sustituye CI/staging/off-host.
- Preparación D11: imágenes backend/frontend no-root, Caddy/TLS, Compose privado con migración previa, backup/restauración Restic cifrados, reconciliación y runbooks.
- Smoke configurable de disponibilidad/rendimiento con camino autenticado opcional mediante cuenta sintética.
- Evidencia de laboratorio D11: Restic 0.19.1 validó backup cifrado de PostgreSQL sintético, restore exacto y 9 conciliaciones; clave errónea y copia corrupta se rechazaron. No equivale a prueba off-host.
- CI construye imágenes y comprueba UID/GID runtime/entrypoint de secretos; Compose valida redes y servicios.
- Entrega 12: validador de manifiesto fail-closed; resuelve tag al commit, verifica hashes de archivos adjuntos y requiere deployment por digest. No declara readiness ni piloto aprobado sin provenance y trust root aprobados.
- CI añade pip-audit/npm audit, escaneo Trivy de secretos/configuración y SARIF de imágenes no-root; los resultados remotos siguen pendientes.
- Entrega 12 endurece el manifiesto contra evidencia vencida o no ligada al commit/digests; el gate siempre guarda un informe nuevo y nunca sobreescribe uno previo.
- El gate D12 ahora valida y liga también el digest de la imagen de backup a la evidencia de build.
- Los módulos operativos registran de forma durable los rechazos de autorización 403 con actor, permiso, recurso y correlación; las decisiones de acceso y respuestas HTTP permanecen iguales.
- Los runbooks verifican permisos del target de restore para UID/GID 10002; ESLint ignora las cachés locales ya excluidas por Git.

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

- Compras/AP: los pagos reusan una clave de idempotencia solo si coinciden proveedor, importe, fecha, método y asignaciones. Reintentos concurrentes se serializan en PostgreSQL; una clave con datos distintos responde con conflicto HTTP 409.
- Revalidación 2026-09-22: se corrigieron errores de Mypy en tests, aislamiento de `sessionStorage` entre pruebas frontend, textos UTF-8 del Catálogo y ramas frontend no cubiertas; backend y frontend pasan sus umbrales oficiales en el entorno reproducible.
- El BFF permite ahora Tesorería, Costos e Informes ya presentes en la UI; esas llamadas antes respondían 404.

### Security

- Revisión manual pendiente: ocho módulos operativos responden 403 sin persistir `authorization.denied`; instrumentación común no implementada a la espera de aprobación del diseño.

- El gate PowerShell ahora falla inmediatamente cuando un comando nativo devuelve código distinto de cero.
- El gate local configura la base PostgreSQL de integración preparada por los scripts.
- Las pruebas de configuración validan de forma aislada credenciales placeholder y CORS wildcard.
- El lint frontend ya no emite advertencias por exportación anónima.
- Alembic se ejecuta desde el intérprete Python activo para funcionar en Windows y Linux CI.
- La validación de producción rechaza URLs PostgreSQL incompletas.
- Las pruebas arquitectónicas detectan dependencias inversas y ciclos internos.
- Los logs estructurados reciben correlation ID y registran errores inesperados sin exponer mensajes sensibles.
- Se normalizó el final de archivo para que el gate histórico de whitespace quede limpio.
