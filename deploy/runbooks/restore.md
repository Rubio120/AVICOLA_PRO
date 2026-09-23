# Backup y restore drill

## Generar backup

El backup es una acción explícita; no se ejecuta al levantar la aplicación. El repositorio y la clave se montan desde archivos secretos externos. No configurar el repositorio Restic como una carpeta del mismo host y llamarlo “off-host”.

Inicializar una sola vez, con destino remoto aprobado y credenciales ya instaladas:

```sh
docker compose --file deploy/compose/compose.production.yml --file deploy/backup/compose.backup.yml --env-file deploy/compose/.env.production --profile operations run --rm --entrypoint /usr/bin/python3 backup -m deploy.backup.initialize_repository
```

Si el repositorio ya existe, no volver a inicializarlo; continuar al paso de backup.

```sh
docker compose --file deploy/compose/compose.production.yml --file deploy/backup/compose.backup.yml --env-file deploy/compose/.env.production --profile operations pull backup
docker compose --file deploy/compose/compose.production.yml --file deploy/backup/compose.backup.yml --env-file deploy/compose/.env.production --profile operations run --rm backup
```

Guardar el `snapshot_id`, hora UTC, commit, estado de `restic check` y ubicación lógica sin credenciales. Retención/prune está intencionalmente deshabilitado hasta aprobación de owner y aprobador.

## Restaurar a un target desechable

1. Crear una base vacía en un PostgreSQL aislado, con nombre `avicola_restore_<identificador>`, y un URL secreto de solo uso en un archivo fuera de Git.
2. Confirmar que la dirección de host/base del target es distinta de la base fuente. El contenedor backup debe resolver ambos hosts por una red privada; no publicar el puerto del target.
3. Seleccionar el ID completo de 64 caracteres del backup y proteger el archivo URL para que el usuario de backup (UID/GID 10002) pueda leerlo: propietario root, grupo 10002, modo 0440, o ACL equivalente. El grupo 10001 solo se añade para leer el URL de origen del servicio.
4. El procedimiento valida Restic con lectura completa, extrae/verifica el archivo y comprueba que el target no tenga tablas antes de ejecutar `pg_restore`. No emplea `--clean`, `--create` ni downgrade.

```sh
docker compose --file deploy/compose/compose.production.yml --file deploy/backup/compose.backup.yml --env-file deploy/compose/.env.production --profile operations run --rm --entrypoint /usr/bin/python3 --volume "$RESTORE_TARGET_DATABASE_URL_FILE:/run/secrets/restore_target:ro" --env RESTORE_TARGET_DATABASE_URL_FILE=/run/secrets/restore_target --env RESTORE_TARGET_DATABASE_NAME="$RESTORE_TARGET_DATABASE_NAME" --env RESTORE_SNAPSHOT_ID="$RESTORE_SNAPSHOT_ID" backup -m deploy.backup.restore
```

5. Confirmar nueve reconciliaciones: cantidades/valores de inventario, ledger avícola, sesiones de caja cerradas, AP/AR, asignaciones de pago y restricciones de forma/resultado de auditoría. Las restricciones de auditoría no son una cadena criptográfica; el esquema no la implementa.
6. Ejecutar readiness y smoke en ese staging aislado. Registrar snapshot, hash del archivo restaurado obtenido por canal de evidencia, commit, versión PostgreSQL, hora/duración, resultado, RPO/RTO observados, owner y aprobador.
7. Destruir el target solo después de guardar evidencia aprobada, mediante el procedimiento del host para bases desechables. No borrar volúmenes productivos.

Un repositorio local sintético, este restore drill por sí solo o una copia del mismo host no cuentan como aceptación off-host.
