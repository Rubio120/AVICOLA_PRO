# Evidencias de Entrega 11

Este directorio conserva evidencias de integración y recuperación generadas con datos y credenciales sintéticos. No incluir secretos, datos personales ni exportaciones de infraestructura real.

## Integración Compose

El workflow `quality`, job `deployment-images`, construye y escanea los tres tags `:ci` y después inicia una pila aislada con `deploy/compose/compose.ci.yml`. Comprueba readiness de base de datos, backend y frontend, migración `0010_costing`, bootstrap del administrador sintético, cambio obligatorio de contraseña, login, `/me`, logout y revocación de sesión. `db` y `backend` deben carecer de puertos publicados al host. Un paso `always()` elimina los contenedores y volúmenes del proyecto efímero.

## Estado de verificación

- Regresión estructural local: pendiente de incorporar al commit de Task 2.
- Ejecución real de Docker Compose en GitHub Actions: pendiente de CI para el commit que incorpore este cambio.
- Los logs y resultados de CI son la fuente de evidencia de la ejecución; no se afirma que la integración haya pasado hasta que ese job termine satisfactoriamente.
