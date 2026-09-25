# Instalación y operación prevista

## Estado

La base técnica de la Entrega 1 es instalable desde lockfiles y fue verificada en Windows con Python 3.13.15, `uv` 0.12.15, Node.js 22.23.2, npm 10.9.8 y PostgreSQL 16.14.

En equipos donde PowerShell aplique política `Restricted`, ejecute los scripts propios sin cambiar la política global:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\clean-install.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\db-up.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\migrate.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check.ps1
```

En Windows el script de backend configura un Selector event loop compatible con Psycopg async.

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

La aplicación fallará al iniciar si faltan claves obligatorias o se detectan valores inseguros. Variables implementadas en Entrega 1 (prefijo `AVICOLA_`):

```text
AVICOLA_ENVIRONMENT
AVICOLA_DATABASE_URL
AVICOLA_CORS_ORIGINS
AVICOLA_LOG_LEVEL
AVICOLA_LOG_FORMAT
AVICOLA_TIMEZONE=America/Asuncion
AVICOLA_BASE_CURRENCY=PYG
```

La configuración de producción vive en `deploy/compose/compose.production.yml`: establece ambiente `production`, logs JSON, cookie Secure y CORS limitado al dominio configurado. La URL de base y HMAC se cargan desde archivos secretos externos; no se escriben en argumentos, Docker build args ni en el archivo de entorno versionado.

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

Los scripts de la raíz implementan en Entrega 1 los pasos 2-5 y las comprobaciones técnicas de los pasos 8-10. El seed de permisos y el primer administrador (pasos 6-7) pertenecen a Entrega 2. Docker Compose permanece disponible para entornos con Docker; la verificación local del 2026-09-16 usó el PostgreSQL 16.14 empaquetado para pruebas porque Docker no estaba disponible en la máquina.

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

La topología Compose y los pasos de secretos, puesta en marcha, rollback, incidentes y restore están en `deploy/runbooks/`. Caddy termina TLS y reenvía todo al frontend/BFF; el frontend accede al backend solo por una red privada. La computadora de desarrollo actual no tiene Docker, por lo que los builds/configuración de imagen aún deben verificarse en CI o en un host Docker.

## Observabilidad y runbooks

- Logs JSON centralizables y correlation ID.
- Métricas de disponibilidad, errores, latencia, pool, locks, jobs outbox y backups.
- Alertas por errores elevados, falta de backup, disco, conexiones y outbox estancada.
- Runbooks: despliegue, rollback, backup, restore, incidente, rotación de secretos y desactivación de usuario.
