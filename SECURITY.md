# Seguridad de AVÍCOLA PRO

## Objetivos

Proteger identidad, datos comerciales y financieros, impedir operaciones no autorizadas y conservar evidencia de toda acción crítica. Seguridad y auditoría forman parte de la Definition of Done.

## Autenticación

- Contraseñas hasheadas con Argon2id y parámetros revisables.
- Longitud mínima y bloqueo de contraseñas comunes; sin reglas de composición artificiales.
- Access token o sesión corta en cookie `HttpOnly`, `Secure`, `SameSite=Lax/Strict`.
- Protección CSRF en operaciones mutables autenticadas por cookie.
- Refresh token rotatorio; solo se conserva su hash y familia de sesión.
- Detección de reutilización revoca toda la familia.
- Revocación en logout, cambio de contraseña, desactivación o incidente.
- Rate limit progresivo en login y recuperación.
- Respuestas genéricas que no revelen usuarios existentes.
- Administrador inicial creado mediante comando de bootstrap de un solo uso.
- MFA queda como evolución; no se declarará disponible en V1 sin implementación completa.

## Autorización

RBAC con permisos `modulo.recurso.accion`, denegación por defecto y mínimo privilegio. El backend verifica permisos concretos en API y caso de uso; la UI solo adapta la experiencia.

Roles iniciales configurables: Administrador, Gerencia, Producción, Inventario, Compras, Ventas, Caja, Finanzas y Auditor.

Controles:

- Separar crear, aprobar, confirmar, anular, revertir, exportar y auditar.
- Cambios de rol y permisos requieren `roles.manage` y auditoría.
- Acciones masivas comprueban cada recurso.
- Reportes y exportaciones respetan permisos de origen.
- Para ajustes de alto impacto se podrá exigir creador distinto de aprobador.
- Al menos un administrador activo debe conservarse mediante regla transaccional.

## Matriz mínima de permisos

```text
users.manage
roles.manage
settings.manage
audit.read
inventory.products.read
inventory.movements.create
inventory.adjustments.approve
inventory.transfers.confirm
purchases.orders.create
purchases.orders.approve
purchases.receipts.confirm
sales.orders.create
sales.documents.issue
sales.documents.cancel
sales.credit_notes.issue
cash.movements.create
cash.movements.reverse
cash.closings.execute
production.mortality.record
production.feed.record
costs.recalculate
reports.profitability.read
reports.export
backups.execute
```

El catálogo definitivo se versionará como seed idempotente.

## Auditoría

`audit_events` es append-only para operaciones de negocio exitosas y participa en la misma UoW. `security_events` registra de forma durable, después del resultado y en transacción independiente, login fallido, 401/403 y operaciones revertidas; así el rollback de negocio no elimina evidencia.

El rol runtime solo puede insertar auditoría, no actualizarla o borrarla. `audit.read` habilita consulta y un permiso separado habilita exportación. Accesos/exportaciones también quedan auditados. Antes del piloto se fijan retención, archivo, propietario y mecanismo de verificación de integridad.

Auditoría obligatoria para:

- login correcto/fallido, bloqueo, renovación y revocación;
- denegaciones de autorización;
- usuarios, roles y permisos;
- empresa, impuestos, timbrado y numeración;
- confirmaciones, anulaciones y reversiones;
- inventario, producción, caja, pagos y cierres;
- costos y corridas;
- exportaciones sensibles;
- backups y restauraciones.

No se guardan contraseñas, tokens, secretos, certificados, datos de tarjeta ni payloads indiscriminados. Se usa allowlist y redacción.

## Modelo de amenazas prioritario

| Amenaza | Control principal | Prueba obligatoria |
|---|---|---|
| Fuerza bruta/robo de sesión | Argon2id, rate limit, cookies, rotación y revocación | login, expiración, reutilización, logout |
| IDOR/BOLA | autorización por recurso y acción | matriz negativa por endpoint |
| Manipulación de importes/IVA | recálculo backend, snapshots y estados | payload adulterado rechazado |
| Stock negativo concurrente | locks, constraints y transacción | dos salidas simultáneas |
| Doble confirmación/pago | idempotencia y unique constraints | reintento concurrente |
| Repudio de anulación | motivo y auditoría append-only | evidencia completa de reversión |
| SQL injection | ORM parametrizado y allowlists | SAST y casos maliciosos |
| XSS/CSRF | encoding, CSP, cookie segura y token CSRF | pruebas frontend/API |
| Fuga en logs/backups | redacción, cifrado y permisos | escaneo de logs/artefactos |
| Denegación por reportes | límites, timeouts, índices y pool | volumen representativo |
| Elevación por frontend | backend como autoridad | llamada directa sin permiso |

## Hardening

- TLS obligatorio; HSTS en producción.
- CORS con orígenes exactos.
- CSP, `X-Content-Type-Options`, `Referrer-Policy` y protección de framing.
- PostgreSQL sin exposición pública.
- Usuario runtime sin superusuario; migraciones con identidad separada cuando sea operativo.
- Contenedores no-root, filesystem mínimo y health checks.
- Límites de request, archivos, página y exportación.
- Validación de tipo, tamaño, extensión y nombre de archivos.
- Secretos por entorno/secret manager; `.env` solo local y fuera de Git.
- Dependencias fijadas, SAST, análisis de secretos e imágenes en CI.
- Datos productivos prohibidos en desarrollo y fixtures.

## Gestión de vulnerabilidades

- Hallazgo crítico/alto bloquea la fase y la entrega.
- Hallazgo medio necesita responsable, fecha y aceptación explícita.
- No se silencian escaneos sin justificación versionada y vencimiento.
- Cada release incluye revisión de autenticación, permisos, secretos y dependencias.
- Incidentes siguen runbook de revocación, rotación, contención y evidencia.

## Backups

- Cifrados en reposo y tránsito.
- Acceso separado de la cuenta normal de aplicación.
- Copia fuera del servidor principal.
- Checksums, retención y alertas.
- Restore drill aislado antes del piloto y periódicamente después.
- Restauraciones y accesos quedan auditados.
- El gate de piloto exige restaurar un artefacto cifrado obtenido de la copia externa, probar clave errónea/corrupción y conservar evidencia fechada aprobada.

La herramienta `deploy/backup/` usa `pg_dump` custom, Restic con repositorio/clave en archivos montados, IDs completos y restore solo a una base vacía `avicola_restore_*` distinta de la fuente. El servicio backup es el único que comparte red interna de PostgreSQL y una red de salida controlada. Un repositorio local sintético no demuestra aceptación off-host. La auditoría tiene restricciones validadas de forma y controles append-only de aplicación, pero no una cadena criptográfica de hashes; no describirla como tamper-evident.
