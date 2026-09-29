# Entrega 2 — Diseño de Identidad, RBAC y Auditoría

**Fecha:** 2026-09-17

**Estado:** aprobado
**Alcance:** exclusivamente Entrega 2

## Objetivo

Incorporar identidad, autorización granular y evidencia inmutable a la base técnica de AVÍCOLA PRO. La solución debe ser segura para una única empresa, revocable en tiempo real y reutilizable por todos los módulos posteriores.

## Arquitectura

`identity` posee usuarios, roles, permisos y sesiones. `audit` posee los eventos funcionales y de seguridad. La API aplica autenticación y autorización antes de invocar servicios de aplicación; el frontend solo adapta la experiencia, nunca decide permisos.

La autenticación usa una sesión opaca completamente estatal. El navegador recibe un identificador aleatorio de alta entropía en cookie `HttpOnly`, `SameSite=Lax`, `Path=/`; `Secure` es obligatorio fuera del entorno local y configurable para pruebas locales. PostgreSQL conserva únicamente un hash con clave del identificador, nunca el valor utilizable. Cada renovación rota el identificador dentro de una familia. Presentar un identificador ya rotado se considera reutilización y revoca inmediatamente toda la familia.

Las operaciones mutables requieren un token CSRF independiente, ligado a la sesión y comparado en tiempo constante. Cierre de sesión, cambio de contraseña, desactivación, incidente o reutilización revocan de inmediato las sesiones afectadas.

## Modelo de datos

- `users`: identificadores UUID, username y email normalizados, nombre, hash Argon2id, activo, cambio obligatorio, intentos fallidos, bloqueo temporal, versión y timestamps.
- `roles`: código estable, nombre, descripción, rol de sistema, activo y timestamps.
- `permissions`: clave estable `recurso.accion`, descripción y timestamps.
- `user_roles` y `role_permissions`: claves compuestas, FKs restrictivas y timestamps de asignación.
- `sessions`: hash del identificador, hash CSRF, familia, usuario, creación, uso, expiración absoluta/ociosa, rotación, revocación, IP y user-agent acotados.
- `audit_events`: actor y snapshot, acción, recurso, identificador, resultado, correlación, IP/agent, before/after redactado y fecha. Solo inserción.
- `security_events`: actor opcional, tipo, resultado, correlación, IP/agent, metadatos permitidos y fecha. Solo inserción.

La migración crea restricciones, índices y protección append-only mediante triggers PostgreSQL que rechazan `UPDATE` y `DELETE`. El seed de permisos y roles de sistema es idempotente.

## Contraseñas y administrador inicial

Las contraseñas usan Argon2id y una política de longitud mínima más rechazo de contraseñas comunes; nunca se registran ni retornan salvo la contraseña temporal del bootstrap, mostrada una única vez por consola. El CLI genera esa contraseña con `secrets`, guarda solamente su hash, marca `must_change_password=true` y audita la creación sin datos sensibles.

El bootstrap se ejecuta en una transacción con bloqueo asesor y comprueba la existencia de cualquier administrador inicial/superadministrador. Repetirlo se detiene de forma segura sin crear ni modificar cuentas. El primer login solo habilita consultar la sesión, cambiar la contraseña y cerrar sesión. El cambio exitoso reemplaza el hash, limpia el indicador y revoca todas las sesiones; la contraseña temporal deja de ser válida.

## RBAC

El catálogo de permisos es explícito e idempotente. Como mínimo incluye gestión separada de usuarios, roles, lectura de auditoría y sesión propia. El policy service carga permisos efectivos de roles activos para un usuario activo y niega por defecto. Cada endpoint protegido declara un permiso concreto. Cambiar roles o permisos requiere `roles.manage`, evita retirar el último administrador activo y se audita en la misma transacción.

## API y errores

Endpoints previstos:

- `POST /api/v1/auth/login`, `POST /refresh`, `POST /logout`, `POST /change-password`, `GET /me`.
- CRUD administrativo controlado para `/api/v1/users`, `/roles` y consulta de `/permissions`.
- consulta paginada y filtrada de `/api/v1/audit-events` con `audit.read`.

Credenciales inválidas producen respuesta genérica. Errores siguen Problem Details, incluyen correlation ID y no filtran hashes, tokens ni existencia de cuentas. Login aplica limitación progresiva por combinación de identidad normalizada e IP.

## Auditoría

Cambios exitosos de usuarios/RBAC y bootstrap insertan `audit_events` dentro de la misma unidad de trabajo. Login, logout, renovación, bloqueo, reutilización, 401 y 403 insertan `security_events` mediante una transacción independiente después del resultado. Los payloads usan allowlist; quedan prohibidos contraseñas, cookies, tokens y hashes.

## Frontend

Se incorpora login, cambio obligatorio de contraseña, sesión actual y cierre de sesión. La navegación respeta permisos para visibilidad, pero toda decisión de seguridad permanece en backend. Estados de carga, error, expiración y denegación son accesibles y consistentes con el diseño existente.

## Pruebas y calidad

La implementación seguirá TDD. Habrá pruebas unitarias e integración PostgreSQL para hash/verificación, bootstrap único, login válido/inválido, bloqueo, usuario inactivo, rotación/reutilización, CSRF, logout, cambio obligatorio, matriz 401/403, escalamiento, cambios RBAC, regla del último administrador, auditoría atómica/append-only y migración desde base vacía. El frontend probará login, cambio obligatorio, errores y permisos visibles.

El cierre exige cobertura sin reducir umbrales, Ruff, formato, Mypy estricto, ESLint, TypeScript, build de producción, migraciones limpias, health checks, análisis de dependencias/secretos y revisión independiente.

## Fuera de alcance

No se implementan configuración empresarial, terceros, catálogo, inventario, compras, ventas, producción ni la Entrega 3. Tampoco MFA, recuperación por email, SSO ni multiempresa.
