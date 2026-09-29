# Diseño: cierre técnico de Entregas 11 y 12

**Fecha:** 2026-09-23  
**Estado:** alcance aprobado por el usuario para integrar D11 y D12 con las entregas 0-10  
**Rama:** `weekend/autonomous`

## Objetivo

Completar el trabajo técnico de las Entregas 11 (preparación del piloto) y 12 (gate final y paquete de liberación) de AVÍCOLA PRO, para que el usuario pueda decidir y ejecutar posteriormente el despliegue. En esta fase no se despliega a producción, no se aprovisiona infraestructura productiva, no se cargan imágenes a un registro de producción y no se usan datos ni secretos reales.

## Estado de partida

Las Entregas 0-10 están cerradas según `PROJECT_STATUS.md`. La rama `weekend/autonomous` ya contiene Dockerfiles, Compose de producción, proxy/TLS, manejo de secretos por archivos, scripts de backup/restore, runbooks y un gate RC/piloto. Las pruebas locales del backend, frontend y restauración sintética han pasado. En la última corrida CI consultada, PostgreSQL, Windows, dependencias, análisis de código y Compose pasaron; el gate de imágenes falló por resultados HIGH/CRITICAL en backend, frontend y backup. El validador D12 comprueba integridad del paquete local, pero no certifica todavía procedencia confiable de los artefactos ni una restauración real fuera del equipo.

## Alcance propuesto

### Entrega 11 — Preparación y pruebas del piloto

- Corregir causas de vulnerabilidades confirmadas en las tres imágenes; mantener el gate bloqueante para hallazgos HIGH/CRITICAL accionables. No silenciar resultados para obtener CI verde.
- Validar build Docker de backend, frontend y backup, la topología Compose, arranque/migración, health/readiness, smoke autenticado con cuentas sintéticas, parada y rollback documentados.
- Probar backup/restauración cifrados y conciliaciones en un entorno de CI aislado con datos sintéticos. Si se usa un servicio S3 compatible efímero para probar almacenamiento separado, documentar expresamente que no equivale a una restauración en la cuenta externa que se usará en producción.
- Actualizar runbooks y evidencia de pruebas para que cada resultado corresponda al mismo commit y a los artefactos probados.

### Entrega 12 — Release candidate y decisión de liberación

- Construir un paquete de evidencia verificable para un commit/tag exactos: resultados de pruebas, reportes de análisis, SBOM, digests inmutables de backend/frontend/backup y procedencia ligada al workflow y al commit.
- Endurecer el gate para comprobar criptográficamente la identidad/procedencia admitida y bloquear evidencia vieja, incompleta o discordante. No aceptar como prueba un estado escrito manualmente en JSON.
- Generar un informe RC `ready` solo cuando todos los gates técnicos aprobados pasen; de otro modo conservar estado bloqueado y enumerar causas.
- Entregar instrucciones reproducibles para que el usuario realice, cuando lo decida, publicación de imágenes y despliegue. No ejecutar esos pasos dentro de este alcance.

## Límites y dependencias externas

La preparación y certificación técnica en CI puede completarse sin infraestructura productiva. No se afirmará que el sistema ya fue desplegado, que se probó con una cuenta real de backup fuera del equipo, ni que existe aprobación operativa. La validación final de dominio/TLS real, registro de imágenes elegido, secreto de producción, backup externo, RPO/RTO, retención, owner/aprobador, carga representativa y restore drill en el entorno del usuario corresponde a una etapa posterior bajo su control. Los valores y aprobaciones no se inventarán.

Un resultado técnico verde significará “paquete técnicamente preparado para que el usuario despliegue siguiendo el runbook”, no “producción ya certificada” ni “piloto aprobado”.

## Criterios de aceptación

1. CI ejecuta y pasa backend PostgreSQL, frontend, análisis de dependencias/código, builds de las tres imágenes, configuración Compose, smoke de despliegue y prueba sintética de backup/restore.
2. El escaneo no contiene hallazgos HIGH/CRITICAL accionables; ningún hallazgo se excluye solo para hacer pasar el gate. Cualquier excepción requiere evidencia técnica y aprobación explícita antes de tratarla como aceptada.
3. Cada reporte, SBOM, digest y procedencia se relaciona inequívocamente con el mismo SHA de commit; se verifica autenticidad, no solo hashes declarados por el propio bundle.
4. El gate RC rechaza evidencia ausente, manipulada, vencida, de otro commit o con resultados de seguridad fallidos; emite un informe nuevo sin sobrescribir evidencia previa.
5. Los runbooks de instalación, despliegue, verificación, rollback, incidentes y restore concuerdan con los comandos y archivos actuales; no contienen valores productivos ficticios.
6. La rama queda con cambios guardados y el estado/evidencia actualizados. Ningún despliegue real o publicación a un registro productivo ocurre como parte del trabajo.

## Decisiones que no se cambiarán silenciosamente

- Se mantiene la arquitectura monolítica y Docker Compose existente; migrar a Kubernetes o a servicios administrados queda fuera de alcance.
- Se mantienen versiones fijadas y builds reproducibles donde el proyecto ya los define; cambios de imagen base o toolchain requieren evidencia del escaneo y pruebas.
- La política de seguridad sigue siendo fail-closed.
- Cualquier dato/credencial/valor operacional real queda a cargo del usuario y fuera del repositorio.

## Revisión

El usuario aprobó el 2026-09-23 completar e integrar las Entregas 11 y 12 con el resto del proyecto. "Listo" significa preparación técnica verificable para el despliegue posterior por el usuario, sin ejecutar el despliegue ni publicar a un registro de producción; las validaciones y aprobaciones ligadas a infraestructura real quedan para esa etapa posterior.
