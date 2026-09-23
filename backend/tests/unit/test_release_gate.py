from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
EXPECTED_HEAD = "0010_costing"
EXPECTED_TAG = "v0.1.0-rc.1"
NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
GIT = shutil.which("git")

from deploy.release_gate import (  # noqa: E402
    ReleaseGateError,
    validate_evidence,
    verify_release_tag,
    verify_report_files,
    write_report_exclusively,
)


def valid_evidence() -> dict[str, Any]:
    return {
        "commit": "a" * 40,
        "release_tag": EXPECTED_TAG,
        "expected_migration_head": EXPECTED_HEAD,
        "alembic_head": EXPECTED_HEAD,
        "scans": {
            name: {
                "status": "passed",
                "report_sha256": chr(100 + index) * 64,
                "completed_at": NOW.isoformat(),
            }
            for index, name in enumerate(("dependency", "secrets", "image"))
        },
        "findings": {"critical": 0, "high": 0},
        "restore": {
            "status": "passed",
            "snapshot_id": "b" * 64,
            "sha256": "c" * 64,
            "reconciliation": "passed",
            "completed_at": NOW.isoformat(),
        },
        "operations": {
            "rpo_approved": True,
            "rpo_minutes": 60,
            "rto_approved": True,
            "rto_minutes": 240,
            "owner": "responsable-ejemplo",
            "approver": "aprobador-ejemplo",
        },
        "images": {
            "backend": "sha256:" + "d" * 64,
            "frontend": "sha256:" + "e" * 64,
            "backup": "sha256:" + "9" * 64,
        },
        "build": {
            "status": "passed",
            "commit": "a" * 40,
            "built_at": NOW.isoformat(),
            "image_digests": {
                "backend": "sha256:" + "d" * 64,
                "frontend": "sha256:" + "e" * 64,
                "backup": "sha256:" + "9" * 64,
            },
        },
        "smoke": {
            "status": "passed",
            "tested_commit": "a" * 40,
            "completed_at": NOW.isoformat(),
            "report_sha256": "f" * 64,
        },
    }


def test_release_gate_validates_manifest_without_claiming_unverified_readiness() -> None:
    report = validate_evidence(
        valid_evidence(),
        mode="rc",
        expected_commit="a" * 40,
        expected_tag=EXPECTED_TAG,
        expected_migration_head=EXPECTED_HEAD,
        max_evidence_age_hours=24,
        now=NOW,
    )

    assert report["technical_status"] == "manifest_validated"
    assert report["pilot_status"] == "blocked"
    assert any("trusted CI provenance" in blocker for blocker in report["blockers"])


def test_release_gate_requires_backup_image_digest_to_match_build_evidence() -> None:
    evidence = valid_evidence()
    evidence["images"]["backup"] = "sha256:" + "1" * 64
    evidence["build"]["image_digests"]["backup"] = "sha256:" + "2" * 64

    with pytest.raises(ReleaseGateError, match="image digests do not match"):
        validate_evidence(
            evidence,
            mode="rc",
            expected_commit="a" * 40,
            expected_tag=EXPECTED_TAG,
            expected_migration_head=EXPECTED_HEAD,
            max_evidence_age_hours=24,
            now=NOW,
        )


def test_release_gate_rejects_evidence_without_a_backup_image_digest() -> None:
    evidence = valid_evidence()
    evidence["images"].pop("backup")

    with pytest.raises(ReleaseGateError, match="backup image digest is missing or invalid"):
        validate_evidence(
            evidence,
            mode="rc",
            expected_commit="a" * 40,
            expected_tag=EXPECTED_TAG,
            expected_migration_head=EXPECTED_HEAD,
            max_evidence_age_hours=24,
            now=NOW,
        )


def test_pilot_gate_fails_closed_when_trusted_provenance_verification_is_unconfigured() -> None:
    with pytest.raises(ReleaseGateError, match="trusted CI provenance"):
        validate_evidence(
            valid_evidence(),
            mode="pilot",
            expected_commit="a" * 40,
            expected_tag=EXPECTED_TAG,
            expected_migration_head=EXPECTED_HEAD,
            max_evidence_age_hours=24,
            now=NOW,
        )


