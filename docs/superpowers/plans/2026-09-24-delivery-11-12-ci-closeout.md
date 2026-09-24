# D11/D12 CI Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task after plan approval and method selection.

**Goal:** Make D11/D12's image-build, security, authenticated Compose, encrypted backup/restore, release bundle and provenance gate pass for the exact candidate commit.

**Architecture:** Keep fail-closed image scans and existing CI topology. The current failure is Restic's upstream `TestScannerError/unreadable-dir`: the builder runs as root, so chmod-restricted test fixtures remain readable. Run Restic tests as a dedicated unprivileged builder user; skip only the FUSE-dependent `TestMount` test in the container build.

**Tech Stack:** Docker BuildKit, Debian Trixie Go builder, Restic 0.19.1 pinned commit, Python, Docker Compose, GitHub Actions, Trivy, CycloneDX/SARIF, GitHub attestations.

**Spec:** `docs/superpowers/specs/2026-09-23-functional-parity-design.md`

## Global Constraints

- Preserve existing worktree changes; do not reset or overwrite them.
- Permission-denial tests must run without root DAC bypass; do not keep broad test exclusions.
- Keep all runtime image scans fail-closed at HIGH/CRITICAL and preserve SARIF artifacts.
- Do not publish image tags or deploy; release bundle is an offline candidate only.
- Do not claim D11/D12 closed when any required job is skipped or the bundle/attestation gate is absent.

## Review Focus

- Root can read mode-000 files; the Dockerfile test must prove the Restic suite runs as a non-root UID.
- The build container may lack `/dev/fuse`; skip only `TestMount`, not scanner or unreadable-file tests.
- Go cache/source ownership must allow the test UID to write without making the final runtime image writable.
- Any image scan failure must prevent release bundle creation; assert workflow dependencies remain fail-closed.
- The release gate must bind bundle digest, reports, image IDs, SBOM, commit/ref and transparency evidence to one run.

---

### Task 1: Pin the builder privilege regression

**Files:**
- Modify: `backend/tests/unit/test_deployment_config.py`
- Test: `backend/tests/unit/test_deployment_config.py`

**Interfaces:**
- Consumes: current backup Dockerfile and deployment workflow text.
- Produces: regression assertions that permission-sensitive upstream tests are not skipped and the test RUN executes as a non-root UID.

- [ ] Add `test_restic_builder_runs_permission_tests_as_unprivileged_user` asserting the builder declares a dedicated test UID before `go test`, the test command skips only `TestMount`, then returns to root only for final artifact build.
- [ ] Run `uv run pytest tests/unit/test_deployment_config.py::test_restic_builder_runs_permission_tests_as_unprivileged_user -q` from `backend/`; verify it fails against the current Dockerfile because it skips permission tests and remains root.
- [ ] Keep assertions about observable Dockerfile behavior; do not assert comment wording or whitespace.

### Task 2: Run the Restic suite without root permission bypass

**Files:**
- Modify: `deploy/backup/Dockerfile`
- Test: `backend/tests/unit/test_deployment_config.py`

**Interfaces:**
- Consumes: pinned Restic source and test suite from Task 1.
- Produces: a test stage running `go test ./... -skip 'TestMount'` as dedicated UID/GID `10003:10003`; final `/out/restic` remains built by root and copied into the non-root runtime image as before.

- [ ] Create the builder test user/group, ensure `/src/restic` and `/tmp/go-build-cache` are writable by it, and set Docker `USER 10003:10003` for the Go test RUN only.
- [ ] Run all Restic tests except `TestMount`; do not skip `TestScannerError`, `TestArchiverErrorReporting`, or unreadable file/directory cases.
- [ ] Restore `USER root` before `go build`, keeping final runtime `USER 10002:10002` unchanged.
- [ ] Run the focused deployment-config test and `uv run pytest tests/unit/test_deployment_config.py -q`; verify both pass.
- [ ] Build the backup image with BuildKit and verify the image user remains `10002:10002`; inspect build logs to confirm the upstream permission tests execute rather than skip.

### Task 3: Complete exact-SHA CI and RC verification

**Files:**
- Modify only if evidence requires: `.github/workflows/ci.yml`, `scripts/release-gate.ps1`, `scripts/release-gate.sh`, associated tests.
- Update after success: `PROJECT_STATUS.md`, `PROJECT_CONTEXT.md`, `artifacts/quality/delivery-11/README.md`, `artifacts/quality/delivery-12/README.md`.

**Interfaces:**
- Consumes: verified non-root builder and existing CI gates.
- Produces: full green workflow run, synthetic Compose and Restic artifacts, release tar/attestation and a passing verifier for the same SHA.

- [ ] Run workflow on the reviewed candidate SHA; do not rerun only failed jobs if prior jobs' outputs are required for one complete run.
- [ ] Inspect every job: Windows, PostgreSQL, dependency/source audits, three image scans, Compose/authenticated smoke, backup/restore, bundle and attestation verification. Require success, not skipped.
- [ ] If runtime scans report HIGH/CRITICAL, remediate the affected locked base/package versions in a separate TDD change and rerun all required gates; never weaken thresholds.
- [ ] Download the release artifact from that successful run and execute the local RC gate with exact repo, workflow, ref, commit, tag and migration head; retain machine-readable report.
- [ ] Update status docs with run ID/SHA/artifact evidence and explicit off-host/staging/RPO/RTO limitations; run `git diff --check` and review the exact file list.
