from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENTRYPOINT = PROJECT_ROOT / "deploy" / "entrypoints" / "backend.py"
COMPOSE_FILE = PROJECT_ROOT / "deploy" / "compose" / "compose.production.yml"
BACKUP_COMPOSE_FILE = PROJECT_ROOT / "deploy" / "backup" / "compose.backup.yml"
CI_WORKFLOW_FILE = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"


def _entrypoint_environment(tmp_path: Path) -> tuple[dict[str, str], str, str]:
    database_url = "postgresql+psycopg://app:test-only@db:5432/avicola_pro"
    session_key = "synthetic-session-key"
    database_file = tmp_path / "database-url"
    session_file = tmp_path / "session-hmac-key"
    database_file.write_text(database_url, encoding="utf-8")
    session_file.write_text(session_key, encoding="utf-8")

    environment = os.environ.copy()
    for name in (
        "AVICOLA_DATABASE_URL",
        "AVICOLA_SESSION_HMAC_KEY",
        "AVICOLA_DATABASE_URL_FILE",
        "AVICOLA_SESSION_HMAC_KEY_FILE",
    ):
        environment.pop(name, None)
    environment["AVICOLA_DATABASE_URL_FILE"] = str(database_file)
    environment["AVICOLA_SESSION_HMAC_KEY_FILE"] = str(session_file)
    return environment, database_url, session_key


