"""Validate a release evidence manifest and write a non-secret decision report."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_SHA = re.compile(r"^[0-9a-f]{40}$")
_TAG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_SNAPSHOT = re.compile(r"^[0-9a-f]{64}$")


class ReleaseGateError(ValueError):
    """Evidence is missing, inconsistent, or does not meet the selected gate."""


def verify_release_tag(repository: Path, tag: str, expected_commit: str) -> str:
    """Resolve an exact local Git tag and require it to point at the expected commit."""
    if not _TAG.fullmatch(tag) or not _SHA.fullmatch(expected_commit):
        raise ReleaseGateError("release tag or expected commit has an invalid format")
    git_executable = shutil.which("git")
    if git_executable is None:
        raise ReleaseGateError("Git executable is unavailable")
    result = subprocess.run(
        [git_executable, "-C", str(repository), "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )  # noqa: S603 - fixed Git executable and validated tag/SHA arguments
    resolved_commit = result.stdout.strip().lower()
    if result.returncode != 0 or not _SHA.fullmatch(resolved_commit) or resolved_commit != expected_commit:
        raise ReleaseGateError("release tag does not resolve to the exact expected commit")
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
        if isinstance(artifact, dict) and (name != "restore" or artifact.get("status") == "passed"):
            entries.append((name, artifact))

    for label, artifact in entries:
        if not isinstance(artifact, dict):
            raise ReleaseGateError(f"{label} report metadata is invalid")
        relative_name = artifact.get("report_file")
        if not isinstance(relative_name, str):
            raise ReleaseGateError(f"{label} report file is missing or invalid")
        relative_path = Path(relative_name)
        if not relative_name or relative_path.is_absolute() or ".." in relative_path.parts:
            raise ReleaseGateError(f"{label} report path must stay inside the evidence bundle")
        report_path = (root / relative_name).resolve(strict=True)
        if not report_path.is_relative_to(root):
            raise ReleaseGateError(f"{label} report path must stay inside the evidence bundle")
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
        raise ReleaseGateError("report path already exists; choose a fresh path to avoid stale evidence") from None


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReleaseGateError(f"{label} must be an object")
    return value


def _nonempty_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReleaseGateError(f"{label} is required")
    return value.strip()


def _timestamp(value: Any, label: str, *, now: datetime, max_age: timedelta) -> datetime:
    if not isinstance(value, str):
        raise ReleaseGateError(f"{label} timestamp is missing or invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ReleaseGateError(f"{label} timestamp is missing or invalid") from None
    if parsed.tzinfo is None or parsed > now or now - parsed > max_age:
        raise ReleaseGateError(f"stale {label} evidence")
    return parsed


def _pilot_blockers(evidence: dict[str, Any], *, now: datetime, max_age: timedelta) -> list[str]:
    blockers = ["trusted CI provenance verification is not configured"]
    restore = evidence.get("restore")
    if not isinstance(restore, dict) or restore.get("status") != "passed":
        blockers.append("restore evidence is missing or not passed")
    else:
        if not isinstance(restore.get("snapshot_id"), str) or not _SNAPSHOT.fullmatch(restore["snapshot_id"]):
            blockers.append("restore snapshot ID is missing or invalid")
        if not isinstance(restore.get("sha256"), str) or not _SNAPSHOT.fullmatch(restore["sha256"]):
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
    expected_migration_head = _nonempty_text(expected_migration_head, "trusted expected migration head")
    if (
        not isinstance(max_evidence_age_hours, int)
        or isinstance(max_evidence_age_hours, bool)
        or max_evidence_age_hours <= 0
    ):
        raise ReleaseGateError("maximum evidence age must be a positive number of hours")
    current_time = now or datetime.now(UTC)
    if current_time.tzinfo is None:
        raise ReleaseGateError("gate evaluation time must include a timezone")
    current_time = current_time.astimezone(UTC)
    max_age = timedelta(hours=max_evidence_age_hours)

    commit = _nonempty_text(evidence.get("commit"), "commit")
    if not _SHA.fullmatch(commit) or commit != expected_commit:
        raise ReleaseGateError("commit does not match the exact expected release commit")
    tag = _nonempty_text(evidence.get("release_tag"), "release tag")
    if tag != expected_tag:
        raise ReleaseGateError("release tag does not match the exact expected tag")

    manifest_head = _nonempty_text(evidence.get("expected_migration_head"), "expected Alembic head")
    if manifest_head != expected_migration_head:
        raise ReleaseGateError("manifest migration expectation does not match the trusted expected migration head")
    actual_head = _nonempty_text(evidence.get("alembic_head"), "actual Alembic head")
    if actual_head != expected_migration_head:
        raise ReleaseGateError(f"Alembic head {actual_head!r} does not match expected {expected_migration_head!r}")

    scans = _object(evidence.get("scans"), "scans")
    for scanner in ("dependency", "secrets", "image"):
        result = scans.get(scanner)
        if not isinstance(result, dict) or result.get("status") != "passed":
            raise ReleaseGateError(f"{scanner} scan is missing or not passed")
        report_hash = result.get("report_sha256")
        if not isinstance(report_hash, str) or not _SNAPSHOT.fullmatch(report_hash):
            raise ReleaseGateError(f"{scanner} report hash is missing or invalid")
        _timestamp(result.get("completed_at"), f"{scanner} scan", now=current_time, max_age=max_age)
    findings = _object(evidence.get("findings"), "findings")
    for severity in ("critical", "high"):
        count = findings.get(severity)
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ReleaseGateError(f"{severity} finding count must be a non-negative integer")
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
        raise ReleaseGateError("build evidence is missing, failed, or bound to another commit")
    if any(build_images.get(image) != images[image] for image in ("backend", "frontend", "backup")):
        raise ReleaseGateError("build evidence image digests do not match the release image digests")
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
        "restore_snapshot_id": restore.get("snapshot_id") if isinstance(restore, dict) else None,
        "restore_sha256": restore.get("sha256") if isinstance(restore, dict) else None,
        "restore_reconciliation": restore.get("reconciliation") if isinstance(restore, dict) else None,
        "rpo_minutes": operations.get("rpo_minutes") if isinstance(operations, dict) else None,
        "rto_minutes": operations.get("rto_minutes") if isinstance(operations, dict) else None,
        "evidence_max_age_hours": max_evidence_age_hours,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--mode", choices=("rc", "pilot"), required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--expected-tag", required=True)
    parser.add_argument("--expected-migration-head", required=True)
    parser.add_argument("--max-evidence-age-hours", required=True, type=int)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.report.exists():
            raise ReleaseGateError("report path already exists; choose a fresh path to avoid stale evidence")
        with args.evidence.open(encoding="utf-8") as evidence_file:
            evidence = json.load(evidence_file)
        evidence_object = _object(evidence, "evidence")
        verify_report_files(evidence_object, args.evidence.resolve().parent)
        report = validate_evidence(
            evidence_object,
            mode=args.mode,
            expected_commit=args.expected_commit,
            expected_tag=args.expected_tag,
            expected_migration_head=args.expected_migration_head,
            max_evidence_age_hours=args.max_evidence_age_hours,
        )
        verify_release_tag(Path(__file__).resolve().parents[1], args.expected_tag, args.expected_commit)
        rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        write_report_exclusively(args.report, rendered)
        sys.stdout.write(rendered)
        return 0
    except (OSError, json.JSONDecodeError, ReleaseGateError) as error:
        print(f"release gate failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
