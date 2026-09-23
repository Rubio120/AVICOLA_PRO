from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.verify_release_attestation import (  # noqa: E402
    ReleaseAttestationError,
    verify_release_attestation,
)

COMMIT = "a" * 40
SOURCE_REF = "refs/heads/weekend/autonomous"
WORKFLOW_SAN = f"https://github.com/Rubio120/AVICOLA_PRO/.github/workflows/ci.yml@{SOURCE_REF}"


def _verification_output(
    bundle_path: Path,
    *,
    repository: str = "Rubio120/AVICOLA_PRO",
    san: str = WORKFLOW_SAN,
) -> str:
    digest = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    return json.dumps(
        [
            {
                "verificationResult": {
                    "signature": {
                        "certificate": {
                            "sourceRepository": repository,
                            "sourceRepositoryOwner": "Rubio120",
                            "subjectAlternativeName": san,
                        }
                    },
                    "statement": {
                        "subject": [
                            {
                                "name": "avicola-pro-release-bundle.tar",
                                "digest": {"sha256": digest},
                            }
                        ]
                    },
                }
            }
        ]
    )


def test_release_attestation_verifies_exact_source_identity_and_bundle_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "avicola-pro-release-bundle.tar"
    bundle.write_bytes(b"synthetic-release-bundle")
    calls: list[list[str]] = []

    def run(arguments: list[str], **_: Any) -> CompletedProcess[str]:
        calls.append(arguments)
        return CompletedProcess(arguments, 0, _verification_output(bundle), "")

    monkeypatch.setattr("scripts.verify_release_attestation.subprocess.run", run)

    verified = verify_release_attestation(bundle, COMMIT, SOURCE_REF, gh_executable="gh")

    assert verified["repository"] == "Rubio120/AVICOLA_PRO"
    assert verified["source_commit"] == COMMIT
    assert verified["source_ref"] == SOURCE_REF
    assert verified["bundle_sha256"] == hashlib.sha256(bundle.read_bytes()).hexdigest()
    command = calls[0]
    assert "--repo" in command and command[command.index("--repo") + 1] == "Rubio120/AVICOLA_PRO"
    assert "--signer-workflow" in command
    assert "--source-digest" in command and command[command.index("--source-digest") + 1] == COMMIT
    assert "--source-ref" in command and command[command.index("--source-ref") + 1] == SOURCE_REF


@pytest.mark.parametrize(
    ("stdout", "repository", "san", "message"),
    [
        ("not-json", "Rubio120/AVICOLA_PRO", WORKFLOW_SAN, "JSON"),
        ("[]", "Rubio120/OTHER", WORKFLOW_SAN, "repository"),
        (
            "[]",
            "Rubio120/AVICOLA_PRO",
            WORKFLOW_SAN.replace("ci.yml", "other.yml"),
            "workflow",
        ),
    ],
)
def test_release_attestation_rejects_invalid_output_or_signer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stdout: str,
    repository: str,
    san: str,
    message: str,
) -> None:
    bundle = tmp_path / "bundle.tar"
    bundle.write_bytes(b"synthetic")
    output = stdout if stdout != "[]" else _verification_output(bundle, repository=repository, san=san)
    monkeypatch.setattr(
        "scripts.verify_release_attestation.subprocess.run",
        lambda arguments, **kwargs: CompletedProcess(arguments, 0, output, ""),
    )

    with pytest.raises(ReleaseAttestationError, match=message):
        verify_release_attestation(bundle, COMMIT, SOURCE_REF, gh_executable="gh")


def test_release_attestation_rejects_subject_digest_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = tmp_path / "bundle.tar"
    bundle.write_bytes(b"expected-bytes")
    forged = json.loads(_verification_output(bundle))
    forged[0]["verificationResult"]["statement"]["subject"][0]["digest"]["sha256"] = "0" * 64
    monkeypatch.setattr(
        "scripts.verify_release_attestation.subprocess.run",
        lambda arguments, **kwargs: CompletedProcess(arguments, 0, json.dumps(forged), ""),
    )

    with pytest.raises(ReleaseAttestationError, match="digest"):
        verify_release_attestation(bundle, COMMIT, SOURCE_REF, gh_executable="gh")


@pytest.mark.parametrize(("commit", "source_ref"), [("b" * 40, SOURCE_REF), (COMMIT, "refs/heads/other")])
def test_release_attestation_passes_exact_commit_and_ref_to_gh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    commit: str,
    source_ref: str,
) -> None:
    bundle = tmp_path / "bundle.tar"
    bundle.write_bytes(b"synthetic")
    calls: list[list[str]] = []

    def run(arguments: list[str], **_: Any) -> CompletedProcess[str]:
        calls.append(arguments)
        requested_commit = arguments[arguments.index("--source-digest") + 1]
        requested_ref = arguments[arguments.index("--source-ref") + 1]
        status = 0 if (requested_commit, requested_ref) == (COMMIT, SOURCE_REF) else 1
        return CompletedProcess(arguments, status, _verification_output(bundle) if status == 0 else "", "")

    monkeypatch.setattr("scripts.verify_release_attestation.subprocess.run", run)

    with pytest.raises(ReleaseAttestationError, match="verification failed"):
        verify_release_attestation(bundle, commit, source_ref, gh_executable="gh")
    assert calls


def test_release_attestation_rejects_missing_gh_and_failed_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "bundle.tar"
    bundle.write_bytes(b"synthetic")

    def missing_executable(*_: Any, **__: Any) -> CompletedProcess[str]:
        raise FileNotFoundError("gh")

    monkeypatch.setattr("scripts.verify_release_attestation.subprocess.run", missing_executable)
    with pytest.raises(ReleaseAttestationError, match="unavailable"):
        verify_release_attestation(bundle, COMMIT, SOURCE_REF, gh_executable="missing-gh")

    monkeypatch.setattr(
        "scripts.verify_release_attestation.subprocess.run",
        lambda arguments, **kwargs: CompletedProcess(arguments, 1, "", "denied"),
    )
    with pytest.raises(ReleaseAttestationError, match="verification failed"):
        verify_release_attestation(bundle, COMMIT, SOURCE_REF, gh_executable="gh")
