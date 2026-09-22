# AVÍCOLA PRO Pilot Readiness Implementation Plan

> **For agentic workers:** Execute this plan natively in the current session, task by task. Each implementation task includes its own test cycle and review checkpoint.

**Goal:** Build and verify the repository-side deployment, encrypted backup/restore, hardening, and release evidence needed to present a pilot candidate.

**Architecture:** Produce locked multi-stage backend/frontend images behind Caddy, with PostgreSQL and app traffic isolated from public ingress. Use Restic for encrypted backups to a configurable remote repository, restore into a disposable PostgreSQL instance, reconcile business ledgers, and record evidence. Keep real remote credentials, domain, operational targets, and approval outside Git.

**Tech Stack:** Docker Compose, Caddy, PostgreSQL 16, Python 3.13/uv, Node.js 22.23.2/npm 10.9.8, Restic, Bash, GitHub Actions, pytest, Vitest.

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
- A restored database with drift in stock, flock, cash, AP/AR, or audit integrity must fail the restore gate; test each invariant with synthetic fixtures.

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
- Create: `backend/Dockerfile`, `backend/.dockerignore`
- Create: `frontend/Dockerfile`, `frontend/.dockerignore`
- Create: `deploy/compose/Caddyfile`, `deploy/compose/compose.production.yml`, `deploy/compose/.env.production.example`
- Modify: `frontend/next.config.ts` for standalone output
- Test: `backend/tests/unit/test_deployment_config.py` and `frontend/tests/deployment-config.test.ts`

**Interfaces:**
- Backend image starts `uvicorn avicola_pro.main:app` on the internal HTTP port and reads `AVICOLA_DATABASE_URL` and `AVICOLA_SESSION_HMAC_KEY` from mounted secret files at runtime.
- Frontend image runs Next.js standalone and reads `BACKEND_INTERNAL_URL` on the internal network.
- Caddy terminates TLS for the externally supplied `APP_DOMAIN`; only Caddy publishes ports 80/443.
- PostgreSQL is reachable only on Compose's private network. A one-shot migration service must succeed before backend traffic is admitted.

- [ ] Add tests that reject secret absence and confirm valid secret files are exported without printing their contents.
- [ ] Add multi-stage Dockerfiles from lockfiles; create fixed non-root runtime users and health checks.
- [ ] Add Caddy TLS routing for `/api/*` to backend and remaining requests to frontend; disable server/version headers where supported.
- [ ] Add production Compose networks, health dependencies, read-only root filesystems where compatible, dropped capabilities, resource settings, restart policies, and external secret file mounts.
- [ ] Add Compose rendering checks that prove only the proxy has published ports and that no secret value enters rendered service commands or image build args.
- [ ] Run Docker build, container user checks, smoke tests, and image scan when Docker/registry access is available.

### Task 3: Add encrypted backup, isolated restore, and business reconciliation

**Files:**
- Create: `deploy/backup/backup.sh`, `deploy/backup/restore.sh`, `deploy/backup/verify_restore.py`
- Create: `deploy/backup/Dockerfile`, `deploy/backup/compose.backup.yml`
- Test: `backend/tests/integration/test_backup_restore.py`
- Evidence: `artifacts/quality/delivery-11/backup-restore/`

**Interfaces:**
- Backup consumes `AVICOLA_DATABASE_URL`, `RESTIC_REPOSITORY`, `RESTIC_PASSWORD_FILE`, and `BACKUP_TAG`; repository credentials are provided by the host or secret manager.
- Backup streams a custom-format `pg_dump` into an encrypted Restic snapshot, verifies repository integrity, and emits only snapshot ID, timestamp, and exit status.
- Restore requires an explicitly named disposable target database, restores the selected snapshot, applies no schema downgrade, and runs `verify_restore.py` plus health/smoke checks.
- Retention pruning is not enabled until approved retention values are supplied.

- [ ] Write tests for successful encrypted snapshot/restore in a temporary local repository, wrong password, corrupted repository, and an invalid target that refuses to restore.
- [ ] Add backup/restore scripts with strict shell modes, traps, cleanup, exit-code propagation, and no password or URL logging.
- [ ] Implement reconciliation queries from the schema: inventory balance versus append-only stock ledger; flock balances versus production events; treasury balances versus cash movements; AP/AR original, applied and outstanding sums; audit hash-chain verification.
- [ ] Add CI fixtures that prove each reconciliation rejects one controlled inconsistency.
- [ ] Verify a local encrypted round trip and document that it is not off-host acceptance evidence.
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

- [ ] Add runbook checks for command presence, required preconditions, secret redaction, and restoration safeguards.
- [ ] Add a non-mutating health smoke and a synthetic authenticated critical-path scenario against staging.
- [ ] Run dependency and secret checks in CI; pin any new scanner action/image to a verified immutable release reference.
- [ ] Build and scan backend/frontend/backup images in CI with published SARIF or machine-readable output and fail on critical/high findings.
- [ ] Correct integration CI so application and test database URLs are distinct; assert this before migrations/tests.
- [ ] Execute deployment, rollback, incident, and restore runbooks in disposable staging and save dated evidence.

### Task 5: Certify Entrega 12 and leave the pilot decision package

**Files:**
- Create: `scripts/release-gate.ps1`, `scripts/release-gate.sh`
- Create: `artifacts/quality/delivery-12/README.md`
- Modify: `PROJECT_STATUS.md`, `PROJECT_CONTEXT.md`, `CHANGELOG.md`

**Interfaces:**
- Release gate consumes the exact release tag, PostgreSQL URLs, deployment domain, scanner outputs, and restore evidence; it exits non-zero for missing or stale evidence.
- The report names the tested commit and image digests, suite results, migration head, restore snapshot/hash, reconciliation results, and open findings.
- An RC can be marked technically ready while the pilot status remains blocked until actual off-host restore evidence and named operational approvals exist.

- [ ] Add tests that reject an absent commit identity, wrong Alembic head, missing scan report, failed restore evidence, unapproved RPO/RTO, and critical/high findings.
- [ ] Run clean install, previous-version upgrade, complete backend/frontend gates, Docker builds, smoke/load tests, and all security scans.
- [ ] Review RBAC permissions and audit event coverage manually and attach evidence by exact commit/image digest.
- [ ] Have an independent comprehensive review of the final diff and resolve critical/high findings.
- [ ] Update status/context/changelog with precise outcomes and distinguish local evidence from off-host/operational approvals.
- [ ] Create the release candidate commit and tag only if every technical gate is green; leave production deployment and pilot activation pending until the external acceptance conditions are met.

## Deferred acceptance decisions

The following values require the project's owner/approver and cannot be inferred from code: RPO, RTO, retention, named service owner, named approver, public hostname/contact, off-host backup provider/repository, target pilot workload, and release activation date. Local development can prepare all interfaces and tests; Entregas 11–12 remain operationally open until those real values and external evidence are recorded.