def test_release_tag_must_resolve_to_the_expected_git_commit(tmp_path: Path) -> None:
    assert GIT is not None
    repository = tmp_path / "repo"
    repository.mkdir()
    for args in (
        [GIT, "init", "--quiet", str(repository)],
        [GIT, "-C", str(repository), "config", "user.name", "Release Gate Test"],
        [GIT, "-C", str(repository), "config", "user.email", "release-gate@example.invalid"],
        [GIT, "-C", str(repository), "commit", "--allow-empty", "--quiet", "-m", "test"],
    ):
        assert subprocess.run(args, check=False, capture_output=True).returncode == 0
    commit = subprocess.run(
        [GIT, "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert (
        subprocess.run([GIT, "-C", str(repository), "tag", EXPECTED_TAG], check=False, capture_output=True).returncode
        == 0
    )

    assert verify_release_tag(repository, EXPECTED_TAG, commit) == commit
    with pytest.raises(ReleaseGateError, match="does not resolve"):
        verify_release_tag(repository, EXPECTED_TAG, "f" * 40)


def test_release_tag_verification_fails_clearly_when_git_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)

    with pytest.raises(ReleaseGateError, match="Git executable is unavailable"):
        verify_release_tag(tmp_path, EXPECTED_TAG, "a" * 40)


def test_report_creation_never_overwrites_a_file_created_after_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report_path = tmp_path / "report.json"
    original_open = Path.open

    def create_between_check_and_write(path: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if path == report_path and mode == "x":
            report_path.write_text("concurrent report", encoding="utf-8")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", create_between_check_and_write)

    with pytest.raises(ReleaseGateError, match="report path already exists"):
        write_report_exclusively(report_path, "gate report")

    assert report_path.read_text(encoding="utf-8") == "concurrent report"


def test_release_gate_hashes_actual_report_files_and_rejects_path_escape(tmp_path: Path) -> None:
    evidence = valid_evidence()
    report_directory = tmp_path / "evidence"
    report_directory.mkdir()
    artifacts = [*evidence["scans"].values(), evidence["build"], evidence["smoke"], evidence["restore"]]
    for index, artifact in enumerate(artifacts):
        report_name = f"report-{index}.json"
        report_data = f'{{"report": {index}}}'.encode()
        (report_directory / report_name).write_bytes(report_data)
        artifact["report_file"] = report_name
        artifact["report_sha256"] = hashlib.sha256(report_data).hexdigest()

    verify_report_files(evidence, report_directory)

    evidence["scans"]["image"]["report_sha256"] = "0" * 64
    with pytest.raises(ReleaseGateError, match="image scan report hash does not match"):
        verify_report_files(evidence, report_directory)

    evidence["scans"]["image"]["report_file"] = "../outside.json"
    with pytest.raises(ReleaseGateError, match="must stay inside"):
        verify_report_files(evidence, report_directory)


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda data: data.update(commit=""), "commit"),
        (lambda data: data.update(alembic_head="0009_treasury"), "Alembic"),
        (lambda data: data["scans"].pop("image"), "image scan"),
        (lambda data: data["scans"]["dependency"].update(report_sha256="invalid"), "dependency report hash"),
        (lambda data: data["restore"].update(status="failed"), "restore"),
        (lambda data: data["operations"].update(rpo_approved=False), "RPO"),
        (lambda data: data["operations"].update(rto_approved=False), "RTO"),
        (lambda data: data["findings"].update(critical=1), "critical"),
        (lambda data: data["findings"].update(high=1), "high"),
    ],
)
def test_pilot_gate_fails_closed_for_missing_or_unaccepted_evidence(
    mutate: Callable[[dict[str, Any]], None], expected: str
) -> None:
    evidence = valid_evidence()
    mutate(evidence)

    with pytest.raises(ReleaseGateError, match=expected):
        validate_evidence(
            evidence,
            mode="pilot",
            expected_commit="a" * 40,
            expected_tag=EXPECTED_TAG,
            expected_migration_head=EXPECTED_HEAD,
            max_evidence_age_hours=24,
            now=NOW,
        )


