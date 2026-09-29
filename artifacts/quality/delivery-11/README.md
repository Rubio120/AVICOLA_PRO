# Evidencias de Entrega 11

Este directorio conserva evidencias de integración y recuperación generadas con datos y credenciales sintéticos. No incluir secretos, datos personales ni exportaciones de infraestructura real.

## Integración Compose

El workflow `quality`, job `deployment-images`, construye y escanea los tres tags `:ci` y después inicia una pila aislada con `deploy/compose/compose.ci.yml`. Comprueba readiness de base de datos, backend y frontend, migración `0010_costing`, bootstrap del administrador sintético, cambio obligatorio de contraseña, login, `/me`, logout y revocación de sesión. `db` y `backend` deben carecer de puertos publicados al host. Un paso `always()` elimina los contenedores y volúmenes del proyecto efímero.

## Estado de verificación

- Regresiones estructurales de Compose, imagen y flujo de backup/restore están en el worktree `weekend/autonomous`.
- Ejecución sintética real de Compose y backup/restore en GitHub Actions sigue pendiente de un `deployment-images` verde. El último run disponible `35890371500` se detuvo construyendo Restic; por eso sus smokes y scans quedaron omitidos.
- Un resultado local o un workflow omitido no cuenta como aprobación. Los logs y artifacts del primer run verde para el SHA exacto serán la evidencia de ejecución.

## Respaldo y restauración sintéticos

El job `deployment-images` inicializa un repositorio Restic local efímero con contraseña aleatoria, genera un snapshot PostgreSQL cifrado, restaura en `restore-db` bajo un nombre desechable y exige nueve conciliaciones. También prueba que una clave equivocada y un repositorio alterado fallen. Comparte job con los tags `:ci` recién construidos y escaneados, sin intentar descargar imágenes desde otro job. La limpieza elimina únicamente el proyecto Compose y las carpetas sintéticas de ese job.

- Estado: pendiente de ejecución satisfactoria en CI para un commit que incluya esta prueba.
- Límite: este ensayo local de CI no prueba almacenamiento off-host, permisos de cuenta externa ni RPO/RTO reales.
