# Cierre técnico de Entregas 11 y 12 - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrar las Entregas 11 y 12 con el producto de las Entregas 0-10 y dejar una versión candidata comprobable para que el usuario la despliegue después.

**Architecture:** Se conserva el monolito modular y Docker Compose actual. GitHub Actions construirá, probará, escaneará y empaquetará localmente en el job los tres contenedores y sus evidencias; el paquete de liberación tendrá procedencia verificable y el gate RC distinguirá readiness técnica de aprobación de piloto en infraestructura real.

**Tech Stack:** GitHub Actions, Docker/Compose, PostgreSQL 16, Python 3.13/FastAPI, Next.js/Node.js 22, Trivy, Restic, GitHub artifact attestations, GitHub CLI y Pytest.

**Spec:** `docs/superpowers/specs/2026-09-23-delivery-11-12-production-readiness-design.md`

## Global Constraints

- En esta fase no se despliega a producción, no se aprovisiona infraestructura productiva, no se cargan imágenes a un registro de producción y no se usan datos ni secretos reales.
- El gate de seguridad debe seguir bloqueando hallazgos HIGH/CRITICAL accionables; no se silencian resultados para obtener CI verde.
- Se mantiene la arquitectura monolítica y Docker Compose existente; migrar a Kubernetes o a servicios administrados queda fuera de alcance.
- Cualquier dato, credencial o valor operacional real queda a cargo del usuario y fuera del repositorio.
- El resultado `ready-for-user-deployment` significa paquete técnicamente preparado para que el usuario despliegue siguiendo el runbook; no significa producción ya certificada ni piloto aprobado.

## Review Focus

- Evidencia correspondiente a otro commit, tag, migración, digest o antigüedad: el gate debe rechazarla; cubrir en Task 4 y Task 5 con pruebas de discordancia y expiración.
- Archivo de evidencia o attestation manipulado, con origen incorrecto o fuera del bundle: rechazarlo; cubrir en Task 4 y Task 5 con pruebas de hash y workflow/repositorio no confiables.
- Hallazgo HIGH/CRITICAL sin versión corregida: no ocultarlo ni declarar readiness; cubrir en Task 1 con el reporte agregado y el gate remoto fail-closed.
- Restore que usa el mismo volumen/base que el origen o una clave incorrecta: no contaminar origen ni aceptar restauración; cubrir en Task 3 con base sintética separada y pruebas de rechazo.
- Fallo de migración o de readiness durante el arranque: no iniciar ni dar por sano el backend; cubrir en Task 2 con Compose de integración y comprobaciones de estado.

---

## File Structure

- `backend/Dockerfile`, `frontend/Dockerfile`, `deploy/backup/Dockerfile`: dependencias y capas de las imágenes runtime.
- `backend/tests/unit/test_deployment_config.py`: políticas estructurales para imágenes, workflow y Compose.
- `.github/workflows/ci.yml`: pruebas integradas, builds, escaneos y evidencias sintéticas.
- `deploy/compose/compose.ci.yml` (nuevo): overlay exclusivo de CI para usar imágenes construidas en el runner y secretos/datos sintéticos sin alterar Compose productivo.
- `scripts/verify_release_attestation.py` (nuevo): adaptador acotado para verificar el bundle de liberación con GitHub CLI y la identidad de repositorio/workflow fijada en el proyecto.
- `backend/tests/unit/test_release_attestation.py` (nuevo): pruebas sin red para argumentos, salida y fallos del verificador.
- `deploy/release_gate.py` y `backend/tests/unit/test_release_gate.py`: integración de autenticidad/procedencia, bundle y estado de readiness técnica.
- `scripts/release-gate.ps1`, `scripts/release-gate.sh`: mismos parámetros y comportamiento en Windows y Linux.
- `deploy/runbooks/{install,deploy,rollback,restore,incident}.md`: instrucciones alineadas con las pruebas y paquete resultante.
- `artifacts/quality/delivery-11/`: inventario de hallazgos, resultados de builds/smokes y restore sintético sin secretos.
- `artifacts/quality/delivery-12/README.md`: formato de paquete y límites del gate RC/piloto.
- `PROJECT_STATUS.md`, `PROJECT_CONTEXT.md`, `CHANGELOG.md`: continuidad coherente de las entregas y evidencias.

