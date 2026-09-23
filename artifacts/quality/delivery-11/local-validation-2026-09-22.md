# Validación local D11/D12 — 2026-09-22

Alcance: pruebas locales en el árbol de trabajo `weekend/autonomous`, sobre el commit base `efbb0cae2cfb43c0c22cd701ee06b43a30231d65` más cambios locales no confirmados. Esta evidencia no representa una imagen publicada ni aceptación de CI/staging.

## Resultados

- Backend: 199/199 pruebas; cobertura con ramas 80,34 % (gate mínimo 80 %), reejecutado desde `backend/` con su configuración pytest oficial. El test PostgreSQL de idempotencia de pagos de D6 también pasó focalizado (1/1).
- Frontend: 47/47; cobertura 87,79 % de statements y 80,26 % de ramas.
- Ruff, formato Ruff, Mypy, ESLint, TypeScript y build de producción Next.js: correctos.
- Dependencias bloqueadas de producción: `pip-audit` y `npm audit --audit-level=high` sin vulnerabilidades conocidas reportadas.
- Migración PostgreSQL 16.14 desde base vacía hasta `0010_costing`: correcta en una base sintética desechable.
- Upgrade PostgreSQL desde `0009_treasury` hasta `0010_costing`: correcto en una base sintética desechable.
- Smoke local de API y frontend de producción: 20 solicitudes, concurrencia 2, p50 27 ms, p95 72 ms, tasa de error 0. Se omitió autenticación porque no había una cuenta sintética configurada.
- Backup y restore reales del proyecto con Restic 0.19.1: repositorio cifrado verificado, restore en una base recién creada y desechable, lista del archivo aceptada por `pg_restore` y 9/9 conciliaciones aprobadas. La base sintética de destino se eliminó al terminar. Clave equivocada y copia corrupta se rechazaron en verificaciones aisladas.
- Evidencia detallada del roundtrip: [local-roundtrip-2026-09-22.md](backup-restore/local-roundtrip-2026-09-22.md).
- Gate RC enfocado: 23/23 pruebas. El estado informado continúa siendo `manifest_validated`; no certifica procedencia confiable ni readiness.

## Hallazgo manual de seguridad pendiente

La revisión de autorización encontró que los rechazos 403 de los módulos operativos (`inventory`, `production`, `purchasing`, `sales`, `treasury`, `costing`, `settings` y `reporting`) no escriben eventos `authorization.denied` en `security_events`. El flujo administrativo de Identity sí lo hace. Esto no cambia la decisión de permisos ni los cuerpos HTTP; falta acordar e implementar el registro común. No se inventó una matriz de permisos para roles de negocio.

La instrumentación común de esos 403 requiere aprobación del diseño propuesto antes de modificar código sensible de auditoría. Hasta entonces, esta revisión manual permanece abierta y D12 no está cerrada.

## Límites de esta evidencia

- Docker/Compose real y escaneos de imágenes no se ejecutaron localmente: Docker no está disponible.
- El smoke fue local y sintético; no hubo staging, carga aprobada ni validación externa.
- El backup/restore fue en el mismo host; no es evidencia off-host.
- CI remoto, registry, provenance/attestations confiables, dominio TLS y aprobaciones operativas siguen pendientes.
- No se desplegó ni se modificó repositorio de backup remoto o datos reales.

## Verificación suplementaria — 2026-09-23

- Build de producción del frontend con Next.js 16.3.5: correcto; compilación, TypeScript, generación de páginas y optimización finalizaron sin error. Se generó `/`, `/_not-found` y el BFF dinámico `/api/[...path]`.
- Smoke de runtime con el servidor Next.js standalone recién construido, API Uvicorn y PostgreSQL sintético local: 20/20 solicitudes, concurrencia 2, 0 errores; corrida caliente p50 30 ms/p95 75 ms. La corrida fría inicial dio p95 769 ms, también sin errores. No existe presupuesto p95 aprobado y se omitió login/`me`/logout por falta de una cuenta sintética configurada. Los dos procesos se detuvieron después; los puertos de prueba quedaron libres.
- Smoke autenticado separado desde una base nueva: migración hasta `0010_costing`, bootstrap del administrador sintético, cambio de su contraseña inicial obligatoria y login/`me`/logout por el BFF, todo correcto. 20 solicitudes, concurrencia 2, 0 errores, p50 29 ms/p95 78 ms; resultado de autenticación `passed-login-me-logout`. Se borró la base creada por el test y se confirmó que no quedaron conexiones ni listeners. Un nombre candidato sin sufijo ya existía antes y se preservó intacto; para la prueba se usó un nombre único.
- Esta comprobación no es un build Docker ni reemplaza el build/scan de imágenes en CI.

