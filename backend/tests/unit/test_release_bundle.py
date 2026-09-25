from __future__ import annotations

import hashlib
import json
import sys
import tarfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.create_release_bundle import ReleaseBundleError, build_release_bundle  # noqa: E402


def _bundle_inputs(root: Path) -> None:
    (root / "images").mkdir(parents=True)
    (root / "sbom").mkdir()
    (root / "reports" / "image-security").mkdir(parents=True)
    (root / "reports" / "dependency-security").mkdir(parents=True)
    (root / "reports" / "source-security").mkdir(parents=True)
    for image in ("backend", "frontend", "backup"):
        (root / "images" / f"avicola-pro-{image}.tar").write_bytes(f"image-{image}".encode())
        (root / "sbom" / f"{image}.cdx.json").write_text(
            json.dumps({"bomFormat": "CycloneDX", "components": []}), encoding="utf-8"
        )
        (root / "reports" / "image-security" / f"{image}.sarif").write_text("{}", encoding="utf-8")
    (root / "image-metadata.json").write_text(
        json.dumps(
            {name: "sha256:" + str(index) * 64 for index, name in enumerate(("backend", "frontend", "backup"), 1)}
        ),
        encoding="utf-8",
    )
    (root / "reports" / "dependency-security" / "pip-audit.json").write_text("{}", encoding="utf-8")
    (root / "reports" / "dependency-security" / "npm-audit.json").write_text("{}", encoding="utf-8")
    (root / "reports" / "source-security" / "trivy-source.sarif").write_text("{}", encoding="utf-8")
    (root / "reports" / "compose-smoke-summary.txt").write_text("compose_smoke=passed\n", encoding="utf-8")
    (root / "reports" / "backup-restore-summary.txt").write_text(
        "Restore reconciliation passed (9 checks)\n", encoding="utf-8"
    )


def test_release_bundle_manifest_binds_images_sboms_reports_and_source(tmp_path: Path) -> None:
    root = tmp_path / "staging"
    root.mkdir()
    _bundle_inputs(root)
    output = tmp_path / "avicola-pro-release-bundle.tar"

    manifest = build_release_bundle(
        root,
        output,
        commit="a" * 40,
        source_ref="refs/heads/weekend/autonomous",
        source_event="push",
        workflow_run_id="123456",
        workflow_run_attempt="1",
    )

    assert manifest["source"]["commit"] == "a" * 40
    assert manifest["migration"]["head"] == "0014_egg_classification_reversal"
    assert manifest["gates"]["backup_restore"] == "passed"
    expected_hash = hashlib.sha256(b"image-backend").hexdigest()
    assert manifest["images"]["backend"]["archive_sha256"] == expected_hash
    assert manifest["images"]["backend"]["docker_image_id"].startswith("sha256:")
    assert manifest["sboms"]["backend"]["path"] == "sbom/backend.cdx.json"
    with tarfile.open(output) as archive:
        names = archive.getnames()
        assert "manifest.json" in names
        assert "images/avicola-pro-backup.tar" in names
        assert all(member.mtime == 0 for member in archive.getmembers())


def test_release_bundle_rejects_missing_reports_and_refuses_to_overwrite_output(tmp_path: Path) -> None:
    root = tmp_path / "staging"
    root.mkdir()
    _bundle_inputs(root)
    (root / "reports" / "backup-restore-summary.txt").unlink()
    output = tmp_path / "bundle.tar"

    with pytest.raises(ReleaseBundleError, match="backup-restore"):
        build_release_bundle(
            root,
            output,
            commit="a" * 40,
            source_ref="refs/heads/weekend/autonomous",
            source_event="push",
            workflow_run_id="123456",
            workflow_run_attempt="1",
        )

    (root / "reports" / "backup-restore-summary.txt").write_text(
        "Restore reconciliation passed (9 checks)\n", encoding="utf-8"
    )
    output.write_bytes(b"preserve existing artifact")
    with pytest.raises(ReleaseBundleError, match="new path"):
        build_release_bundle(
            root,
            output,
            commit="a" * 40,
            source_ref="refs/heads/weekend/autonomous",
            source_event="push",
            workflow_run_id="123456",
            workflow_run_attempt="1",
        )
    assert output.read_bytes() == b"preserve existing artifact"