### Task 1: Identificar y remediar los hallazgos de las tres imágenes

**Files:**
- Modify: `backend/Dockerfile`
- Modify: `frontend/Dockerfile`
- Modify: `deploy/backup/Dockerfile`
- Modify: `backend/tests/unit/test_deployment_config.py`
- Modify: `artifacts/quality/delivery-11/image-security-remediation.md` (create)

**Interfaces:**
- Consumes: los tres informes SARIF del job `deployment-images` y la política `CRITICAL,HIGH` de `.github/workflows/ci.yml`.
- Produces: tres imágenes no-root construibles cuyo informe Trivy no contiene hallazgos HIGH/CRITICAL accionables; el inventario conserva paquete, versión instalada, identificador, severidad y versión corregida cuando exista.

- [ ] **Step 1: Registrar el baseline vigente**. Descarga el artifact `image-security-sarif` del run `35872211024` si sigue disponible; si expiró, usa el próximo run completo como baseline. Deduplica findings SARIF por imagen, identificador y paquete, y registra también los hallazgos sin versión corregida en el inventario.
- [ ] **Step 2: Escribir regresiones estructurales** en `test_deployment_config.py` para que cada Dockerfile conserve su runtime/versión funcional, usuario no-root, instalación reproducible del lockfile y ausencia de herramientas de build copiadas al runtime. Ejecutar `uv run pytest tests/unit/test_deployment_config.py -q` desde `backend/`; esperado: fallan solo las nuevas aserciones hasta que se aplique la remediación prevista.
- [ ] **Step 3: Corregir causas, no el reporte**. Actualiza bases o paquetes únicamente con versiones soportadas y compatibles; elimina paquetes innecesarios del runtime y reconstruye Restic si la evidencia muestra que su runtime Go empaquetado es la causa. Mantén las versiones necesarias para Python 3.13, Node 22 y PostgreSQL 16; no uses `ignore-unfixed`, allowlists ni exclusiones Trivy para simular cero hallazgos.
- [ ] **Step 4: Ejecutar regresiones y publicar evidencia técnica**. Ejecuta `uv run pytest tests/unit/test_deployment_config.py -q` y `uv run ruff check tests/unit/test_deployment_config.py` desde `backend/`; ambos deben pasar. Guarda el inventario final con versiones y referencias a SARIF sin copiar secretos.
- [ ] **Step 5: Reconstruir y escanear las tres imágenes en CI**. El job existente debe terminar backend, frontend y backup, preservar los tres SARIF y fallar si un scan detecta HIGH/CRITICAL o error. Esperado: tres builds exitosos y cero resultados bloqueantes en cada imagen; de lo contrario, Task 1 no está completo.
- [ ] **Step 6: Commit de Task 1** con mensaje `fix: remediate runtime image vulnerabilities`.

### Task 2: Probar arranque e integración de la aplicación con Compose

**Files:**
- Create: `deploy/compose/compose.ci.yml`
- Modify: `.github/workflows/ci.yml`
- Modify: `backend/tests/unit/test_deployment_config.py`
- Modify: `artifacts/quality/delivery-11/README.md` (create)

**Interfaces:**
- Consumes: imágenes `backend:ci`, `frontend:ci`, `backup:ci`; base PostgreSQL sintética; archivos de secretos efímeros creados durante el job.
- Produces: job Linux de Compose que aplica migraciones hasta `0010_costing`, espera readiness, ejecuta smoke autenticado y comprueba que DB/backend no publiquen puertos al host.

- [ ] **Step 1: Escribir primero la regresión del job** en `test_deployment_config.py`: comprobar que `ci.yml` contiene un job de runtime Compose que construye/usa el overlay CI, espera health checks, comprueba la migración y realiza login/`me`/logout sintéticos. Ejecutar `uv run pytest tests/unit/test_deployment_config.py -q` desde `backend/`; esperado: FAIL porque hoy solo se renderiza Compose.
- [ ] **Step 2: Añadir overlay exclusivamente CI** en `compose.ci.yml`, con imágenes locales `:ci`, puertos internos y credenciales sintéticas; no editar valores productivos ni `.env.production`.
- [ ] **Step 3: Implementar el job de smoke** en `ci.yml`: crear secretos aleatorios en el runner, iniciar PostgreSQL y los servicios con el overlay, esperar health, comprobar `alembic current` igual a `0010_costing`, ejecutar flujo bootstrap/cambio inicial de contraseña/login/`me`/logout con una cuenta sintética, y detener el stack con limpieza aun ante fallo.
- [ ] **Step 4: Ejecutar pruebas y validar el comportamiento**. Ejecuta `uv run pytest tests/unit/test_deployment_config.py -q` y `uv run ruff check tests/unit/test_deployment_config.py` desde `backend/`; después espera el job CI de Compose. Esperado: prueba unitaria verde y CI muestra migración/head, smoke autenticado y shutdown exitosos; servicios reales no se crean.
- [ ] **Step 5: Commit de Task 2** con mensaje `test: exercise production compose with synthetic data`.

