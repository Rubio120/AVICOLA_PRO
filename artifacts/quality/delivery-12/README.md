# Entrega 12 — gate RC y paquete verificable

La Entrega 12 prepara un candidato para que el responsable lo pruebe y decida si lo despliega. No publica imágenes, no despliega y no aprueba por sí sola un piloto en producción. El cierre técnico depende de una ejecución completa y verde de CI para el mismo commit; no se considera cerrada por tener solo el código del workflow.

## Paquete firmado por CI

El workflow `quality` genera `avicola-pro-release-bundle` únicamente cuando pasan Windows, PostgreSQL, auditorías de dependencias y código, construcción/escaneo de las tres imágenes, Compose, smoke autenticado y el restore sintético. Incluye los archivos `docker save`, sus SHA-256 e IDs locales, SBOM CycloneDX y reportes de esa ejecución. GitHub atestigua el `.tar`; otro job verifica el repositorio, workflow, commit/ref, digest exacto y rechaza una copia modificada. Las imágenes no se publican a un registry.

El verificador local requiere GitHub CLI (`gh`) autenticado con permiso para leer attestations y un tag Git local que apunte exactamente al commit esperado. Primero verifica la atestación criptográfica y su timestamp de transparencia; luego inspecciona el tar sin seguir enlaces ni permitir rutas fuera del paquete, vuelve a calcular hashes, comprueba SBOM/escaneos, migración y smoke, y por último verifica el tag. No sobrescribe el informe de salida.

## Ejecutar el gate RC en Windows

1. Descarga desde la ejecución aprobada de GitHub Actions el artifact `avicola-pro-release-bundle` y guárdalo en una carpeta de trabajo confiable.
2. Comprueba que `gh auth status` muestre la cuenta autorizada para leer attestations. No uses tokens personales pegados en comandos ni guardes secretos en el repo.
3. Confirma el SHA completo y la ref exacta del mismo run. Crea/obtén localmente el tag de revisión que hayas aprobado, apuntando a ese SHA. El gate no inventa ni publica tags.
4. Sustituye los valores entre `<...>` por los valores revisados para ese RC y usa una ruta de informe nueva:

```powershell
./scripts/release-gate.ps1 `
  -Bundle C:/ruta-segura/avicola-pro-release-bundle.tar `
  -Mode rc `
  -ExpectedCommit <40-hex-del-run> `
  -ExpectedSourceRef refs/heads/<rama-del-run> `
  -ExpectedTag <tag-local-aprobado> `
  -ExpectedMigrationHead 0014_egg_classification_reversal `
  -MaxEvidenceAgeHours <limite-aprobado> `
  -Report artifacts/quality/delivery-12/rc-report.json
```

El resultado `technical_status: ready_for_user_deployment` significa que la evidencia CI autenticada corresponde al commit/ref indicados, que la etiqueta local, Alembic `0014_egg_classification_reversal`, archivos de imagen/SBOM/reportes y antigüedad cumplen el gate. Es una autorización técnica para que el usuario haga pruebas y gestione el despliegue; no prueba el entorno real ni reemplaza su decisión operativa. El informe separa los SHA-256 de los archivos de imagen y los Docker image IDs. No contiene `registry_manifest_digest`, porque todavía no hay publicación en registry.

El modo `pilot` permanece bloqueado: este paquete solo acredita un restore sintético local de CI. Aún hacen falta destino de backup off-host, restauración en staging real, tiempos observados, RPO/RTO y retención aprobados, owner y aprobador nombrados, además de la validación operativa correspondiente. No se deben introducir datos o aprobaciones ficticios para desbloquearlo.

## Verificación local vigente

En PostgreSQL 16 de test: 246/246 pruebas backend pasaron con 80,86 % de cobertura. Ruff check/format, Mypy, `pip-audit` sin vulnerabilidades conocidas, ESLint, TypeScript, build Next.js y `npm audit --audit-level=high` pasaron. Vitest no pudo arrancar desde este Windows sandbox porque esbuild no pudo leer `../..` fuera del workspace; la suite frontend previa 47/47 es evidencia histórica, no sustituye un run actual. El último workflow remoto disponible `35890371500` sigue fallido en la construcción de Restic; por eso no existe aún artifact RC verificado. Exigir un workflow verde para el SHA final antes de usar el gate.

Si la attestation, firma, digest, fecha, tag, head Alembic, gate CI o cualquier hash no coincide, el comando falla y no crea un informe de éxito. Para Linux/macOS el wrapper `scripts/release-gate.sh` acepta los mismos argumentos del validador (`--bundle`, `--mode`, `--expected-commit`, `--expected-source-ref`, `--expected-tag`, `--expected-migration-head`, `--max-evidence-age-hours`, `--report`).
