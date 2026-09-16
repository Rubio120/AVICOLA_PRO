# Instalación y operación prevista

## Estado

Este documento define el contrato operativo; los scripts y contenedores se crearán en la Fase 1. Actualmente no existe aplicación instalable.

## Entornos

- `development`: servicios locales, logs legibles, datos sintéticos.
- `test`: PostgreSQL efímero y configuración determinista.
- `staging`: equivalente a producción con secretos y datos no productivos.
- `production`: TLS, logs JSON, backups, alertas y configuración validada.

## Requisitos previstos

- Git.
- Python 3.13 compatible y `uv`.
- Node.js LTS y gestor fijado por lockfile.
- Docker Engine/Compose para PostgreSQL y ejecución reproducible.
- PostgreSQL 16+ en producción.

## Configuración

La aplicación fallará al iniciar si faltan claves obligatorias o se detectan valores inseguros. Variables previstas:

```text
APP_ENV
DATABASE_URL
SECRET_KEY
ALLOWED_ORIGINS
COOKIE_SECURE
LOG_LEVEL
TIMEZONE=America/Asuncion
BASE_CURRENCY=PYG
```

El repositorio incluirá `.env.example` sin secretos. Certificados, contraseñas y tokens no se almacenarán en Git ni en `app_settings`.

## Flujo de instalación objetivo

1. Clonar una versión etiquetada.
2. Copiar `.env.example` y proporcionar secretos por canal seguro.
3. Levantar PostgreSQL.
4. Instalar dependencias desde lockfiles.
5. Ejecutar `alembic upgrade head`.
6. Ejecutar seed de permisos/configuración de forma idempotente.
7. Crear el primer administrador con comando de un solo uso.
8. Construir frontend/backend.
9. Iniciar servicios y comprobar health/readiness.
10. Ejecutar smoke tests.

Los comandos exactos se incorporarán y probarán en la Fase 1; este documento se actualizará con evidencia real.

## Migraciones

- Nunca ejecutar cambios manuales de esquema.
- Hacer backup verificado antes de migración productiva.
- Revisar SQL generado.
- Aplicar estrategia expand/migrate/contract.
- Registrar versión, duración y resultado.
- El rollback de aplicación no presupone downgrade de datos; cada release define su runbook.

## Backup y restauración

Política inicial de diseño; antes del piloto sus valores se convierten en objetivos firmes con owner y aprobador:

- `pg_dump --format=custom` diario, cifrado.
- Retención base: 7 diarios, 4 semanales y 12 mensuales, sujeta a aprobación formal antes del piloto.
- Copia fuera del host principal.
- Checksums y alerta ante fallo.
- Restore drill antes del piloto y de forma periódica.

Validación de restauración:

1. Recuperar un artefacto cifrado real desde la copia externa y validar hash.
2. Restaurar en PostgreSQL aislado con versiones/extensiones compatibles.
3. Validar esquema/migración, configuración no secreta y disponibilidad de secretos por canal independiente.
4. Reconciliar stock cantidad/valor, aves, caja, AR/AP y auditoría.
5. Iniciar aplicación restaurada y ejecutar smoke/E2E críticos.
6. Probar detección de artefacto corrupto y clave incorrecta.
7. Registrar fecha, RPO/RTO observados, owner, aprobador y evidencia.

## Despliegue inicial

Un servidor Linux podrá ejecutar proxy TLS, frontend, backend y PostgreSQL o conectarse a una base administrada. PostgreSQL no se expondrá públicamente. Los contenedores se ejecutarán sin root, con health checks, límites y volúmenes explícitos.

## Observabilidad y runbooks

- Logs JSON centralizables y correlation ID.
- Métricas de disponibilidad, errores, latencia, pool, locks, jobs outbox y backups.
- Alertas por errores elevados, falta de backup, disco, conexiones y outbox estancada.
- Runbooks: despliegue, rollback, backup, restore, incidente, rotación de secretos y desactivación de usuario.