### Task 3: Automatizar el roundtrip cifrado de backup y restore sintético

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `backend/tests/unit/test_deployment_config.py`
- Modify: `deploy/backup/README.md` (create solo si no existe; si existe, modificar ese mismo archivo)
- Modify: `artifacts/quality/delivery-11/README.md`

**Interfaces:**
- Consumes: servicio `backup` del perfil `operations`, Restic y la API existente `deploy.backup.backup` / `deploy.backup.restore`.
- Produces: job CI que crea un snapshot cifrado de una base de prueba, restaura en una base aislada diferente y ejecuta las 9 conciliaciones existentes; conserva reporte sin contraseñas ni datos personales.

- [ ] **Step 1: Añadir test de regresión del workflow** en `test_deployment_config.py` para exigir dos bases distintas, repositorio Restic temporal/cifrado, restore a destino aislado, conciliaciones y cleanup con `if: always()`. Ejecuta `uv run pytest tests/unit/test_deployment_config.py -q` desde `backend/`; esperado: FAIL porque hoy no existe ese job.
- [ ] **Step 2: Añadir job de backup/restore** en `ci.yml` usando PostgreSQL y un directorio/volumen temporal dentro del runner; genera la clave Restic aleatoria solo en el runner, inicializa schema y datos sintéticos, crea snapshot, restaura a base con nombre único, ejecuta reconciliaciones y rechaza clave incorrecta/corrupción en pruebas aisladas.
- [ ] **Step 3: Asegurar limpieza no destructiva**: borrar solo bases con prefijo sintético y recursos creados por ese job; conservar el servicio PostgreSQL ajeno al job fuera del workflow. Añadir una comprobación de que la URL de origen y destino no coinciden.
- [ ] **Step 4: Ejecutar regresiones**. Ejecuta `uv run pytest tests/unit/test_deployment_config.py -q` y `uv run ruff check tests/unit/test_deployment_config.py` desde `backend/`; luego exige CI con snapshot, restore y 9/9 conciliaciones aprobadas. Documenta que es una prueba aislada de CI, no una restauración en cuenta externa productiva.
- [ ] **Step 5: Commit de Task 3** con mensaje `test: verify encrypted backup restore in CI`.

### Task 4: Producir un paquete con SBOM y procedencia autenticada sin publicar a producción

**Files:**
- Modify: `.github/workflows/ci.yml`
- Create: `scripts/verify_release_attestation.py`
- Create: `backend/tests/unit/test_release_attestation.py`
- Modify: `artifacts/quality/delivery-12/README.md`

**Interfaces:**
- Consumes: imágenes CI escaneadas, digests, reportes de pruebas/seguridad, SBOMs y SHA/ref del workflow.
- Produces: `verify_release_attestation(bundle_path: Path, expected_commit: str, expected_source_ref: str) -> dict[str, Any]`; bundle versionado como artifact de Actions con archivos de imagen, manifest, SBOM y reportes; atestación de GitHub sobre el bundle que exige repo `Rubio120/AVICOLA_PRO`, workflow `.github/workflows/ci.yml`, evento/ref/commit permitidos y digest exacto del bundle.

- [ ] **Step 1: Test-first del verificador**. Añade pruebas que simulen `gh attestation verify` con éxito y que comprueben rechazo de ejecutable ausente, salida no JSON, repositorio distinto, workflow distinto, commit/ref distintos y digest del subject distinto. Ejecuta `uv run pytest tests/unit/test_release_attestation.py -q` desde `backend/`; esperado: FAIL porque el módulo aún no existe.
- [ ] **Step 2: Implementar el adaptador seguro** con lista de argumentos, sin shell y timeout; forzar identidad de repositorio, workflow y source ref/commit en la verificación criptográfica; rechazar salida no-cero, JSON vacío, subject SHA-256 distinto al archivo y certificado cuya SAN/workflow no coincidan. No confiar solo en campos mutables del predicate.

