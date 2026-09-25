"""Create a deterministic, non-secret release evidence bundle from CI artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path
from typing import Any

_SHA = re.compile(r"[0-9a-f]{40}\Z")
_SOURCE_REF = re.compile(r"refs/(?:heads|tags)/[A-Za-z0-9._/-]+\Z")
_IMAGE_NAMES = ("backend", "frontend", "backup")
_REQUIRED_REPORTS = (
    "reports/compose-smoke-summary.txt",
    "reports/backup-restore-summary.txt",
    "reports/source-security/trivy-source.sarif",
    "reports/dependency-security/pip-audit.json",
    "reports/dependency-security/npm-audit.json",
    *(f"reports/image-security/{name}.sarif" for name in _IMAGE_NAMES),
)


class ReleaseBundleError(ValueError):
    """Release inputs are incomplete, inconsistent, or not safe to package."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_stream:
        for chunk in iter(lambda: file_stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path, label: str) -> Any:
    try:
        with path.open(encoding="utf-8") as file_stream:
            return json.load(file_stream)
    except (OSError, json.JSONDecodeError):
        raise ReleaseBundleError(f"{label} is missing or invalid JSON") from None


def build_release_bundle(
    root: Path,
    output: Path,
    *,
    commit: str,
    source_ref: str,
    source_event: str,
    workflow_run_id: str,
    workflow_run_attempt: str,
) -> dict[str, Any]:
    """Validate CI evidence, write a stable manifest, and create a normalized tar archive."""
    if not _SHA.fullmatch(commit) or not _SOURCE_REF.fullmatch(source_ref) or source_event != "push":
        raise ReleaseBundleError("release source identity is invalid or not an allowed push ref")
    if not workflow_run_id.isdecimal() or not workflow_run_attempt.isdecimal():
        raise ReleaseBundleError("workflow run identity is invalid")
    try:
        bundle_root = root.resolve(strict=True)
    except OSError:
        raise ReleaseBundleError("release evidence staging directory is unavailable") from None
    if not bundle_root.is_dir():
        raise ReleaseBundleError("release evidence root is not a directory")
    output_path = output.resolve()
    if output_path.exists() or output_path.is_relative_to(bundle_root):
        raise ReleaseBundleError("bundle output must be a new path outside the staging directory")
    manifest_path = bundle_root / "manifest.json"
    if manifest_path.exists():
        raise ReleaseBundleError("staging directory already contains a manifest")

    metadata = _read_json(bundle_root / "image-metadata.json", "image metadata")
    if not isinstance(metadata, dict):
        raise ReleaseBundleError("image metadata must be a JSON object")
    images: dict[str, dict[str, str]] = {}
    sboms: dict[str, dict[str, str]] = {}
    for name in _IMAGE_NAMES:
        archive_path = bundle_root / "images" / f"avicola-pro-{name}.tar"
        sbom_path = bundle_root / "sbom" / f"{name}.cdx.json"
        if not archive_path.is_file() or not sbom_path.is_file():
            raise ReleaseBundleError(f"{name} image archive or SBOM is missing")
        image_id = metadata.get(name)
        if not isinstance(image_id, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
            raise ReleaseBundleError(f"{name} Docker image ID is missing or invalid")
        sbom = _read_json(sbom_path, f"{name} SBOM")
        if not isinstance(sbom, dict) or sbom.get("bomFormat") != "CycloneDX":
            raise ReleaseBundleError(f"{name} SBOM is not CycloneDX")
        images[name] = {
            "archive_path": archive_path.relative_to(bundle_root).as_posix(),
            "archive_sha256": _sha256(archive_path),
            "docker_image_id": image_id,
        }
        sboms[name] = {
            "path": sbom_path.relative_to(bundle_root).as_posix(),
            "sha256": _sha256(sbom_path),
        }

    reports: dict[str, dict[str, str]] = {}
    for relative_name in _REQUIRED_REPORTS:
        report_path = bundle_root / relative_name
        if not report_path.is_file():
            raise ReleaseBundleError(f"required evidence report is missing: {relative_name}")
        if report_path.suffix in {".json", ".sarif"}:
            _read_json(report_path, relative_name)
        reports[relative_name] = {"sha256": _sha256(report_path)}
    smoke_summary = (bundle_root / "reports/compose-smoke-summary.txt").read_text(encoding="utf-8")
    restore_summary = (bundle_root / "reports/backup-restore-summary.txt").read_text(encoding="utf-8")
    if "compose_smoke=passed" not in smoke_summary:
        raise ReleaseBundleError("authenticated Compose smoke report is not passed")
    if "Restore reconciliation passed (9 checks)" not in restore_summary:
        raise ReleaseBundleError("backup-restore report does not confirm nine reconciliations")

    manifest: dict[str, Any] = {
        "format_version": 1,
        "repository": "Rubio120/AVICOLA_PRO",
        "workflow": {
            "path": ".github/workflows/ci.yml",
            "run_id": workflow_run_id,
            "run_attempt": workflow_run_attempt,
            "event": source_event,
        },
        "source": {"commit": commit, "ref": source_ref},
        "migration": {"head": "0014_egg_classification_reversal"},
        "gates": {
            "windows_toolchains": "passed",
            "postgresql_integration": "passed",
            "dependency_security": "passed",
            "source_security": "passed",
            "image_security": "passed",
            "compose_topology": "passed",
            "compose_smoke": "passed",
            "backup_restore": "passed",
        },
        "images": images,
        "sboms": sboms,
        "reports": reports,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    files: list[Path] = []
    for path in sorted(bundle_root.rglob("*")):
        if path.is_symlink():
            manifest_path.unlink()
            raise ReleaseBundleError("symbolic links are not permitted in the release bundle")
        if path.is_file():
            files.append(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(output_path, mode="x") as bundle:
            for path in files:
                relative_name = path.relative_to(bundle_root).as_posix()
                info = tarfile.TarInfo(relative_name)
                info.size = path.stat().st_size
                info.mode = 0o644
                info.mtime = 0
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                with path.open("rb") as file_stream:
                    bundle.addfile(info, file_stream)
    except (OSError, tarfile.TarError):
        manifest_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)
        raise ReleaseBundleError("release bundle could not be created") from None
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--source-event", required=True)
    parser.add_argument("--workflow-run-id", required=True)
    parser.add_argument("--workflow-run-attempt", required=True)
    args = parser.parse_args(argv)
    try:
        manifest = build_release_bundle(
            args.root,
            args.output,
            commit=args.commit,
            source_ref=args.source_ref,
            source_event=args.source_event,
            workflow_run_id=args.workflow_run_id,
            workflow_run_attempt=args.workflow_run_attempt,
        )
    except (OSError, ReleaseBundleError) as error:
        parser.exit(1, f"release bundle failed: {error}\n")
    print(f"Release evidence bundle created for {manifest['source']['commit']} ({len(manifest['reports'])} reports)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
