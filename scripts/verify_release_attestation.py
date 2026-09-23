"""Verify GitHub's signed provenance for an exact release bundle and source revision."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

REPOSITORY = "Rubio120/AVICOLA_PRO"
SIGNER_WORKFLOW = "Rubio120/AVICOLA_PRO/.github/workflows/ci.yml"
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_SOURCE_REF = re.compile(r"refs/(?:heads|tags)/[A-Za-z0-9._/-]+\Z|refs/pull/[0-9]+/(?:merge|head)\Z")


class ReleaseAttestationError(ValueError):
    """The release bundle or its verified provenance does not match policy."""


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReleaseAttestationError(f"verified attestation {label} is malformed")
    return value


def _matching_verified_attestation(output: Any, *, bundle_name: str, digest: str, source_ref: str) -> bool:
    if not isinstance(output, list) or not output:
        raise ReleaseAttestationError("GitHub CLI returned no verified attestations")
    repository_mismatch = False
    signer_mismatch = False
    digest_mismatch = False
    for item in output:
        result = _object(item, "result").get("verificationResult")
        if not isinstance(result, dict):
            continue
        signature = result.get("signature")
        if not isinstance(signature, dict):
            continue
        certificate = signature.get("certificate")
        if not isinstance(certificate, dict):
            continue
        repository = certificate.get("sourceRepository")
        owner = certificate.get("sourceRepositoryOwner")
        san = certificate.get("subjectAlternativeName")
        expected_san = f"https://github.com/{REPOSITORY}/{SIGNER_WORKFLOW.split(REPOSITORY + '/', 1)[1]}@{source_ref}"
        if repository != REPOSITORY or owner != "Rubio120":
            repository_mismatch = True
            continue
        if san != expected_san:
            signer_mismatch = True
            continue

        statement = result.get("statement")
        if not isinstance(statement, dict) or not isinstance(statement.get("subject"), list):
            continue
        for subject in statement["subject"]:
            if not isinstance(subject, dict) or subject.get("name") != bundle_name:
                continue
            digests = subject.get("digest")
            if isinstance(digests, dict) and digests.get("sha256") == digest:
                return True
            digest_mismatch = True
    if repository_mismatch:
        raise ReleaseAttestationError("verified certificate repository does not match trusted repository")
    if signer_mismatch:
        raise ReleaseAttestationError("verified certificate workflow or source ref does not match policy")
    if digest_mismatch:
        raise ReleaseAttestationError("verified attestation subject digest does not match the release bundle")
    return False


def verify_release_attestation(
    bundle_path: Path,
    expected_commit: str,
    expected_source_ref: str,
    *,
    gh_executable: str | None = None,
) -> dict[str, Any]:
    """Cryptographically verify the exact bundle digest, repository, workflow, commit and ref."""
    if not _SHA.fullmatch(expected_commit):
        raise ReleaseAttestationError("expected source commit must be a full 40-character SHA")
    if not _SOURCE_REF.fullmatch(expected_source_ref):
        raise ReleaseAttestationError("expected source ref is invalid")
    try:
        resolved_bundle = bundle_path.resolve(strict=True)
    except OSError:
        raise ReleaseAttestationError("release bundle is unavailable") from None
    if not resolved_bundle.is_file():
        raise ReleaseAttestationError("release bundle is not a regular file")
    executable = gh_executable or shutil.which("gh")
    if not executable:
        raise ReleaseAttestationError("GitHub CLI is unavailable")

    command = [
        executable,
        "attestation",
        "verify",
        str(resolved_bundle),
        "--repo",
        REPOSITORY,
        "--signer-workflow",
        SIGNER_WORKFLOW,
        "--source-digest",
        expected_commit,
        "--source-ref",
        expected_source_ref,
        "--format",
        "json",
    ]
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argument vector; values are validated policy inputs.
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except FileNotFoundError:
        raise ReleaseAttestationError("GitHub CLI is unavailable") from None
    except (OSError, subprocess.TimeoutExpired):
        raise ReleaseAttestationError("GitHub attestation verification could not be completed") from None
    if completed.returncode != 0:
        raise ReleaseAttestationError("GitHub artifact attestation verification failed")
    try:
        verified = json.loads(completed.stdout)
    except json.JSONDecodeError:
        raise ReleaseAttestationError("GitHub CLI returned invalid verification JSON") from None

    bundle_hash = hashlib.sha256()
    with resolved_bundle.open("rb") as bundle_file:
        for chunk in iter(lambda: bundle_file.read(1024 * 1024), b""):
            bundle_hash.update(chunk)
    digest = bundle_hash.hexdigest()
    if not _matching_verified_attestation(
        verified,
        bundle_name=resolved_bundle.name,
        digest=digest,
        source_ref=expected_source_ref,
    ):
        raise ReleaseAttestationError("verified certificate identity or bundle subject digest does not match policy")
    return {
        "repository": REPOSITORY,
        "workflow": SIGNER_WORKFLOW,
        "source_commit": expected_commit,
        "source_ref": expected_source_ref,
        "bundle_sha256": digest,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--expected-source-ref", required=True)
    args = parser.parse_args(argv)
    try:
        result = verify_release_attestation(args.bundle, args.expected_commit, args.expected_source_ref)
    except ReleaseAttestationError as error:
        parser.exit(1, f"release attestation failed: {error}\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
