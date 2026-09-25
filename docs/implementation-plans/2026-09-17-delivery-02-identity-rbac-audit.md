# Entrega 2 — Plan de implementación

> Ejecutar con TDD, en `delivery/02-identity-rbac-audit`, sin avanzar a Entrega 3.

**Objetivo:** entregar identidad, sesiones opacas, RBAC y auditoría append-only verificadas de extremo a extremo.

## 1. Línea base y dependencias

- Ejecutar `scripts/bootstrap.ps1` y `scripts/check.ps1` en el worktree limpio.
- Agregar dependencias mínimas para Argon2id y CLI, actualizar `uv.lock` y ejemplos de configuración sin secretos.
- Escribir primero pruebas de configuración segura; comprobar RED y luego GREEN.
- Commit y push del diseño/plan y de la base reproducible.

## 2. Esquema PostgreSQL y migración

- Escribir pruebas de migración para tablas, constraints, índices, seed idempotente y protección append-only.
- Crear modelos SQLAlchemy compartidos por los repositorios.
- Crear migración `0002_identity_rbac_audit` con usuarios, roles, permisos, asociaciones, sesiones y eventos.
- Ejecutar upgrade desde base vacía, downgrade/upgrade y pruebas de integridad.
- Actualizar documentos, commit y push.

## 3. Dominio y seguridad de credenciales

- Pruebas RED para normalización, política de contraseña, Argon2id y generación temporal.
- Implementar tipos/servicios puros y errores de dominio.
- Pruebas RED para bootstrap único, cambio obligatorio y no exposición de secretos.
- Implementar CLI transaccional con bloqueo, auditoría allowlist y salida única.

## 4. Sesiones y autenticación API

- Pruebas RED para login válido/inválido/inactivo/bloqueado y respuesta genérica.
- Implementar repositorios, servicio de autenticación y rate limiting persistente.
- Pruebas RED para cookie, CSRF, rotación, reutilización, logout, expiración y revocación.
- Implementar sesión opaca con hashes, familias y comparación constante.
- Pruebas RED para `must_change_password`; implementar guard restringido y revocación tras cambio.

## 5. RBAC y administración

- Pruebas RED de deny-by-default, permisos efectivos, usuario/rol inactivo, 401/403 y bypass directo.
- Implementar dependencias FastAPI y policy service exclusivamente backend.
- Pruebas RED para gestión de usuarios, roles y permisos, incluyendo escalamiento y último administrador.
- Implementar endpoints y servicios transaccionales con DTOs estrictos.

## 6. Auditoría

- Pruebas RED para auditoría en la misma UoW, rollback, canal independiente y redacción.
- Implementar writers y consulta paginada protegida por `audit.read`.
- Verificar en PostgreSQL que `UPDATE`/`DELETE` fallen para ambos registros.

## 7. Frontend

- Pruebas RED de formularios de login/cambio obligatorio, errores, expiración y navegación por permisos.
- Implementar cliente server-side/BFF seguro para cookies y CSRF, pantallas y estados accesibles.
- Ejecutar Vitest con cobertura, ESLint, TypeScript y build.

## 8. Integración y revisión final

- Ejecutar instalación limpia, migraciones desde cero y seed/bootstrap de prueba sin registrar contraseña.
- Ejecutar suite backend completa con cobertura, Ruff format/check y Mypy.
- Ejecutar suite frontend, cobertura, ESLint, TypeScript y build de producción.
- Levantar PostgreSQL/backend/frontend y verificar health/readiness y flujo de autenticación.
- Ejecutar auditoría de dependencias y búsqueda de secretos/artefactos prohibidos.
- Solicitar revisión independiente; corregir hallazgos críticos/importantes con pruebas RED.
- Actualizar `PROJECT_STATUS.md` y `PROJECT_CONTEXT.md`, revisar diff/status, crear commit final y push.
- Confirmar rama remota y árbol limpio; detenerse sin iniciar Entrega 3.
