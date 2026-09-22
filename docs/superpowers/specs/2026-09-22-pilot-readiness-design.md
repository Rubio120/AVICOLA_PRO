# Diseño: preparación de piloto de AVÍCOLA PRO

## Propósito

Preparar el estado del repositorio `weekend/autonomous` para una instalación de staging y una futura decisión de piloto. La aplicación debe construirse como imágenes reproducibles, exponerse mediante TLS, mantener PostgreSQL en una red privada y permitir generar, cifrar, transferir y restaurar copias con evidencia verificable.

## Alcance

- Imágenes de backend y frontend con dependencias bloqueadas, usuarios no root, health checks y sin secretos en capas de build.
- Compose de despliegue con proxy TLS, backend/frontend y PostgreSQL no publicado; migraciones como tarea explícita antes de cambiar tráfico.
- Flujo de backup cifrado con repositorio externo configurable, verificación del repositorio, restauración aislada, reconciliación de invariantes y pruebas de clave incorrecta/artefacto alterado.
- Runbooks de instalación, despliegue, rollback, incidente, rotación de secretos, backup y restauración.
- CI para pruebas, escaneo de dependencias, secretos e imágenes; smoke y carga básicos reproducibles.
- Evidencia versionable por release candidate en `artifacts/quality/` sin credenciales ni datos productivos.

## Decisiones de diseño

1. Staging se entrega como despliegue Docker Compose de un solo host con Caddy como proxy TLS. El hostname y correo ACME se suministran fuera del repositorio.
2. PostgreSQL se une solo a una red interna de Compose y no publica un puerto al host en el perfil de staging/producción.
3. Backend y frontend se construyen desde el lockfile. Las imágenes finales no incluyen toolchains de desarrollo ni se ejecutan como root.
4. Secretos sensibles se montan desde archivos externos a Compose; los archivos fuente no se versionan. Las imágenes no contienen `.env` ni claves.
5. Restic cifra los dumps antes de enviarlos a un repositorio remoto seleccionado por configuración. Un repositorio local sintético solo valida el flujo; no constituye evidencia off-host.
6. Restore drill usa una base PostgreSQL aislada, ejecuta reconciliaciones sobre ledger/saldos y health/E2E; no restaura sobre una instancia viva.
7. No se inventan RPO, RTO, retención, owner, aprobador, hostname ni proveedor remoto. Se documentan como decisiones operativas por registrar antes del piloto.

## Seguridad y fallos

- El proxy es el único servicio con puertos públicos.
- Los servicios internos usan redes separadas, health checks, límites y políticas de reinicio explícitas.
- Fallos de migración bloquean el despliegue; rollback revierte tráfico/imágenes sin asumir que una migración de datos sea reversible.
- Fallo de cifrado, transferencia, hash, restore o reconciliación bloquea el backup como válido.
- El repositorio remoto, contraseña de Restic, destinatario/llave de cifrado y secretos de aplicación se proporcionan por canales externos y nunca se imprimen en logs.
- Una copia local, un build correcto o un análisis estático no se presentan como restore off-host aprobado.

## Validación

- `docker compose config` con valores de prueba y comprobación de que PostgreSQL no tiene `ports` en despliegue.
- Build multi-stage y análisis de imagen cuando Docker y acceso a los registries estén disponibles.
- Pruebas de scripts de backup/restore con datos sintéticos, repo local aislado, hash, clave incorrecta y alteración controlada.
- Suite backend/frontend, migración desde la versión anterior soportada, health/smoke, escaneos y carga básica.
- Restore desde un artefacto recuperado de un destino remoto real; firma de aprobación operativa y mediciones RPO/RTO.

## Límites de cierre

El código y la evidencia local pueden dejar el release candidate preparado. El gate de piloto queda abierto hasta contar con dominio/TLS público, almacenamiento off-host real, secretos entregados por canal seguro, RPO/RTO y retención aprobados, responsables identificados, restore drill ejecutado sobre el artefacto remoto y aprobación operativa. No se despliega a producción desde esta tarea.
