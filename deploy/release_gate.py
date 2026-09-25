"""Validate a release evidence manifest and write a non-secret decision report."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.verify_release_attestation import (
    ReleaseAttestationError,
    verify_release_attestation,
)

_SHA = re.compile(r"^[0-9a-f]{40}$")
_TAG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_SNAPSHOT = re.compile(r"^[0-9a-f]{64}$")
_IMAGE_NAMES = ("backend", "frontend", "backup")
_REQUIRED_REPORTS = (
    "reports/compose-smoke-summary.txt",
    "reports/backup-restore-summary.txt",
    "reports/source-security/trivy-source.sarif",
    "reports/dependency-security/pip-audit.json",
    "reports/dependency-security/npm-audit.json",
    *(f"reports/image-security/{name}.sarif" for name in _IMAGE_NAMES),
)
_REQUIRED_GATES = (
    "windows_toolchains",
    "postgresql_integration",
    "dependency_security",
    "source_security",
    "image_security",
    "compose_topology",
    "compose_smoke",
    "backup_restore",
)
_MAX_BUNDLE_MEMBERS = 1000
_MAX_BUNDLE_TOTAL_BYTES = 5 * 1024**3
_MAX_BUNDLE_MEMBER_BYTES = 3 * 1024**3
_MAX_SMALL_FILE_BYTES = 64 * 1024**2
_MAX_MANIFEST_BYTES = 2 * 1024**2


class ReleaseGateError(ValueError):
    """Evidence is missing, inconsistent, or does not meet the selected gate."""


def validate_release_bundle(
    manifest: dict[str, Any],
    files: Mapping[str, bytes | Path],
    attestation: dict[str, Any],
    *,
    mode: str,
    expected_commit: str,
    expected_source_ref: str,
    expected_tag: str,
    expected_migration_head: str,
    max_evidence_age_hours: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate bundle content only after the caller authenticates its exact bytes."""
    if mode not in {"rc", "pilot"}:
        raise ReleaseGateError("mode must be rc or pilot")
    if (
        not _SHA.fullmatch(expected_commit)
        or not isinstance(expected_source_ref, str)
        or not expected_source_ref.startswith("refs/")
    ):
        raise ReleaseGateError("trusted expected source identity is invalid")
    if not _TAG.fullmatch(expected_tag):
        raise ReleaseGateError("expected release tag is invalid")
    expected_migration_head = _nonempty_text(
        expected_migration_head, "trusted expected migration head"
    )
    if (
        not isinstance(max_evidence_age_hours, int)
        or isinstance(max_evidence_age_hours, bool)
        or max_evidence_age_hours <= 0
    ):
        raise ReleaseGateError(
            "maximum evidence age must be a positive number of hours"
        )
    current_time = now or datetime.now(UTC)
    if current_time.tzinfo is None:
        raise ReleaseGateError("gate evaluation time must include a timezone")
    current_time = current_time.astimezone(UTC)
    max_age = timedelta(hours=max_evidence_age_hours)

    attested = _object(attestation, "verified provenance")
    if attested.get("repository") != "Rubio120/AVICOLA_PRO":
        raise ReleaseGateError(
            "attestation repository does not match trusted repository"
        )
    if attested.get("workflow") != "Rubio120/AVICOLA_PRO/.github/workflows/ci.yml":
        raise ReleaseGateError("attestation workflow does not match trusted workflow")
    if attested.get("source_commit") != expected_commit:
        raise ReleaseGateError("attestation commit does not match expected commit")
    if attested.get("source_ref") != expected_source_ref:
        raise ReleaseGateError("attestation ref does not match expected source ref")
    if not isinstance(attested.get("bundle_sha256"), str) or not _SNAPSHOT.fullmatch(
        attested["bundle_sha256"]
    ):
        raise ReleaseGateError("attestation bundle digest is missing or invalid")
    verified_at = _timestamp(
        attested.get("attestation_verified_at"),
        "attestation",
        now=current_time,
        max_age=max_age,
    )

    bundle_manifest = _object(manifest, "bundle manifest")
    if bundle_manifest.get("format_version") != 1:
        raise ReleaseGateError("release bundle format version is unsupported")
    if bundle_manifest.get("repository") != attested["repository"]:
        raise ReleaseGateError("manifest repository does not match attestation")
    workflow = _object(bundle_manifest.get("workflow"), "workflow")
    if (
        workflow.get("path") != ".github/workflows/ci.yml"
        or workflow.get("event") != "push"
    ):
        raise ReleaseGateError("manifest workflow identity or event is invalid")
    for key in ("run_id", "run_attempt"):
        if not isinstance(workflow.get(key), str) or not workflow[key].isdecimal():
            raise ReleaseGateError("manifest workflow run identity is invalid")
    source = _object(bundle_manifest.get("source"), "source")
    if source.get("commit") != expected_commit:
        raise ReleaseGateError("manifest commit does not match expected commit")
    if source.get("ref") != expected_source_ref:
        raise ReleaseGateError("manifest ref does not match expected source ref")
    migration = _object(bundle_manifest.get("migration"), "migration")
    if migration.get("head") != expected_migration_head:
        raise ReleaseGateError(
            "manifest migration head does not match trusted expected migration head"
        )

    gates = _object(bundle_manifest.get("gates"), "gates")
    for gate_name in _REQUIRED_GATES:
        if gates.get(gate_name) != "passed":
            raise ReleaseGateError(
                f"required CI gate {gate_name} is missing or not passed"
            )

    declared_files = set(files)
    expected_files = {"image-metadata.json", *_REQUIRED_REPORTS}
    images = _object(bundle_manifest.get("images"), "images")
    sboms = _object(bundle_manifest.get("sboms"), "SBOMs")
    if set(images) != set(_IMAGE_NAMES) or set(sboms) != set(_IMAGE_NAMES):
        raise ReleaseGateError(
            "bundle must contain exactly the three expected images and SBOMs"
        )
    archive_hashes: dict[str, str] = {}
    image_ids: dict[str, str] = {}
    for name in _IMAGE_NAMES:
        image = _object(images.get(name), f"{name} image")
        archive_path = _bundle_path(image.get("archive_path"), f"{name} image archive")
        if archive_path != f"images/avicola-pro-{name}.tar":
            raise ReleaseGateError(
                f"{name} image archive path is not the expected bundle path"
            )
        archive_hash = _file_sha256(files, archive_path, f"{name} image archive")
        if image.get("archive_sha256") != archive_hash:
            raise ReleaseGateError(f"{name} image archive hash does not match its file")
        image_id = image.get("docker_image_id")
        if not isinstance(image_id, str) or not _DIGEST.fullmatch(image_id):
            raise ReleaseGateError(f"{name} Docker image ID is missing or invalid")
        archive_hashes[name] = archive_hash
        image_ids[name] = image_id
        expected_files.add(archive_path)

        sbom = _object(sboms.get(name), f"{name} SBOM")
        sbom_path = _bundle_path(sbom.get("path"), f"{name} SBOM")
        if sbom_path != f"sbom/{name}.cdx.json":
            raise ReleaseGateError(f"{name} SBOM path is not the expected bundle path")
        sbom_bytes = _file_bytes(files, sbom_path, f"{name} SBOM")
        if sbom.get("sha256") != _sha256_bytes(sbom_bytes):
            raise ReleaseGateError(f"{name} SBOM hash does not match its file")
        try:
            sbom_data = json.loads(sbom_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ReleaseGateError(f"{name} SBOM is invalid JSON") from None
        if not isinstance(sbom_data, dict) or sbom_data.get("bomFormat") != "CycloneDX":
            raise ReleaseGateError(f"{name} SBOM is not CycloneDX")
        expected_files.add(sbom_path)

    try:
        image_metadata = json.loads(
            _file_bytes(files, "image-metadata.json", "image metadata")
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ReleaseGateError("image metadata is invalid JSON") from None
    if image_metadata != image_ids:
        raise ReleaseGateError("image metadata IDs do not match the bundle manifest")

    reports = _object(bundle_manifest.get("reports"), "reports")
    if set(reports) != set(_REQUIRED_REPORTS):
        raise ReleaseGateError(
            "bundle must contain exactly the required evidence reports"
        )
    report_hashes: dict[str, str] = {}
    for report_path in _REQUIRED_REPORTS:
        report = _object(reports.get(report_path), f"{report_path} report")
        report_bytes = _file_bytes(files, report_path, f"{report_path} report")
        report_hash = _sha256_bytes(report_bytes)
        if report.get("sha256") != report_hash:
            raise ReleaseGateError(f"{report_path} report hash does not match its file")
        if report_path.endswith((".sarif", ".json")):
            try:
                report_data = json.loads(report_bytes)
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise ReleaseGateError(
                    f"{report_path} report is invalid JSON"
                ) from None
            if report_path.startswith("reports/image-security/"):
                runs = (
                    report_data.get("runs") if isinstance(report_data, dict) else None
                )
                if not isinstance(runs, list) or any(
                    not isinstance(run, dict)
                    or not isinstance(run.get("results", []), list)
                    for run in runs
                ):
                    raise ReleaseGateError(
                        f"{report_path} image SARIF structure is invalid"
                    )
                if any(run.get("results", []) for run in runs):
                    raise ReleaseGateError(
                        "HIGH/CRITICAL runtime image findings must be zero"
                    )
        report_hashes[report_path] = report_hash
        expected_files.add(report_path)
    if declared_files != expected_files:
        raise ReleaseGateError("bundle contains missing or unreferenced files")
    if b"compose_smoke=passed" not in _file_bytes(
        files, _REQUIRED_REPORTS[0], "Compose smoke report"
    ):
        raise ReleaseGateError("authenticated Compose smoke report is not passed")
    if b"Restore reconciliation passed (9 checks)" not in _file_bytes(
        files, _REQUIRED_REPORTS[1], "backup restore report"
    ):
        raise ReleaseGateError(
            "backup restore report does not confirm nine reconciliations"
        )

    blockers = ["off-host restore, named RPO/RTO, owner and approver remain unverified"]
    if mode == "pilot":
        raise ReleaseGateError("pilot gate blocked: " + "; ".join(blockers))
    return {
        "commit": expected_commit,
        "source_ref": expected_source_ref,
        "release_tag": expected_tag,
        "technical_status": "ready_for_user_deployment",
        "pilot_status": "blocked",
        "migration_head": expected_migration_head,
        "attestation_verified_at": verified_at.isoformat().replace("+00:00", "Z"),
        "attestation_bundle_sha256": attested["bundle_sha256"],
        "workflow_run_id": workflow["run_id"],
        "workflow_run_attempt": workflow["run_attempt"],
        "image_archive_sha256": archive_hashes,
        "docker_image_ids": image_ids,
        "sbom_sha256": {name: sboms[name]["sha256"] for name in _IMAGE_NAMES},
        "report_sha256": report_hashes,
        "ci_gates": {name: "passed" for name in _REQUIRED_GATES},
        "evidence_max_age_hours": max_evidence_age_hours,
        "blockers": blockers,
    }


def _sha256_bytes(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def _file_sha256(files: Mapping[str, bytes | Path], path: str, label: str) -> str:
    source = files.get(path)
    digest = hashlib.sha256()
    if isinstance(source, bytes):
        digest.update(source)
    elif isinstance(source, Path) and source.is_file() and not source.is_symlink():
        with source.open("rb") as file_stream:
            for chunk in iter(lambda: file_stream.read(1024 * 1024), b""):
                digest.update(chunk)
    else:
        raise ReleaseGateError(f"{label} is missing or not a regular file")
    return digest.hexdigest()


def _bundle_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ReleaseGateError(f"{label} path is invalid")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ReleaseGateError(f"{label} path must stay inside the bundle")
    return path.as_posix()


def _file_bytes(files: Mapping[str, bytes | Path], path: str, label: str) -> bytes:
    contents = files.get(path)
    if isinstance(contents, bytes):
        if len(contents) > _MAX_SMALL_FILE_BYTES:
            raise ReleaseGateError(f"{label} exceeds the allowed size")
        return contents
    if (
        not isinstance(contents, Path)
        or not contents.is_file()
        or contents.is_symlink()
    ):
        raise ReleaseGateError(f"{label} is missing or not a regular file")
    if contents.stat().st_size > _MAX_SMALL_FILE_BYTES:
        raise ReleaseGateError(f"{label} exceeds the allowed size")
    return contents.read_bytes()


def read_release_bundle(
    bundle_path: Path, extraction_root: Path
) -> tuple[dict[str, Any], dict[str, Path]]:
    """Read a flat regular-file tar bundle without following links or extracting unsafe paths."""
    try:
        root = extraction_root.resolve(strict=True)
        bundle_file = bundle_path.resolve(strict=True)
        if (
            not root.is_dir()
            or extraction_root.is_symlink()
            or not bundle_file.is_file()
        ):
            raise ReleaseGateError("release bundle or extraction directory is invalid")
        if any(root.iterdir()):
            raise ReleaseGateError("release bundle extraction directory must be empty")
        names: set[str] = set()
        total_size = 0
        with tarfile.open(bundle_file, mode="r:") as archive:
            members = archive.getmembers()
            if not members or len(members) > _MAX_BUNDLE_MEMBERS:
                raise ReleaseGateError("release bundle member count is invalid")
            for member in members:
                name = member.name
                path = PurePosixPath(name)
                if (
                    not member.isfile()
                    or not name
                    or "\\" in name
                    or ":" in name
                    or path.is_absolute()
                    or path.as_posix() != name
                    or any(part in {"", ".", ".."} for part in path.parts)
                    or len(name) > 1024
                ):
                    raise ReleaseGateError(
                        "unsafe bundle member: paths, directories and links are rejected"
                    )
                if name in names:
                    raise ReleaseGateError("unsafe bundle member: duplicate path")
                if member.size < 0 or member.size > _MAX_BUNDLE_MEMBER_BYTES:
                    raise ReleaseGateError(
                        "release bundle member exceeds the allowed size"
                    )
                total_size += member.size
                if total_size > _MAX_BUNDLE_TOTAL_BYTES:
                    raise ReleaseGateError(
                        "release bundle exceeds the allowed total size"
                    )
                names.add(name)
                destination = root.joinpath(*path.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if not destination.resolve().is_relative_to(root):
                    raise ReleaseGateError(
                        "unsafe bundle member: path escapes extraction directory"
                    )
                source = archive.extractfile(member)
                if source is None:
                    raise ReleaseGateError("release bundle member could not be read")
                remaining = member.size
                with destination.open("xb") as output:
                    while remaining:
                        block = source.read(min(1024 * 1024, remaining))
                        if not block:
                            raise ReleaseGateError("release bundle member is truncated")
                        output.write(block)
                        remaining -= len(block)
        manifest_path = root / "manifest.json"
        if (
            "manifest.json" not in names
            or manifest_path.stat().st_size > _MAX_MANIFEST_BYTES
        ):
            raise ReleaseGateError("release bundle manifest is missing or too large")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ReleaseGateError("release bundle manifest must be an object")
        return manifest, {
            name: root.joinpath(*PurePosixPath(name).parts)
            for name in names
            if name != "manifest.json"
        }
    except ReleaseGateError:
        raise
    except (OSError, tarfile.TarError, json.JSONDecodeError, UnicodeDecodeError):
        raise ReleaseGateError("release bundle is unreadable or malformed") from None


def verify_release_tag(repository: Path, tag: str, expected_commit: str) -> str:
    """Resolve an exact local Git tag and require it to point at the expected commit."""
    if not _TAG.fullmatch(tag) or not _SHA.fullmatch(expected_commit):
        raise ReleaseGateError("release tag or expected commit has an invalid format")
    git_executable = shutil.which("git")
    if git_executable is None:
        raise ReleaseGateError("Git executable is unavailable")
    result = subprocess.run(
        [
            git_executable,
            "-C",
            str(repository),
            "rev-parse",
            "--verify",
            f"refs/tags/{tag}^{{commit}}",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    resolved_commit = result.stdout.strip().lower()
    if (
        result.returncode != 0
        or not _SHA.fullmatch(resolved_commit)
        or resolved_commit != expected_commit
    ):
        raise ReleaseGateError(
            "release tag does not resolve to the exact expected commit"
        )
    return resolved_commit


def verify_report_files(evidence: dict[str, Any], evidence_root: Path) -> None:
    """Verify report bytes against declared hashes, refusing paths outside the evidence bundle."""
    root = evidence_root.resolve(strict=True)
    entries: list[tuple[str, Any]] = []
    scans = evidence.get("scans")
    if isinstance(scans, dict):
        entries.extend((f"{name} scan", artifact) for name, artifact in scans.items())
    for name in ("build", "smoke", "restore"):
        artifact = evidence.get(name)
        if isinstance(artifact, dict) and (
            name != "restore" or artifact.get("status") == "passed"
        ):
            entries.append((name, artifact))

    for label, artifact in entries:
        if not isinstance(artifact, dict):
            raise ReleaseGateError(f"{label} report metadata is invalid")
        relative_name = artifact.get("report_file")
        if not isinstance(relative_name, str):
            raise ReleaseGateError(f"{label} report file is missing or invalid")
        relative_path = Path(relative_name)
        if (
            not relative_name
            or relative_path.is_absolute()
            or ".." in relative_path.parts
        ):
            raise ReleaseGateError(
                f"{label} report path must stay inside the evidence bundle"
            )
        report_path = (root / relative_name).resolve(strict=True)
        if not report_path.is_relative_to(root):
            raise ReleaseGateError(
                f"{label} report path must stay inside the evidence bundle"
            )
        if not report_path.is_file():
            raise ReleaseGateError(f"{label} report is not a regular file")
        digest = hashlib.sha256()
        with report_path.open("rb") as report_file:
            for chunk in iter(lambda: report_file.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != artifact.get("report_sha256"):
            raise ReleaseGateError(f"{label} report hash does not match its file")


def write_report_exclusively(report_path: Path, contents: str) -> None:
    """Create a new report without overwriting a file created concurrently."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with report_path.open("x", encoding="utf-8") as report_file:
            report_file.write(contents)
    except FileExistsError:
        raise ReleaseGateError(
            "report path already exists; choose a fresh path to avoid stale evidence"
        ) from None


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReleaseGateError(f"{label} must be an object")
    return value


def _nonempty_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReleaseGateError(f"{label} is required")
    return value.strip()


def _timestamp(
    value: Any, label: str, *, now: datetime, max_age: timedelta
) -> datetime:
    if not isinstance(value, str):
        raise ReleaseGateError(f"{label} timestamp is missing or invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ReleaseGateError(f"{label} timestamp is missing or invalid") from None
    if parsed.tzinfo is None or parsed > now or now - parsed > max_age:
        raise ReleaseGateError(f"stale {label} evidence")
    return parsed


def _pilot_blockers(
    evidence: dict[str, Any], *, now: datetime, max_age: timedelta
) -> list[str]:
    blockers = ["trusted CI provenance verification is not configured"]
    restore = evidence.get("restore")
    if not isinstance(restore, dict) or restore.get("status") != "passed":
        blockers.append("restore evidence is missing or not passed")
    else:
        if not isinstance(restore.get("snapshot_id"), str) or not _SNAPSHOT.fullmatch(
            restore["snapshot_id"]
        ):
            blockers.append("restore snapshot ID is missing or invalid")
        if not isinstance(restore.get("sha256"), str) or not _SNAPSHOT.fullmatch(
            restore["sha256"]
        ):
            blockers.append("restore SHA-256 is missing or invalid")
        if restore.get("reconciliation") != "passed":
            blockers.append("restore reconciliation is missing or not passed")
        try:
            _timestamp(restore.get("completed_at"), "restore", now=now, max_age=max_age)
        except ReleaseGateError:
            blockers.append("restore evidence is missing a fresh completion timestamp")

    operations = evidence.get("operations")
    if not isinstance(operations, dict):
        operations = {}
    for name in ("rpo", "rto"):
        if operations.get(f"{name}_approved") is not True:
            blockers.append(f"{name.upper()} approval is missing")
        minutes = operations.get(f"{name}_minutes")
        if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes <= 0:
            blockers.append(f"approved {name.upper()} minutes are missing or invalid")
    for name in ("owner", "approver"):
        if not isinstance(operations.get(name), str) or not operations[name].strip():
            blockers.append(f"named operational {name} is missing")
    return blockers


def validate_evidence(
    evidence: dict[str, Any],
    *,
    mode: str,
    expected_commit: str,
    expected_tag: str,
    expected_migration_head: str,
    max_evidence_age_hours: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate technical evidence; pilot mode additionally requires external approvals."""
    if mode not in {"rc", "pilot"}:
        raise ReleaseGateError("mode must be rc or pilot")
    if not _SHA.fullmatch(expected_commit):
        raise ReleaseGateError("expected commit must be a full 40-character Git SHA")
    expected_tag = _nonempty_text(expected_tag, "expected release tag")
    expected_migration_head = _nonempty_text(
        expected_migration_head, "trusted expected migration head"
    )
    if (
        not isinstance(max_evidence_age_hours, int)
        or isinstance(max_evidence_age_hours, bool)
        or max_evidence_age_hours <= 0
    ):
        raise ReleaseGateError(
            "maximum evidence age must be a positive number of hours"
        )
    current_time = now or datetime.now(UTC)
    if current_time.tzinfo is None:
        raise ReleaseGateError("gate evaluation time must include a timezone")
    current_time = current_time.astimezone(UTC)
    max_age = timedelta(hours=max_evidence_age_hours)

    commit = _nonempty_text(evidence.get("commit"), "commit")
    if not _SHA.fullmatch(commit) or commit != expected_commit:
        raise ReleaseGateError(
            "commit does not match the exact expected release commit"
        )
    tag = _nonempty_text(evidence.get("release_tag"), "release tag")
    if tag != expected_tag:
        raise ReleaseGateError("release tag does not match the exact expected tag")

    manifest_head = _nonempty_text(
        evidence.get("expected_migration_head"), "expected Alembic head"
    )
    if manifest_head != expected_migration_head:
        raise ReleaseGateError(
            "manifest migration expectation does not match the trusted expected migration head"
        )
    actual_head = _nonempty_text(evidence.get("alembic_head"), "actual Alembic head")
    if actual_head != expected_migration_head:
        raise ReleaseGateError(
            f"Alembic head {actual_head!r} does not match expected {expected_migration_head!r}"
        )

    scans = _object(evidence.get("scans"), "scans")
    for scanner in ("dependency", "secrets", "image"):
        result = scans.get(scanner)
        if not isinstance(result, dict) or result.get("status") != "passed":
            raise ReleaseGateError(f"{scanner} scan is missing or not passed")
        report_hash = result.get("report_sha256")
        if not isinstance(report_hash, str) or not _SNAPSHOT.fullmatch(report_hash):
            raise ReleaseGateError(f"{scanner} report hash is missing or invalid")
        _timestamp(
            result.get("completed_at"),
            f"{scanner} scan",
            now=current_time,
            max_age=max_age,
        )
    findings = _object(evidence.get("findings"), "findings")
    for severity in ("critical", "high"):
        count = findings.get(severity)
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ReleaseGateError(
                f"{severity} finding count must be a non-negative integer"
            )
        if count:
            raise ReleaseGateError(f"{severity} findings must be zero (found {count})")

    images = _object(evidence.get("images"), "images")
    for image in ("backend", "frontend", "backup"):
        digest = images.get(image)
        if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            raise ReleaseGateError(f"{image} image digest is missing or invalid")
    build = _object(evidence.get("build"), "build")
    build_images = _object(build.get("image_digests"), "build image digests")
    if build.get("status") != "passed" or build.get("commit") != commit:
        raise ReleaseGateError(
            "build evidence is missing, failed, or bound to another commit"
        )
    if any(
        build_images.get(image) != images[image]
        for image in ("backend", "frontend", "backup")
    ):
        raise ReleaseGateError(
            "build evidence image digests do not match the release image digests"
        )
    _timestamp(build.get("built_at"), "build", now=current_time, max_age=max_age)
    smoke = _object(evidence.get("smoke"), "smoke")
    if smoke.get("status") != "passed" or smoke.get("tested_commit") != commit:
        raise ReleaseGateError("smoke test is missing or not passed")
    smoke_hash = smoke.get("report_sha256")
    if not isinstance(smoke_hash, str) or not _SNAPSHOT.fullmatch(smoke_hash):
        raise ReleaseGateError("smoke report hash is missing or invalid")
    _timestamp(smoke.get("completed_at"), "smoke", now=current_time, max_age=max_age)

    blockers = _pilot_blockers(evidence, now=current_time, max_age=max_age)
    if mode == "pilot" and blockers:
        raise ReleaseGateError("pilot gate blocked: " + "; ".join(blockers))

    restore = evidence.get("restore")
    operations = evidence.get("operations")
    return {
        "commit": commit,
        "release_tag": tag,
        "technical_status": "manifest_validated",
        "pilot_status": "approved" if not blockers else "blocked",
        "migration_head": actual_head,
        "image_digests": images,
        "scans": scans,
        "critical_findings": findings["critical"],
        "high_findings": findings["high"],
        "smoke_status": smoke["status"],
        "build_completed_at": build["built_at"],
        "smoke_completed_at": smoke["completed_at"],
        "restore_snapshot_id": restore.get("snapshot_id")
        if isinstance(restore, dict)
        else None,
        "restore_sha256": restore.get("sha256") if isinstance(restore, dict) else None,
        "restore_reconciliation": restore.get("reconciliation")
        if isinstance(restore, dict)
        else None,
        "rpo_minutes": operations.get("rpo_minutes")
        if isinstance(operations, dict)
        else None,
        "rto_minutes": operations.get("rto_minutes")
        if isinstance(operations, dict)
        else None,
        "evidence_max_age_hours": max_evidence_age_hours,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--mode", choices=("rc", "pilot"), required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--expected-source-ref", required=True)
    parser.add_argument("--expected-tag", required=True)
    parser.add_argument("--expected-migration-head", required=True)
    parser.add_argument("--max-evidence-age-hours", required=True, type=int)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.report.exists():
            raise ReleaseGateError(
                "report path already exists; choose a fresh path to avoid stale evidence"
            )
        attestation = verify_release_attestation(
            args.bundle, args.expected_commit, args.expected_source_ref
        )
        with tempfile.TemporaryDirectory(
            prefix="avicola-release-gate-"
        ) as temporary_directory:
            manifest, files = read_release_bundle(
                args.bundle, Path(temporary_directory)
            )
            report = validate_release_bundle(
                manifest,
                files,
                attestation,
                mode=args.mode,
                expected_commit=args.expected_commit,
                expected_source_ref=args.expected_source_ref,
                expected_tag=args.expected_tag,
                expected_migration_head=args.expected_migration_head,
                max_evidence_age_hours=args.max_evidence_age_hours,
            )
        verify_release_tag(_PROJECT_ROOT, args.expected_tag, args.expected_commit)
        rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        write_report_exclusively(args.report, rendered)
        sys.stdout.write(rendered)
        return 0
    except (
        OSError,
        json.JSONDecodeError,
        ReleaseGateError,
        ReleaseAttestationError,
    ) as error:
        print(f"release gate failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