```python
completed = subprocess.run(
    [
        gh_executable,
        "attestation",
        "verify",
        str(bundle_path),
        "--repo",
        "Rubio120/AVICOLA_PRO",
        "--signer-workflow",
        "Rubio120/AVICOLA_PRO/.github/workflows/ci.yml",
        "--source-digest",
        expected_commit,
        "--source-ref",
        expected_source_ref,
        "--format",
        "json",
    ],
    capture_output=True,
    text=True,
    check=False,
    timeout=30,
)
if completed.returncode != 0:
    raise ReleaseGateError("GitHub artifact attestation verification failed")
verified_attestations = json.loads(completed.stdout)
```
- [ ] **Step 3: Preservar los archivos de imagen entre jobs**. En `deployment-images`, ejecuta `docker save --output avicola-pro-backend.tar avicola-pro-backend:ci`, `docker save --output avicola-pro-frontend.tar avicola-pro-frontend:ci` y `docker save --output avicola-pro-backup.tar avicola-pro-backup:ci`; súbelos junto con los SARIF usando `actions/upload-artifact@v4`. El job dependiente descarga esos archivos por nombre, evitando rebuilds que separen el scan del artefacto entregado.
- [ ] **Step 4: Empaquetar solo si todos los gates previos pasan**: genera SBOM CycloneDX para cada image archive con Trivy, calcula SHA-256 de los archivos exportados, construye un manifest que liga reportes, image IDs, archive hashes, commit, ref, workflow y head de Alembic, y crea `avicola-pro-release-bundle.tar`. Genera atestación `actions/attest@v4` sobre el bundle con `subject-path`; súbelo como artifact de Actions con retención explícita, nunca a un registry.
- [ ] **Step 5: Verificar atestación en el runner** con GitHub CLI contra el repositorio y workflow exactos; conceder `id-token: write`, `attestations: write`, `contents: read` al job que atestigua y `attestations: read`, `contents: read` al que verifica. Pasar `GH_TOKEN: ${{ github.token }}` al paso CLI, mantener permisos restringidos al job y no usar tokens personales ni secretos productivos.
- [ ] **Step 6: Ejecutar pruebas y el job**. Ejecuta `uv run pytest tests/unit/test_release_attestation.py -q` y `uv run ruff check tests/unit/test_release_attestation.py` desde `backend/`; CI debe producir/verificar un bundle del mismo commit y rechazar un bundle de prueba modificado.
- [ ] **Step 7: Commit de Task 4** con mensaje `feat: attest reproducible release evidence bundle`.

### Task 5: Vincular el gate RC a atestación, bundle y estado deployable

**Files:**
- Modify: `deploy/release_gate.py`
- Modify: `backend/tests/unit/test_release_gate.py`
- Modify: `scripts/release-gate.ps1`
- Modify: `scripts/release-gate.sh`
- Modify: `artifacts/quality/delivery-12/README.md`

**Interfaces:**
- Consumes: `verify_release_attestation(bundle_path, expected_commit, expected_source_ref) -> dict[str, Any]` de Task 4, configuración esperada del llamador y evidencias del bundle.
- Produces: informe RC con `technical_status: ready_for_user_deployment` solo si atestación, subject, SHA, tag, Alembic head, edad, pruebas, scans, SBOM, hashes de los tres archivos de imagen e image IDs concuerdan; `pilot_status` permanece `blocked` hasta cumplir aprobaciones/restore externo. Los registry manifest digests solo se agregan cuando el usuario publique las imágenes más adelante; no se inventan ni se presentan como ya existentes.

