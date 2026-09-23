# Evidencia local - backup y restore Restic

Fecha: 2026-09-22 (-03). Laboratorio local en Windows; no se usaron datos de produccion.

## Alcance y resultado

- Fuente: base sintetica `avicola_pro_test`, PostgreSQL 16.14, head Alembic `0010_costing`.
- Restic portable 0.19.1 para Windows x86_64. El ZIP oficial se contrasto con el SHA-256 de su manifiesto WinGet antes de extraerlo.
- El flujo directo inicial creo un repositorio Restic cifrado, leyo todos los datos con `restic check --read-data`, restauro el archivo y verifico su integridad con `pg_restore --list`; el hash del archivo fuente y su copia restaurada coincidio.
- Se ejercitaron tambien los entrypoints del proyecto: `deploy.backup.backup.main()` y `deploy.backup.restore.main()`. El backup produjo el snapshot `06bb5941e68cfc1cadc2125718c9622370ea8268be101d1fcd71daf8f4792839`; Restic verifico el repositorio, `check --read-data` paso y `pg_restore --list` acepto el archivo de 194063 bytes.
- El entrypoint de restore recupero ese snapshot a una nueva base local desechable `avicola_restore_d11_script`. Las nueve reconciliaciones pasaron. SHA-256 reportado: `3fc752dd346c416f592160f5336d9577c0424d9b8060b4a1dc642865f10147ae`. Se elimino unicamente esa base sintetica, creada para el ejercicio.
- En otro repositorio aislado, Restic rechazo una clave equivocada. Luego rechazo una copia con un byte alterado intencionalmente; el repositorio intacto de ese ejercicio siguio pasando su verificacion completa.
- La prueba descubrio dos defectos reales: los valores de service file de libpq estaban entrecomillados (las comillas se interpretaban literalmente), y Restic recibia a la vez `RESTIC_REPOSITORY` y `RESTIC_REPOSITORY_FILE`. Se corrigio la serializacion INI y ambos entrypoints ahora resuelven el archivo de repositorio antes de invocar Restic. Las regresiones estan cubiertas por pruebas.

## Limites

Las pruebas usaron un repositorio en el mismo host y solo la base sintetica. El restore local no demuestra almacenamiento off-host, CI/provenance autenticada, staging, RPO/RTO aprobados ni aceptacion de negocio. En Windows se sustituyeron las rutas de binarios Linux del contenedor por los ejecutables PostgreSQL locales; el orquestador y las verificaciones del proyecto fueron ejecutados. No constituye autorizacion para activar el piloto.