## Verificación suplementaria - 2026-09-23 (suite backend y CI local)

- Suite backend completa contra un clúster PostgreSQL 16.14 nuevo y aislado: 201/201 pruebas; cobertura de ramas 80,30 % (mínimo 80 %). Incluye integraciones de autenticación, costing, migraciones, compras/idempotencia D6, ventas y tesorería. La base de aplicación migró desde cero hasta `0010_costing`; las URLs de aplicación y pruebas fueron distintas.
- Suite/configuración del job Windows parcial: 159 pasaron, 42 pruebas de integración se excluyeron sin aplicar cobertura parcial. Pruebas de configuración de workflow/despliegue: 8/8. El job PostgreSQL completo mantiene el umbral de cobertura.
- El chequeo local de CI encontró y corrigió el health check PostgreSQL, que esperaba una base creada solo en un paso posterior. El workflow local también habilita disparadores `weekend/**` y separa las URLs de aplicación/pruebas.
- Limpieza: las dos bases sintéticas se eliminaron; el servidor temporal se detuvo, el puerto se verificó cerrado y los artefactos generados se retiraron. No se tocaron bases ni procesos PostgreSQL preexistentes.
- GitHub Actions remoto: el workflow publicado en `weekend/autonomous` aún no incluye los cambios locales, no se activa en `weekend/**` y usa la misma URL para aplicación/pruebas. La consulta de ejecuciones remotas no encontró runs para esa rama. Los cambios siguen locales/no publicados; no constituyen evidencia CI remota.

## Refuerzo D11/D12 - 2026-09-23

- Revisión independiente del diff local: sin hallazgos críticos; dos importantes corregidos: el gate RC liga el digest de backup junto con backend/frontend, y los rechazos de autorización operativa ahora se registran durablemente sin cambiar el HTTP 403. Pruebas del gate cubren digest de backup ausente y discordante; pruebas unitarias del guard verifican actor, permiso, recurso, correlación y que los autorizados no generen denegación.
- Nueva prueba de integración PostgreSQL cubre el flujo HTTP autenticado que recibe 403 y consulta el evento persistido; ejecutada y aprobada en la suite PostgreSQL de abajo.
- Verificación inicial de la suite Windows parcial: 162 pasaron, 42 pruebas de integración excluidas intencionalmente sin cobertura parcial. Esa evidencia queda supersedida por la corrida completa de abajo.
- Frontend en el mismo árbol: 47/47 pasaron, statements 87,79 %, ramas 80,26 %. No se modificó el frontend al resolver los hallazgos de esta revisión.
- Una sugerencia menor sobre el límite de prefijo del BFF queda documentada como diferida. La revisión de matriz de permisos por rol, los builds/escaneos Docker, CI remoto, staging, backup off-host y aprobaciones operativas siguen abiertos.

## Suite backend completa fresca - 2026-09-23

- 206/206 pruebas aprobadas en Windows/Python 3.13.15 contra un clúster PostgreSQL 16.14 nuevo, enlazado solo a `127.0.0.1:55436`; cobertura total con ramas 80,86 % (umbral 80 %). Incluye la integración del 403 auditado y las pruebas del digest de backup presente, ausente y discordante.
- Base de aplicación distinta de la base de pruebas; migración limpia de `0001_baseline` a `0010_costing`. El clúster de validación fue detenido y su directorio temporal dedicado eliminado; puerto confirmado cerrado.
- Ruff check, Ruff format check (186 archivos) y Mypy (131 módulos fuente) aprobados. La suite de frontend 47/47 y sus gates constan en la validación local previa; no hubo cambios de frontend en esta corrección.
- Esto sigue siendo evidencia local: no equivale a CI remoto, build/escaneo de imágenes, staging ni aprobación de piloto/producción.