def test_rc_report_can_be_technically_ready_while_external_pilot_gates_are_open() -> None:
    evidence = valid_evidence()
    evidence["restore"] = {}
    evidence["operations"] = {}

    report = validate_evidence(
        evidence,
        mode="rc",
        expected_commit="a" * 40,
        expected_tag=EXPECTED_TAG,
        expected_migration_head=EXPECTED_HEAD,
        max_evidence_age_hours=24,
        now=NOW,
    )

    assert report["technical_status"] == "manifest_validated"
    assert report["pilot_status"] == "blocked"
    assert any("restore" in blocker.lower() for blocker in report["blockers"])
    assert any("RPO" in blocker for blocker in report["blockers"])


def test_release_gate_command_rejects_mismatched_commit_and_writes_no_success_report(tmp_path: Path) -> None:
    evidence_file = tmp_path / "evidence.json"
    report_file = tmp_path / "report.json"
    evidence = valid_evidence()
    for index, artifact in enumerate(
        [*evidence["scans"].values(), evidence["build"], evidence["smoke"], evidence["restore"]]
    ):
        report_name = f"report-{index}.json"
        report_data = f'{{"report": {index}}}'.encode()
        (tmp_path / report_name).write_bytes(report_data)
        artifact["report_file"] = report_name
        artifact["report_sha256"] = hashlib.sha256(report_data).hexdigest()
    evidence_file.write_text(json.dumps(evidence), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "deploy" / "release_gate.py"),
            "--evidence",
            str(evidence_file),
            "--mode",
            "rc",
            "--expected-commit",
            "f" * 40,
            "--expected-tag",
            EXPECTED_TAG,
            "--expected-migration-head",
            EXPECTED_HEAD,
            "--max-evidence-age-hours",
            "24",
            "--report",
            str(report_file),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode != 0
    assert "commit" in result.stderr.lower()
    assert not report_file.exists()


def test_gate_compares_migration_and_tag_to_trusted_expected_values_not_manifest_claims() -> None:
    evidence = valid_evidence()
    evidence["expected_migration_head"] = "untrusted-manifest-value"

    with pytest.raises(ReleaseGateError, match="expected migration head"):
        validate_evidence(
            evidence,
            mode="rc",
            expected_commit="a" * 40,
            expected_tag=EXPECTED_TAG,
            expected_migration_head=EXPECTED_HEAD,
            max_evidence_age_hours=24,
            now=NOW,
        )


def test_gate_rejects_a_release_tag_that_differs_from_the_trusted_tag() -> None:
    with pytest.raises(ReleaseGateError, match="release tag"):
        validate_evidence(
            valid_evidence(),
            mode="rc",
            expected_commit="a" * 40,
            expected_tag="v0.1.0-rc.2",
            expected_migration_head=EXPECTED_HEAD,
            max_evidence_age_hours=24,
            now=NOW,
        )


def test_gate_rejects_stale_scanner_evidence_at_an_operator_supplied_age_limit() -> None:
    evidence = valid_evidence()
    evidence["scans"]["dependency"]["completed_at"] = (NOW - timedelta(hours=25)).isoformat()

    with pytest.raises(ReleaseGateError, match="stale dependency scan"):
        validate_evidence(
            evidence,
            mode="rc",
            expected_commit="a" * 40,
            expected_tag=EXPECTED_TAG,
            expected_migration_head=EXPECTED_HEAD,
            max_evidence_age_hours=24,
            now=NOW,
        )


@pytest.mark.parametrize("field", ("commit", "backend_digest"))
def test_gate_rejects_build_evidence_not_bound_to_release(field: str) -> None:
    evidence = valid_evidence()
    if field == "commit":
        evidence["build"]["commit"] = "f" * 40
    else:
        evidence["build"]["image_digests"]["backend"] = "sha256:" + "f" * 64

    with pytest.raises(ReleaseGateError, match="build evidence"):
        validate_evidence(
            evidence,
            mode="rc",
            expected_commit="a" * 40,
            expected_tag=EXPECTED_TAG,
            expected_migration_head=EXPECTED_HEAD,
            max_evidence_age_hours=24,
            now=NOW,
        )


def test_release_gate_cli_requires_a_saved_report_instead_of_stdout_only() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "deploy" / "release_gate.py"),
            "--evidence",
            "missing-evidence.json",
            "--mode",
            "rc",
            "--expected-commit",
            "a" * 40,
            "--expected-tag",
            EXPECTED_TAG,
            "--expected-migration-head",
            EXPECTED_HEAD,
            "--max-evidence-age-hours",
            "24",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode != 0
    assert "--report" in result.stderr
