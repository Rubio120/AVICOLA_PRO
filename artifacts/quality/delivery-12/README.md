# Entrega 12 — paquete de decisión RC/piloto

Estado al 2026-09-22: gate RC implementado; todavía no hay un release candidate certificado ni evidencia real de staging/off-host. Este directorio describe cómo producir el informe; no contiene una aprobación ficticia.

## Gate

`scripts/release-gate.ps1` (Windows) y `scripts/release-gate.sh` (Linux/macOS) llaman al validador común `deploy/release_gate.py`. Se requiere un manifiesto JSON de evidencia creado para el commit exacto:

```powershell
./scripts/release-gate.ps1 -Evidence C:/ruta-segura/evidence.json -Mode rc -ExpectedCommit <40-hex-del-commit> -ExpectedTag <tag-rc> -ExpectedMigrationHead <head-aprobado> -MaxEvidenceAgeHours <limite-aprobado> -Report artifacts/quality/delivery-12/rc-report.json
```

En modo `rc`, exige el commit/tag y head Alembic esperados; además resuelve el tag local en Git y exige que apunte al mismo SHA. Cada reporte adjunto debe estar dentro del directorio del manifiesto y su SHA-256 se calcula contra los bytes reales del archivo. El build/digests, cero hallazgos críticos/altos y smoke deben declararse ligados al mismo commit, con fechas UTC dentro del máximo de antigüedad proporcionado por el operador. El resultado actual es deliberadamente `technical_status: manifest_validated`, no "técnicamente listo": el gate aún no valida attestations/provenance autenticadas de CI ni comprueba la existencia de imágenes en un registry.

El modo `pilot` verifica además restore, RPO/RTO y responsables, pero por ahora siempre falla cerrado porque no existe una identidad/clave de confianza aprobada para autenticar attestations CI, approvals ni la evidencia de que el restore fue off-host. Los estados y nombres dentro de un manifiesto no bastan para aprobar el piloto. `-Report` es obligatorio y debe señalar un nombre nuevo: el gate no sobrescribe un informe anterior ni permite una ejecución exitosa sin guardar el resultado.

## Manifiesto requerido

Esquema orientativo (valores ilustrativos, no evidencia):

```json
{
  "commit": "<40 caracteres hexadecimales>",
  "release_tag": "<tag exacto>",
  "expected_migration_head": "<head aprobado>",
  "alembic_head": "<head observado>",
  "scans": {
    "dependency": {"status": "passed", "report_file": "pip-audit.json", "report_sha256": "<hash de bytes>", "completed_at": "<ISO-8601 UTC>"},
    "secrets": {"status": "passed", "report_file": "trivy-source.sarif", "report_sha256": "<hash de bytes>", "completed_at": "<ISO-8601 UTC>"},
    "image": {"status": "passed", "report_file": "trivy-images.sarif", "report_sha256": "<hash de bytes>", "completed_at": "<ISO-8601 UTC>"}
  },
  "findings": {"critical": 0, "high": 0},
  "images": {"backend": "sha256:<64 hex>", "frontend": "sha256:<64 hex>", "backup": "sha256:<64 hex>"},
  "build": {
    "status": "passed",
    "commit": "<mismo commit>",
    "built_at": "<ISO-8601 UTC>",
    "report_file": "build-provenance.json",
    "report_sha256": "<hash de bytes>",
    "image_digests": {"backend": "sha256:<64 hex>", "frontend": "sha256:<64 hex>", "backup": "sha256:<64 hex>"}
  },
  "smoke": {
    "status": "passed",
    "tested_commit": "<mismo commit>",
    "completed_at": "<ISO-8601 UTC>",
    "report_file": "smoke.json",
    "report_sha256": "<64 hex>"
  },
  "restore": {
    "status": "passed",
    "snapshot_id": "<64 hex>",
    "sha256": "<64 hex>",
    "reconciliation": "passed",
    "report_file": "restore.json",
    "completed_at": "<ISO-8601 UTC>"
  },
  "operations": {
    "rpo_approved": true,
    "rpo_minutes": 60,
    "rto_approved": true,
    "rto_minutes": 240,
    "owner": "<responsable aprobado>",
    "approver": "<aprobador aprobado>"
  }
}
```

Los minutos anteriores son solo ejemplos de formato, no valores aceptados para la operación. No guardar URLs/credenciales, datos de clientes/empleados ni secretos en el manifiesto. Las rutas de archivo son relativas al directorio del manifiesto; se rechazan las rutas que escapen de ese bundle y el gate vuelve a calcular cada hash. Esto prueba integridad local del bundle, no quién lo produjo. `-MaxEvidenceAgeHours` debe ser el límite aprobado para esa revisión; se contrasta contra las fechas UTC y no tiene un valor por defecto.

## Evidencia aún pendiente

- Ejecución de CI en el remoto: builds, render Compose, dependency/source/image scans y pruebas completas.
- Restore cifrado extremo a extremo, incluyendo clave errónea y corrupción, primero en laboratorio desechable.
- Staging con dominio/TLS y destino de backup off-host aprobados; migración desde versión soportada, smoke/carga y ejercicios de deploy/rollback/incidente/restore.
- Attestations verificables para ligar tests/scans/build a workflow, commit, tag y digest; verificación del tag firmado y existencia de cada digest en un registry.
- Revisión manual de RBAC/auditoría y revisión independiente del diff.
- RPO, RTO, retención, workload piloto, fecha, owner y aprobador definidos por las personas responsables.
- Restore drill off-host con hash, snapshot, conciliaciones, tiempos observados y aprobaciones preservados sin secretos.

El tag debe existir localmente y resolver al commit esperado. No desplegar ni activar piloto basándose en `technical_status: manifest_validated`; este informe no autentica origen ni equivale a `technical_status: ready`.
