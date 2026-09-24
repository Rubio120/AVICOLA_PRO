from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKUP_DOCKERFILE = PROJECT_ROOT / "deploy" / "backup" / "Dockerfile"


def test_restic_binary_build_metadata_must_match_the_declared_go_toolchain() -> None:
    dockerfile = BACKUP_DOCKERFILE.read_text(encoding="utf-8")

    assert "FROM golang:1.26.8-trixie AS restic-builder" in dockerfile
    assert "ARG GO_VERSION=1.26.8" in dockerfile
    assert "ENV GOTOOLCHAIN=local" in dockerfile
    assert 'actual="$(go version | awk' in dockerfile
    assert "go version -m /out/restic" in dockerfile
    assert 'expected="go${GO_VERSION}"' in dockerfile
    assert 'grep -Fx "/out/restic: ${expected}"' in dockerfile
    assert "sid" not in dockerfile.lower()
    assert "forky" not in dockerfile.lower()
