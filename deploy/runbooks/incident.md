# Incidentes operativos

## Primeros pasos

- Confirmar severidad, alcance, hora de inicio y responsable que coordina.
- Ante sospecha de exposición, revocar/rotar el secreto comprometido por el gestor seguro; no copiarlo al ticket ni a los logs.
- Ante corrupción de escrituras, detener el tráfico en `proxy`; no borrar contenedores, volúmenes, eventos ni filas.
- Preservar logs de contenedor y host con acceso limitado; redactar cookies, `Authorization`, URLs, datos personales y financieros.
- Revisar healthchecks, migración, espacio libre, conectividad PostgreSQL y estado del repositorio remoto. No ejecutar `prune`, `forget`, downgrade o restauración improvisada.
- Notificar al owner/aprobador por el canal interno aprobado y conservar decisiones/timestamps.

## Recuperación

1. Si es fallo de aplicación sin corrupción, seguir `rollback.md`.
2. Si se sospecha corrupción o pérdida, congelar cambios y seguir `restore.md` en un target aislado.
3. Abrir tráfico solo tras reconciliación, smoke autenticado, revisión de permisos/auditoría y aprobación explícita.
4. Documentar causa raíz, impacto, evidencia, RPO/RTO observado y acciones correctivas.

No existe envío automático a un sistema de alertas todavía: antes del piloto deben configurarse destinatarios, umbrales, guardia y prueba de entrega fuera del repositorio.
