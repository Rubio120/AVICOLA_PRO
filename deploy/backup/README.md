# Operaciones de respaldo cifrado

El servicio de respaldo usa Restic para cifrar snapshots de `pg_dump` y ejecuta `restic check` al terminar. La restauración exige un snapshot ID completo y una base vacía con nombre `avicola_restore_<identificador>`; valida que el destino sea distinto del origen, verifica la integridad del repositorio y del archivo antes de restaurar, y corre nueve conciliaciones de la aplicación. No usa `--clean`, `--create`, ni borra o modifica la base de origen.

El flujo operativo y sus permisos están descritos en [`deploy/runbooks/restore.md`](../runbooks/restore.md). Las credenciales Restic y las URL de base se suministran como archivos montados y nunca deben guardarse en el repositorio.

## Alcance de CI

GitHub Actions crea un repositorio Restic local y efímero con clave aleatoria, toma un snapshot de una base PostgreSQL sintética, restaura en otro servicio/base de CI y exige las nueve conciliaciones. También verifica que una clave incorrecta y un repositorio dañado sean rechazados. Este ensayo valida el mecanismo, pero no acredita una copia off-host, una restauración en infraestructura real ni objetivos RPO/RTO de producción. La evidencia de cada ejecución se conserva como artifact de CI sin URL ni claves.
