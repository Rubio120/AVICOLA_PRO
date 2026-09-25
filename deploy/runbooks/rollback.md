# Rollback de aplicación

Ejecutar solo con incidente confirmado, aprobador/owner disponibles e imagen previa por digest verificado. Un digest no publicado ni una imagen local efímera no son alternativa de rollback.

1. Declarar el incidente y detener cambios concurrentes. Si hay riesgo de escritura corrupta, pausar el tráfico en el proxy y escalar al owner.
2. Confirmar el último backup remoto comprobado y conservar evidencia/logs no sensibles.
3. Cambiar `BACKEND_IMAGE_REF` y `FRONTEND_IMAGE_REF` en el archivo externo `deploy/compose/.env.production` a los digests exactos de la versión anterior aprobada.
4. Revisar si las migraciones nuevas son compatibles con la versión anterior. No ejecutar `alembic downgrade` automáticamente.
5. Aplicar la imagen previa:

```sh
docker compose --file deploy/compose/compose.production.yml --env-file deploy/compose/.env.production up -d
```

6. Verificar readiness, smoke y escrituras críticas antes de abrir tráfico. Si el código anterior no es compatible con el esquema actual, mantener el servicio pausado y ejecutar el plan de recuperación aprobado.
7. Restaurar datos solo en una base aislada y siguiendo `restore.md`; nunca usar el script de restore sobre la base viva.
8. Registrar alcance, versiones, datos afectados, tiempos, aprobaciones y acciones preventivas.
