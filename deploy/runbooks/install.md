# Instalación de staging

Este procedimiento es para un staging aislado. No ejecutarlo en producción sin aprobación del owner y del aprobador nombrados; no ejecutar sobre un host real hasta que el usuario elija la ventana y los responsables confirmen los prerrequisitos. No es una orden de despliegue ni se ejecuta desde CI.

## Requisitos previos

- Docker Engine y Docker Compose v2 compatibles con `docker compose config`.
- DNS público de `APP_DOMAIN` apuntando a este host; entrada TCP 80/443 y UDP 443 habilitada.
- Referencias de imagen por digest SHA-256 publicadas y aprobadas por CI, un repositorio Restic remoto y una cuenta PostgreSQL dedicada.
- Secretos entregados por un gestor seguro, nunca pegados en comandos, tickets, Git o archivos `.env`.
- Decisiones registradas de RPO, RTO, retención, owner, aprobador y fecha de activación.
- Gate RC local con `technical_status: ready_for_user_deployment` para el commit/ref/tag exactos y evidencia CI reciente. La atestación no sustituye la revisión humana.
- Imágenes publicadas voluntariamente en un registry autorizado y referenciadas por sus digests reales. La CI de este proyecto solo conserva artifacts; no publica imágenes.

## Preparar configuración

1. Obtener la versión revisada del repositorio y copiar `deploy/compose/.env.production.example` a `deploy/compose/.env.production` fuera de Git.
2. Sustituir el dominio, usuario/base de PostgreSQL y las tres referencias de imagen por digests publicados (backend, frontend y backup). No usar tags mutables ni guardar contraseñas/tokens en ese archivo.
3. Crear fuera del repositorio `secrets/postgres_password`, `secrets/database_url`, `secrets/session_hmac_key`, `secrets/restic_repository` y `secrets/restic_password`.
4. El URL de base debe usar `postgresql+psycopg://` y el host interno `db`; su contraseña debe coincidir con `postgres_password`. Los archivos secretos deben contener un valor, sin saltos de línea finales.
5. `session_hmac_key` debe ser Base64 URL-safe canónico sin relleno, representar al menos 32 bytes aleatorios y no ser una clave de ejemplo. En Linux, restringir lectura: `postgres_password` solo root (0400); `database_url` y `session_hmac_key` root:10001 (0440); `restic_repository` y `restic_password` root:10002 (0440). No hacerlos legibles por todos.
6. Confirmar que el archivo de repositorio Restic señala un destino remoto cifrado y que sus credenciales remotas están disponibles por el canal aprobado.

## Revisar y levantar

```sh
docker compose --file deploy/compose/compose.production.yml --env-file deploy/compose/.env.production config --quiet
docker compose --file deploy/compose/compose.production.yml --file deploy/backup/compose.backup.yml --env-file deploy/compose/.env.production pull
docker compose --file deploy/compose/compose.production.yml --env-file deploy/compose/.env.production up -d
```

Los Dockerfiles deben construirse y escanearse en CI antes de staging; el workflow no publica imágenes. El operador solo configura digests después de publicarlos por el proceso autorizado. No se construyen imágenes nuevas en el host de despliegue. El archivo de ejemplo contiene referencias `.invalid` únicamente para permitir el render estructural y jamás debe usarse para arrancar servicios.

El servicio `migrate` debe terminar con código cero antes de que `backend` pase readiness y `frontend` reciba tráfico. Solo `proxy` publica puertos. Confirmar el certificado HTTPS, readiness, login con una cuenta de prueba y el smoke de `deploy/performance/smoke.js` antes de aceptar staging.

Un staging exitoso no aprueba un piloto ni producción. Preservar commit/tag, digests reales, migración, reportes, resultado de restore y aprobaciones operativas. Si falta un prerrequisito, no levantar el stack.
