# AVÍCOLA PRO Pilot Readiness Implementation Plan

> **For agentic workers:** Execute this plan natively in the current session, task by task. Each implementation task includes its own test cycle and review checkpoint.

**Goal:** Build and verify the repository-side deployment, encrypted backup/restore, hardening, and release evidence needed to present a pilot candidate.

**Architecture:** Produce locked multi-stage backend/frontend images behind Caddy, with PostgreSQL and app traffic isolated from public ingress. Use Restic for encrypted backups to a configurable remote repository, restore into a disposable PostgreSQL instance, reconcile business ledgers, and record evidence. Keep real remote credentials, domain, operational targets, and approval outside Git.

**Tech Stack:** Docker Compose, Caddy, PostgreSQL 16, Python 3.13/uv, Node.js 22.23.2/npm 10.9.8, Restic, GitHub Actions, pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-22-pilot-readiness-design.md`; acceptance source: `IMPLEMENTATION_PLAN.md` Entregas 11–12, `TESTING_STRATEGY.md`, `SECURITY.md`, and `INSTALLATION.md`.

## Global Constraints

- PostgreSQL 16+ remains the only integration database; SQLite is not a substitute.
- Backend Python stays `>=3.13,<3.14`; frontend Node/npm remain pinned to 22.23.2/10.9.8.
- Runtime containers use non-root users and never contain application secrets.
- PostgreSQL is private and has no host-published port in staging/production Compose.
- All security and coverage gates stay enabled; global backend coverage remains at least 80%.
- Backup evidence is valid only after encrypted transfer off-host, restore, reconciliation, and smoke/E2E checks.
- Never invent production RPO, RTO, retention, owner, approver, hostname, remote destination, or credentials.
- Do not run a production deployment or mutate a real off-host repository without its actual configuration.

## Review Focus

- Concurrent retries with the same payment key must create one payment and return it only for a byte-equivalent business request; tested in PostgreSQL by `test_supplier_payment_idempotency_reuses_identical_request_and_rejects_changed_request`.
- Missing or malformed deployment secrets must stop the container before serving traffic; test the entrypoint with absent and valid secret files.
- A database must not be reachable through a published host port; parse rendered Compose and assert the database service has no `ports` mapping.
- A wrong Restic password or altered backup must fail verification and leave the destination database untouched; test with disposable local repositories and databases.
- A restored database with drift in stock, flock, closed cash session totals, AP/AR or their allocations must fail the restore gate. Audit checks validate the schema's required validated event-shape constraints; this schema does not provide a cryptographic audit hash chain.

---

### Task 1: Complete and certify Entrega 6 payment idempotency

**Files:**
- Modify: `backend/src/avicola_pro/modules/purchasing/application/service.py`
- Modify: `backend/src/avicola_pro/modules/purchasing/api/routes.py`
- Test: `backend/tests/integration/test_purchasing_service.py`
- Evidence: `artifacts/quality/delivery-6/`

**Interfaces:**
- `PurchaseService.create_payment(session, supplier_id, amount, payment_date, payment_method_code, idempotency_key, allocations) -> (payment, replayed)`
- PostgreSQL transaction advisory lock serializes requests for the same non-empty key; the unique database constraint remains the final integrity guard.
- A replay returns the existing payment only when supplier, amount, date, method, and the complete AP allocation multiset match.

- [x] Write a PostgreSQL integration test for concurrent identical retries, changed payload rejection, multi-payment/multi-payable allocation, and the keyless path.
- [x] Run the test red against the original service and observe that `create_payment` is absent.
- [x] Implement the idempotent service operation and route through it.
- [x] Run the targeted purchasing tests, Ruff, and Mypy.
- [x] Run the complete backend suite: 159 passed, 80.30% coverage.
- [x] Save dated evidence and commit this delivery fix.

### Task 2: Build locked production images and a private service topology

**Files:**
- Create: `backend/Dockerfile`, root `.dockerignore`
- Create: `deploy/entrypoints/backend.py`
- Create: `deploy/backup/Dockerfile`, `deploy/backup/compose.backup.yml`
- Create: `frontend/Dockerfile`, `frontend/.dockerignore`
- Create: `deploy/compose/Caddyfile`, `deploy/compose/compose.production.yml`, `deploy/compose/.env.production.example`
- Modify: `frontend/next.config.ts` for standalone output
- Test: `backend/tests/unit/test_deployment_config.py` and `frontend/tests/deployment-config.test.ts`

**Interfaces:**
- Backend image starts `uvicorn avicola_pro.main:app` on the internal HTTP port and reads `AVICOLA_DATABASE_URL` and `AVICOLA_SESSION_HMAC_KEY` from mounted secret files at runtime.
- Frontend image runs Next.js standalone and reads `BACKEND_INTERNAL_URL` on the internal network.
- Caddy terminates TLS for the externally supplied `APP_DOMAIN`; only Caddy publishes ports 80/443 and routes all requests through the Next.js frontend/BFF, which forwards allowed APIs over the private app network.
- PostgreSQL is reachable only on Compose's private network. A one-shot migration service must succeed before backend traffic is admitted.

- [x] Add tests that reject secret absence and confirm valid secret files are exported without printing their contents.
- [x] Add multi-stage backend/frontend Dockerfiles from lockfiles; create fixed non-root runtime users and health checks. Add a version-pinned PostgreSQL/Restic backup image with a non-root user.
- [x] Add Caddy TLS routing to the frontend/BFF; disable server/version headers where supported.
- [x] Add production Compose networks, health dependencies, read-only root filesystems where compatible, dropped capabilities, resource settings, restart policies, external secret mounts, and isolated backup egress.
- [x] Add Compose structure/render checks that prove only the proxy has published ports and that PostgreSQL remains private.
- [ ] Run Docker build, container user checks, smoke tests, and image scan when Docker/registry access is available.

### Task 3: Add encrypted backup, isolated restore, and business reconciliation

**Files:**
- Create: `deploy/backup/backup.py`, `deploy/backup/restore.py`, `deploy/backup/verify_restore.py`, `deploy/backup/db_connection.py`
- Create: `deploy/backup/Dockerfile`, `deploy/backup/compose.backup.yml`
- Test: `backend/tests/unit/test_backup_restore.py`, `backend/tests/unit/test_deployment_config.py`
- Evidence: `artifacts/quality/delivery-11/backup-restore/`

**Interfaces:**
- Backup consumes mounted files for the database URL, Restic repository locator, and Restic password, plus a non-secret `BACKUP_TAG`; repository credentials are provided by the host or secret manager.
- Backup streams a custom-format `pg_dump` into an encrypted Restic snapshot, verifies repository integrity, and emits only snapshot ID, timestamp, and exit status.
- Restore requires a full snapshot ID and a target named `avicola_restore_*`; it rejects the source database and a target containing user tables, verifies the Restic repository and archive before touching the target, applies no schema downgrade, and runs `verify_restore.py`.
- Retention pruning is not enabled until approved retention values are supplied.

- [x] Add unit coverage for restore success/failure behavior, every reconciliation rejecting controlled drift, safe URL handling, and invalid/source/ambiguous targets; verify local encrypted Restic round-trip, wrong-password rejection, and corruption detection. Evidence is local-only, not off-host acceptance.
- [x] Add Python backup/restore/initialization scripts with timeouts, secret redaction, service files outside argv, exit-code propagation, and cleanup.
- [x] Implement schema-backed checks for inventory, flock events, closed treasury sessions, AP/AR balances and allocations, and validated audit/security shape constraints. `OTHER` bird movements fail closed; this schema has no audit hash chain.
- [x] Add unit fixtures that prove each reconciliation rejects controlled drift.
- [x] Verify a local encrypted PostgreSQL round trip, wrong-password rejection, and corruption detection on an isolated repository copy; document explicitly that this is not off-host acceptance evidence.
- [ ] Run the same process with a real off-host repository only after its credentials/destination are configured; preserve restore log, snapshot ID, hash, observed RPO/RTO, owner, and approver without secrets.

### Task 4: Add operational runbooks, smoke/load checks, and CI supply-chain gates

**Files:**
- Create: `deploy/runbooks/install.md`, `deploy/runbooks/deploy.md`, `deploy/runbooks/rollback.md`, `deploy/runbooks/incident.md`, `deploy/runbooks/restore.md`
- Create: `deploy/performance/smoke.js`
- Modify: `.github/workflows/ci.yml`, `INSTALLATION.md`, `SECURITY.md`, `TESTING_STRATEGY.md`
- Evidence: `artifacts/quality/delivery-11/`

**Interfaces:**
- Runbooks use the Compose project and documented environment variable names; destructive operations require an explicit disposable target and backup verification.
- Smoke/load scenario uses only synthetic data and a configurable base URL; it records p50/p95/error rate and enforces the documented p95 budget only after the pilot volume is approved.
- CI runs locked builds, backend/frontend tests, migrations, dependency checks, secret scanning, static security analysis, image scanning, and Compose validation.

- [x] Add runbook checks for operational preconditions, restore-target permissions, secret-safe procedures, and restoration safeguards.
- [x] Add a configurable health/load smoke and optional synthetic login/me/logout path. Staging execution remains open.
- [x] Configure dependency and secret checks in CI; pin Trivy to its immutable `v0.36.0` release. Remote execution remains pending.
- [x] Configure backend/frontend/backup builds and image SARIF scans in CI; fail on critical/high findings. Remote execution remains pending.
- [x] Correct integration CI so application and test database URLs are distinct; assert this before migrations/tests.
- [ ] Execute deployment, rollback, incident, and restore runbooks in disposable staging and save dated evidence.

### Task 5: Certify Entrega 12 and leave the pilot decision package

**Files:**
- Create: `scripts/release-gate.ps1`, `scripts/release-gate.sh`
- Create: `artifacts/quality/delivery-12/README.md`
- Modify: `PROJECT_STATUS.md`, `PROJECT_CONTEXT.md`, `CHANGELOG.md`
- Modify: `frontend/src/app/api/[...path]/route.ts` to allow the existing treasury, costing, and reporting UI endpoints through the BFF.
- Test: `frontend/tests/bff-proxy.test.ts`

**Interfaces:**
- Release gate consumes the exact release tag, PostgreSQL URLs, deployment domain, scanner outputs, and restore evidence; it exits non-zero for missing or stale evidence.
- The report names the tested commit and image digests, suite results, migration head, restore snapshot/hash, reconciliation results, and open findings.
- An RC can be marked technically ready while the pilot status remains blocked until actual off-host restore evidence and named operational approvals exist.

- [x] Add tests that reject absent/mismatched commit/tag, wrong trusted Alembic head, missing/invalid/stale scan output, failed restore evidence, unapproved RPO/RTO, unbound build/digests, and critical/high findings.
- [x] Add RC/pilot gate CLI and PowerShell/Linux wrappers; current RC output reports only `manifest_validated`, and pilot fails closed pending trusted provenance configuration.
- [x] Add the D12 decision-package guide without manufacturing project evidence.
- [x] Run clean database install and previous-version migration locally on synthetic PostgreSQL 16.14 databases; run local API/frontend production smoke and dependency audits. Evidence: `artifacts/quality/delivery-11/local-validation-2026-09-22.md`. Built-runtime health smoke: 20 requests, concurrency 2, 0 errors, warm p50 30 ms/p95 75 ms; cold-start p95 769 ms. Separate authenticated smoke on a fresh disposable DB passed initial-admin bootstrap, required password change, and BFF login/me/logout: 20 requests, 0 errors, p50 29 ms/p95 78 ms; DB and listeners were removed/verified. No p95 budget is approved. Fresh local gates: backend 199/199 (80.34% branches); frontend 47/47 (87.79% statements, 80.26% branches); focused D12 tests 23/23.
- [ ] Run Docker image builds/user checks, image scans, full remote CI, and deployment/rollback/incident/restore runbooks in staging; Docker is unavailable locally and remote/staging results are not yet present.
- [x] Implement common durable `authorization.denied` events for operational-module 403 responses; tests verify the actor, permission, resource, correlation, and unchanged 403 response.
- [ ] Obtain a business-owner review of the role/permission matrix; no business authorization assumptions are inferred.
- [x] Complete independent review of the D11/D12 working diff and fix the critical/important findings: bind backup image digest to build evidence and persist operational authorization denials. A minor BFF path-prefix boundary suggestion remains deferred. Do not attach acceptance evidence until remote CI and trusted commit/image provenance are present.
- [x] Update status/context/changelog with precise outcomes and distinguish local evidence from off-host/operational approvals.
- [ ] Create the release candidate commit and tag only if every technical gate is green; leave production deployment and pilot activation pending until the external acceptance conditions are met.

## Deferred acceptance decisions

The following values require the project's owner/approver and cannot be inferred from code: RPO, RTO, retention, named service owner, named approver, public hostname/contact, off-host backup provider/repository, target pilot workload, and release activation date. Local development can prepare all interfaces and tests; Entregas 11–12 remain operationally open until those real values and external evidence are recorded.