- [ ] **Step 1: Escribir casos RED** en `test_release_gate.py`: aceptar informe técnico cuando todos los datos verificados coinciden; rechazar commit/ref/workflow, digest/SBOM/report, scan fallido, HIGH/CRITICAL, antigüedad, tag y Alembic discrepantes; mantener piloto bloqueado por ausencia de evidencia/aprobación externa. Ejecuta `uv run pytest tests/unit/test_release_gate.py -q` desde `backend/`; esperado: fallan los nuevos casos ante el estado actual `manifest_validated`.
- [ ] **Step 2: Integrar autenticidad antes del contenido**: hacer que el CLI verifique primero la atestación y extraiga el bundle de forma segura; luego recalcular hashes de cada archivo y validar evidencia. Rechazar rutas fuera del bundle y no sobrescribir informes existentes. El informe separa `image_archive_sha256`/`docker_image_id` de cualquier `registry_manifest_digest`.
- [ ] **Step 3: Actualizar los wrappers PowerShell/Linux** para requerir bundle, commit esperado, ref esperada, tag, migration head, antigüedad y ruta nueva del reporte; mantener el mismo contrato entre plataformas.
- [ ] **Step 4: Ejecutar suites**. Ejecuta `uv run pytest tests/unit/test_release_gate.py tests/unit/test_release_attestation.py -q`, `uv run ruff check src tests`, `uv run ruff format --check src tests` y `uv run mypy src tests` desde `backend/`; todos deben pasar. Añade pruebas de CLI que demuestren que una atestación fallida no escribe un reporte `ready`.
- [ ] **Step 5: Commit de Task 5** con mensaje `feat: verify provenance in release readiness gate`.

### Task 6: Cerrar integración documental y verificar el producto completo

**Files:**
- Modify: `deploy/runbooks/install.md`
- Modify: `deploy/runbooks/deploy.md`
- Modify: `deploy/runbooks/rollback.md`
- Modify: `deploy/runbooks/restore.md`
- Modify: `deploy/runbooks/incident.md`
- Modify: `artifacts/quality/delivery-11/README.md`
- Modify: `artifacts/quality/delivery-12/README.md`
- Modify: `PROJECT_STATUS.md`
- Modify: `PROJECT_CONTEXT.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: bundle y gate verificados de Tasks 1-5, head Alembic `0010_costing` y plan oficial de entregas 0-12.
- Produces: runbooks y estado global que distinguen D11/D12 completadas técnicamente, release listo para que el usuario despliegue, y los pasos de piloto que requieren datos/servicios/aprobación reales.

- [ ] **Step 1: Actualizar runbooks** con los comandos que realmente pasaron en CI; separar `build/test`, descarga/verificación del bundle, publicación voluntaria al registry y despliegue; no incluir valores secretos/operacionales inventados ni instrucciones que automaticen producción.
- [ ] **Step 2: Actualizar continuidad** en `PROJECT_STATUS.md`, `PROJECT_CONTEXT.md` y `CHANGELOG.md` con commit, run IDs, conteos y links a artifacts; dejar explícitos los límites de prueba sintética y los gates externos que siguen pendientes.
- [ ] **Step 3: Ejecutar verificación integrada**: en `backend/`, `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src tests`, `uv run pip-audit`; en `frontend/`, `npm ci`, `npm run lint`, `npm run typecheck`, `npm test`, `npm run build` y `npm audit --audit-level=high`. Luego esperar CI completo con PostgreSQL, Windows, seguridad, tres imágenes, Compose, smoke, backup/restore y bundle.
- [ ] **Step 4: Confirmar limpieza y estado final** con `git diff --check`, `git status -sb`, `git log -1 --oneline`; no hacer merge a la rama principal ni desplegar. Guardar los commits en la rama autorizada y actualizar el estado solo con los resultados reales de CI.
- [ ] **Step 5: Commit de Task 6** con mensaje `docs: close delivery 11 and 12 readiness evidence`.

## Fuentes oficiales para ejecutar el plan

- [GitHub: generar atestaciones para artifacts](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations)
- [GitHub CLI: verificar identidad, workflow y subject de una atestación](https://cli.github.com/manual/gh_attestation_verify)
- [Trivy: escanear una imagen exportada como tar](https://github.com/aquasecurity/trivy/blob/main/docs/guide/target/container_image.md#tar-files)

## Handoff

El usuario ya aprobó completar e integrar D11 y D12 en `weekend/autonomous`. La implementación será nativa en esta sesión porque no hay herramienta de despacho de subagentes disponible; antes de ejecutar, el usuario revisará este plan y confirmará que refleja el trabajo pedido. No se selecciona ni se usa un agente externo.
