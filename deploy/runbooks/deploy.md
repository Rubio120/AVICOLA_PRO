# Despliegue

Este runbook es una referencia manual. No lo ejecuta CI y no autoriza un despliegue. El proyecto aún no publica sus imágenes; no ejecutar `pull` hasta que el usuario las publique voluntariamente en un registry autorizado y configure digests reales.

## Antes del cambio

- Confirmar tag/commit aprobado, imágenes construidas y escaneos vigentes.
- Verificar el artifact firmado con `scripts/release-gate.ps1` / `scripts/release-gate.sh`; exigir `ready_for_user_deployment` para el commit, ref, tag y Alembic head esperados.
- Confirmar backup remoto reciente y que un restore drill pasó reconciliación.
- Registrar owner, ventana, RPO/RTO acordados y plan de comunicación.
- Revisar cambios Alembic y compatibilidad hacia atrás; un downgrade de esquema no es el plan de rollback.

## Aplicar

```sh
docker compose --file deploy/compose/compose.production.yml --env-file deploy/compose/.env.production pull
docker compose --file deploy/compose/compose.production.yml --env-file deploy/compose/.env.production up -d
docker compose --file deploy/compose/compose.production.yml --env-file deploy/compose/.env.production ps
```

Compose ejecuta `migrate` y solo inicia `backend` cuando la migración termina correctamente. Si falla, no derivar tráfico ni repetir con cambios manuales en la base.

Verificar readiness por HTTPS, smoke básico, login/CSRF/RBAC con una cuenta no privilegiada, y una lectura de dashboard. Confirmar logs sin secretos, alertas activas y ausencia de puertos publicados salvo 80/443 TCP y 443 UDP en `proxy`.

## Cerrar

Guardar commit, tags y digests desplegados, cabecera Alembic, resultados de pruebas/smoke, hora inicio/fin y actor aprobador. No registrar URLs con credenciales, cookies, tokens, claves ni datos reales de aves/clientes.