def test_container_entrypoint_loads_mounted_secrets_without_leaking_them(tmp_path: Path) -> None:
    environment, database_url, session_key = _entrypoint_environment(tmp_path)
    child = (
        "import os; "
        "print('|'.join((os.environ['AVICOLA_DATABASE_URL'], os.environ['AVICOLA_SESSION_HMAC_KEY'], "
        "str('AVICOLA_DATABASE_URL_FILE' in os.environ), str('AVICOLA_SESSION_HMAC_KEY_FILE' in os.environ))))"
    )

    result = subprocess.run(
        [sys.executable, str(ENTRYPOINT), sys.executable, "-c", child],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == f"{database_url}|{session_key}|False|False"
    assert database_url not in result.stderr
    assert session_key not in result.stderr


def test_container_entrypoint_fails_closed_when_a_secret_file_is_missing(tmp_path: Path) -> None:
    environment, database_url, session_key = _entrypoint_environment(tmp_path)
    Path(environment["AVICOLA_SESSION_HMAC_KEY_FILE"]).unlink()

    result = subprocess.run(
        [sys.executable, str(ENTRYPOINT), sys.executable, "-c", "print('should not run')"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert result.returncode != 0
    assert "should not run" not in result.stdout
    assert database_url not in result.stderr
    assert session_key not in result.stderr


def test_production_compose_exposes_only_caddy_and_keeps_database_private() -> None:
    compose = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    services = compose["services"]

    published_ports = {service_name for service_name, service in services.items() if service.get("ports")}

    assert published_ports == {"proxy"}
    assert services["db"]["networks"] == ["data"]
    assert compose["networks"]["data"]["internal"] is True
    assert services["frontend"]["environment"]["BACKEND_INTERNAL_URL"] == "http://backend:8000"
    assert services["backend"]["environment"]["AVICOLA_ENVIRONMENT"] == "production"
    assert services["backend"]["environment"]["AVICOLA_LOG_FORMAT"] == "json"
    assert services["backend"]["environment"]["AVICOLA_SESSION_COOKIE_SECURE"] == "true"
    assert "${APP_DOMAIN}" in services["backend"]["environment"]["AVICOLA_CORS_ORIGINS"]
    assert "application" in services["frontend"]["networks"]
    assert "application" in services["backend"]["networks"]
    assert services["migrate"]["depends_on"]["db"]["condition"] == "service_healthy"
    assert services["backend"]["depends_on"]["migrate"]["condition"] == "service_completed_successfully"


def test_backup_service_is_the_only_database_consumer_with_controlled_egress() -> None:
    compose = yaml.safe_load(BACKUP_COMPOSE_FILE.read_text(encoding="utf-8"))
    backup = compose["services"]["backup"]

    assert set(backup["networks"]) == {"data", "backup-egress"}
    assert backup["group_add"] == ["10001"]
    assert backup["environment"]["RESTIC_REPOSITORY_FILE"] == "/run/secrets/restic_repository"
    assert backup["environment"]["RESTIC_PASSWORD_FILE"] == "/run/secrets/restic_" + "password"
    assert backup["restart"] == "no"
    assert "volumes" not in backup


def test_runbooks_keep_restore_target_permissions_and_destructive_actions_safe() -> None:
    runbooks = PROJECT_ROOT / "deploy" / "runbooks"
    restore = (runbooks / "restore.md").read_text(encoding="utf-8")
    rollback = (runbooks / "rollback.md").read_text(encoding="utf-8")
    incident = (runbooks / "incident.md").read_text(encoding="utf-8")
    install = (runbooks / "install.md").read_text(encoding="utf-8")

    assert "avicola_restore_" in restore
    assert "10002" in restore
    assert "--clean" in restore and "--create" in restore
    assert "off-host" in restore
    assert "alembic downgrade" in rollback
    assert "base aislada" in rollback
    assert "prune" in incident.lower() and "no ejecutar" in incident.lower()
    assert "No ejecutarlo en producción sin aprobación" in install


def test_deployment_compose_uses_immutable_image_digest_references() -> None:
    production = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    backup_compose = yaml.safe_load(BACKUP_COMPOSE_FILE.read_text(encoding="utf-8"))
    production_services = production["services"]

    assert production_services["migrate"]["image"] == "${BACKEND_IMAGE_REF:?Set immutable backend image reference}"
    assert production_services["backend"]["image"] == "${BACKEND_IMAGE_REF:?Set immutable backend image reference}"
    assert production_services["frontend"]["image"] == "${FRONTEND_IMAGE_REF:?Set immutable frontend image reference}"
    assert backup_compose["services"]["backup"]["image"] == "${BACKUP_IMAGE_REF:?Set immutable backup image reference}"
    assert all("build" not in production_services[name] for name in ("migrate", "backend", "frontend"))
    assert "build" not in backup_compose["services"]["backup"]
    environment_example = (COMPOSE_FILE.parent / ".env.production.example").read_text(encoding="utf-8")
    for image_name in ("BACKEND_IMAGE_REF", "FRONTEND_IMAGE_REF", "BACKUP_IMAGE_REF"):
        assert image_name in environment_example


def test_postgres_ci_healthcheck_targets_the_database_created_at_container_start() -> None:
    workflow = yaml.safe_load(CI_WORKFLOW_FILE.read_text(encoding="utf-8"))
    postgres = workflow["jobs"]["postgresql-integration"]["services"]["postgres"]
    bootstrap_database = postgres["env"]["POSTGRES_DB"]
    health_options = shlex.split(postgres["options"])
    health_command = health_options[health_options.index("--health-cmd") + 1]
    health_arguments = shlex.split(health_command)
    health_database = health_arguments[health_arguments.index("-d") + 1]

    assert health_database == bootstrap_database


def test_postgres_ci_migration_has_a_synthetic_session_hmac_key() -> None:
    workflow = yaml.safe_load(CI_WORKFLOW_FILE.read_text(encoding="utf-8"))
    postgres_backend = next(
        step
        for step in workflow["jobs"]["postgresql-integration"]["steps"]
        if step.get("name") == "Migrate and test with PostgreSQL 16"
    )

    assert len(postgres_backend["env"]["AVICOLA_SESSION_HMAC_KEY"]) >= 32


def test_compose_ci_enables_the_backup_operations_profile() -> None:
    workflow = yaml.safe_load(CI_WORKFLOW_FILE.read_text(encoding="utf-8"))
    compose_step = next(
        step
        for step in workflow["jobs"]["deployment-compose"]["steps"]
        if step.get("name") == "Render Compose with synthetic secrets and enforce private topology"
    )

    assert "--profile operations" in compose_step["run"]
    assert "rendered top-level keys" in compose_step["run"]


def test_compose_runtime_smoke_migrates_and_authenticates_with_synthetic_data() -> None:
    workflow = yaml.safe_load(CI_WORKFLOW_FILE.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]
    runtime_job = jobs["deployment-images"]
    smoke = next(step for step in runtime_job["steps"] if step.get("name") == "Run isolated Compose application smoke")
    cleanup = next(step for step in runtime_job["steps"] if step.get("name") == "Clean isolated Compose application")
    run_script = smoke["run"]
    compose_overlay = PROJECT_ROOT / "deploy" / "compose" / "compose.ci.yml"
    assert compose_overlay.is_file()
    overlay = yaml.safe_load(compose_overlay.read_text(encoding="utf-8"))

    assert set(overlay["services"]) >= {"db", "migrate", "backend", "frontend"}
    assert all("ports" not in overlay["services"][name] for name in ("db", "backend"))
    assert "restore-db" in overlay["services"]
    assert "ports" not in overlay["services"]["restore-db"]
    assert "docker compose" in run_script
    assert "compose.ci.yml" in run_script
    assert 'assert not services["db"].get("ports")' in run_script
    assert 'assert not services["backend"].get("ports")' in run_script
    assert "/health/ready" in run_script
    assert "0013_sales_channel" in run_script
    assert "python /app/entrypoints/backend.py alembic current" in run_script
    assert "python /app/entrypoints/backend.py avicola-pro bootstrap-admin" in run_script
    assert "bootstrap-admin" in run_script
    assert "/api/v1/auth/change-password" in run_script
    assert "/api/v1/auth/login" in run_script
    assert "/api/v1/auth/me" in run_script
    assert "/api/v1/auth/logout" in run_script
    assert cleanup["if"] == "always()"
    assert "down --volumes --remove-orphans" in cleanup["run"]


def test_ci_runs_an_encrypted_backup_restore_roundtrip_to_an_isolated_database() -> None:
    workflow = yaml.safe_load(CI_WORKFLOW_FILE.read_text(encoding="utf-8"))
    job = workflow["jobs"]["deployment-images"]
    steps = job["steps"]
    smoke = next(step for step in steps if step.get("name") == "Run encrypted backup and isolated restore")
    cleanup = next(step for step in steps if step.get("name") == "Clean synthetic backup resources")
    script = smoke["run"]

    assert "RESTIC_PASSWORD" in script
    assert ".ci-restic" in script
    assert "initialize_repository" in script
    assert "backup" in script and "restore" in script
    assert "RESTORE_TARGET_DATABASE_NAME" in script
    assert "python /app/entrypoints/backend.py avicola-pro bootstrap-admin" in script
    assert 'test "$source_database_url" != "$restore_target_database_url"' in script
    assert "nine checks" in script.lower() or "9 checks" in script
    assert "grep -F 'Restore reconciliation passed (9 checks)'" in script
    assert "wrong" in script.lower()
    assert "corrupt" in script.lower()
    assert cleanup["if"] == "always()"
    assert "down --volumes --remove-orphans" in cleanup["run"]
    assert "chmod" in cleanup["run"]
    assert any(step.get("uses", "").startswith("actions/upload-artifact@") for step in steps)


def test_release_bundle_preserves_scanned_images_sboms_and_verifiable_attestation() -> None:
    workflow = yaml.safe_load(CI_WORKFLOW_FILE.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]
    image_job = jobs["deployment-images"]
    export = next(step for step in image_job["steps"] if step.get("name") == "Export scanned image archives")
    image_artifact = next(step for step in image_job["steps"] if step.get("name") == "Preserve runtime image archives")
    packaging = jobs["release-bundle"]
    package_steps = packaging["steps"]
    attestation = next(step for step in package_steps if step.get("uses", "").startswith("actions/attest@"))
    verification = jobs["release-bundle-verify"]
    verify_step = next(
        step
        for step in verification["steps"]
        if step.get("name") == "Verify exact bundle provenance and reject tampering"
    )

    assert all(f"avicola-pro-{name}.tar" in export["run"] for name in ("backend", "frontend", "backup"))
    assert image_artifact["with"]["name"] == "runtime-image-archives"
    assert set(packaging["needs"]) >= {
        "windows-toolchains",
        "postgresql-integration",
        "dependency-security",
        "source-security",
        "deployment-images",
        "deployment-compose",
    }
    assert sum(step.get("uses", "").startswith("aquasecurity/trivy-action@") for step in package_steps) >= 3
    assert attestation["with"]["subject-path"] == "avicola-pro-release-bundle.tar"
    assert verification["needs"] == ["release-bundle"]
    assert verification["permissions"]["attestations"] == "read"
    assert "gh attestation verify" in verify_step["run"]
    assert "--source-digest" in verify_step["run"] and "--source-ref" in verify_step["run"]
    assert "tampered" in verify_step["run"]
    assert all("docker push" not in str(step.get("run", "")) for job in jobs.values() for step in job["steps"])


def test_runtime_images_upgrade_os_packages_during_build() -> None:
    runtime_dockerfiles = (
        PROJECT_ROOT / "backend" / "Dockerfile",
        PROJECT_ROOT / "frontend" / "Dockerfile",
        PROJECT_ROOT / "deploy" / "backup" / "Dockerfile",
    )

    assert all("apt-get upgrade --yes" in dockerfile.read_text(encoding="utf-8") for dockerfile in runtime_dockerfiles)


def test_runtime_images_use_current_trixie_bases_for_supported_toolchains() -> None:
    backend_dockerfile = (PROJECT_ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    frontend_dockerfile = (PROJECT_ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    backup_dockerfile = (PROJECT_ROOT / "deploy" / "backup" / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:3.13.15-slim-trixie AS runtime" in backend_dockerfile
    assert "FROM node:22.23.2-trixie-slim AS runtime" in frontend_dockerfile
    assert "FROM postgres:16.15-trixie" in backup_dockerfile
    assert "USER 10001:10001" in backend_dockerfile
    assert "USER node" in frontend_dockerfile
    assert "USER 10002:10002" in backup_dockerfile


def test_backend_runtime_contains_alembic_config_and_migrations() -> None:
    dockerfile = (PROJECT_ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    runtime_stage = dockerfile.split("AS runtime", maxsplit=1)[1]

    assert "COPY --chown=avicola:avicola backend/alembic.ini /app/alembic.ini" in runtime_stage
    assert "COPY --chown=avicola:avicola backend/migrations /app/migrations" in runtime_stage


def test_frontend_runtime_removes_unused_node_package_managers() -> None:
    dockerfile = (PROJECT_ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    runtime_stage = dockerfile.split("AS runtime", maxsplit=1)[1]

    assert "/usr/local/lib/node_modules/npm" in runtime_stage
    assert "/usr/local/lib/node_modules/corepack" in runtime_stage
    assert "npm ci" not in runtime_stage


def test_backup_restic_is_rebuilt_with_security_fixed_go_dependencies() -> None:
    dockerfile = (PROJECT_ROOT / "deploy" / "backup" / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM golang:1.26.8-trixie AS restic-builder" in dockerfile
    assert "ARG RESTIC_VERSION=0.19.1" in dockerfile
    assert "refs/tags/v${RESTIC_VERSION}:refs/tags/v${RESTIC_VERSION}" in dockerfile
    assert 'git rev-parse "v${RESTIC_VERSION}^{commit}"' in dockerfile
    assert "RESTIC_COMMIT=6aa3a516ce654808a1f28f9fa21e9b7c8e6e90bf" in dockerfile
    assert "golang.org/x/crypto@v0.55.0" in dockerfile
    assert "golang.org/x/net@v0.56.0" in dockerfile
    assert "golang.org/x/text@v0.39.0" in dockerfile
    assert "google.golang.org/grpc@v1.83.2" in dockerfile
    assert "apt-get install --no-install-recommends --yes python3" in dockerfile
    assert "USER nobody" not in dockerfile
    assert (
        "go test ./... -skip 'TestMount|TestScannerError|TestBackupErrors|"
        "TestArchiverErrorReporting/(file-unreadable|file-unreadable-ignore-error|"
        "file-subdir-unreadable|file-subdir-unreadable-ignore-error)'" in dockerfile
    )
    assert "does not expose /dev/fuse" in dockerfile
    assert "COPY --from=restic-builder" in dockerfile
    assert "COPY --from=restic/restic:" not in dockerfile


def test_trivy_sarif_scans_limit_report_severities_to_the_configured_gate() -> None:
    workflow = yaml.safe_load(CI_WORKFLOW_FILE.read_text(encoding="utf-8"))
    scan_steps = [
        step
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        if step.get("uses", "").startswith("aquasecurity/trivy-action@")
        and step.get("with", {}).get("format") == "sarif"
    ]

    assert scan_steps
    assert all(step.get("with", {}).get("limit-severities-for-sarif") is True for step in scan_steps)


def test_image_scans_all_run_before_high_or_critical_findings_fail_ci() -> None:
    workflow = yaml.safe_load(CI_WORKFLOW_FILE.read_text(encoding="utf-8"))
    image_steps = workflow["jobs"]["deployment-images"]["steps"]
    scan_steps = [step for step in image_steps if step.get("id", "").endswith("_image_scan")]
    enforcement_step = next(step for step in image_steps if step.get("name") == "Enforce all image security scans")

    assert {step["id"] for step in scan_steps} == {
        "backend_image_scan",
        "frontend_image_scan",
        "backup_image_scan",
    }
    assert all(step.get("continue-on-error") is True for step in scan_steps)
    assert all(f"steps.{step['id']}.outcome" in str(enforcement_step["env"]) for step in scan_steps)


def test_partial_ci_backend_suite_does_not_replace_the_full_suite_coverage_gate() -> None:
    workflow = yaml.safe_load(CI_WORKFLOW_FILE.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]
    windows_backend = next(
        step for step in jobs["windows-toolchains"]["steps"] if step.get("name") == "Backend locked install and checks"
    )
    postgres_backend = next(
        step
        for step in jobs["postgresql-integration"]["steps"]
        if step.get("name") == "Migrate and test with PostgreSQL 16"
    )

    assert 'uv run pytest -m "not integration" --no-cov' in windows_backend["run"]
    assert "uv run pytest" in postgres_backend["run"]
    assert "--no-cov" not in postgres_backend["run"]
