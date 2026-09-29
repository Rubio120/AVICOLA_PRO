# Delivery 01 Technical Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` or `superpowers:executing-plans`. All behavioral code follows RED-GREEN-REFACTOR. Configuration/generated lockfiles are verified by reproducibility checks.

**Goal:** establish a reproducible FastAPI/PostgreSQL/Next.js foundation without implementing business modules.

**Architecture:** modular-monolith skeleton with hexagonal layer boundaries. FastAPI exposes technical liveness/readiness only; PostgreSQL/Alembic provide an empty baseline; Next.js renders a technical landing page and degrades safely when the backend is unavailable.

**Tech Stack:** Python 3.13, uv, FastAPI, Pydantic Settings, SQLAlchemy 2, Psycopg 3, Alembic, PostgreSQL 16, Next.js App Router, React, TypeScript, Tailwind CSS, npm, Pytest, Ruff, mypy, Vitest, ESLint.

**Spec:** `ARCHITECTURE.md`, `SECURITY.md`, `TESTING_STRATEGY.md`, and Delivery 1 in `IMPLEMENTATION_PLAN.md`.

## Global constraints

- Work only on branch `delivery/01-foundation`.
- Do not implement users, RBAC, audit persistence, production, inventory, purchasing, sales, treasury, costing, business dashboard, reports, SIFEN, or multi-company behavior.
- PostgreSQL is mandatory for integration/migration evidence; SQLite is forbidden.
- The Alembic baseline contains no business tables.
- Lockfiles and exact runtime/toolchain versions are committed.
- Backend configuration rejects non-PostgreSQL URLs and unsafe production settings.
- No secret values are committed.

---

### Task 1: Repository and toolchain foundation

**Files:** `.gitignore`, `.editorconfig`, `.gitattributes`, `.env.example`, `backend/.python-version`, `backend/pyproject.toml`, `frontend/.nvmrc`, `frontend/package.json`, `deploy/compose/docker-compose.yml`, `.github/workflows/ci.yml`, `scripts/*.ps1`.

**Produces:** pinned toolchains, project scripts, PostgreSQL 16 Compose definition, CI matrix, and reproducible dependency entry points.

- [ ] Create ignore/editor/environment contracts without secrets.
- [ ] Define backend/frontend manifests with exact toolchain policy.
- [ ] Resolve and commit `uv.lock` and `package-lock.json`.
- [ ] Add PowerShell scripts that use `$PSScriptRoot`, stop on error, and never change global policy.
- [ ] Validate Compose config and workflow syntax where tooling is available.

### Task 2: Configuration and application factory — TDD

**Tests first:** `backend/tests/unit/test_config.py`, `backend/tests/unit/test_app_factory.py`.

**Implementation:** `backend/src/avicola_pro/shared/infrastructure/config.py`, `backend/src/avicola_pro/bootstrap/app.py`, `backend/src/avicola_pro/main.py`.

**Produces:** `Settings`, `Environment`, `get_settings`, `create_app`.

- [ ] RED: local PostgreSQL configuration is accepted; invalid scheme/unknown fields/unsafe production values fail; secrets are redacted.
- [ ] GREEN: implement typed Pydantic settings and cross-field validators.
- [ ] RED: two app factory calls do not leak state.
- [ ] GREEN: implement FastAPI factory and lifespan wiring.
- [ ] Run focused tests and refactor while green.

### Task 3: Logging, correlation and Problem Details — TDD

**Tests first:** `backend/tests/unit/test_correlation.py`, `backend/tests/unit/test_problem_details.py`.

**Implementation:** `shared/infrastructure/logging.py`, `shared/api/middleware.py`, `shared/api/problem.py`, `shared/api/errors.py`.

**Produces:** bounded correlation IDs, structured stdout logs, RFC 9457 responses and safe 500 handling.

- [ ] RED: generated/propagated correlation IDs are response-scoped and bounded.
- [ ] GREEN: middleware uses contextvars and clears them in `finally`.
- [ ] RED: validation/application/HTTP/unhandled errors have expected Problem Details; secrets/tracebacks never appear.
- [ ] GREEN: add handlers and structured logging with redaction.
- [ ] Run focused tests and refactor while green.

### Task 4: PostgreSQL, health and Alembic — TDD

**Tests first:** `backend/tests/integration/test_health.py`, `backend/tests/integration/test_migrations.py`.

**Implementation:** `shared/infrastructure/database.py`, `shared/api/health.py`, `backend/alembic.ini`, `backend/migrations/*`.

**Produces:** async engine/session factory, live/ready endpoints and empty baseline migration.

- [ ] RED: liveness succeeds without DB; readiness returns 503 safely when DB fails.
- [ ] GREEN: add `/health/live` and timeout-bounded `/health/ready` using `SELECT 1`.
- [ ] RED: readiness succeeds against PostgreSQL and migration roundtrip reaches head.
- [ ] GREEN: configure SQLAlchemy/Psycopg and Alembic async environment with empty metadata.
- [ ] Run upgrade from empty DB, current=head, downgrade base, and upgrade head.

### Task 5: Module skeleton and architecture enforcement — TDD

**Tests first:** `backend/tests/architecture/test_dependency_rules.py`.

**Implementation:** package skeleton under `backend/src/avicola_pro/modules/*/{domain,application,infrastructure,api}` and shared layers.

**Produces:** all approved module boundaries without business behavior.

- [ ] RED: prove an illegal fixture import is detected.
- [ ] GREEN: implement AST/import graph rules for domain, application, cross-module infrastructure and cycles.
- [ ] Remove illegal fixture and verify the real tree passes.

### Task 6: Minimal Next.js technical UI — TDD

**Tests first:** `frontend/tests/system-status.test.tsx`, `frontend/tests/health.test.ts`, `frontend/tests/env.test.ts`.

**Implementation:** `frontend/src/app/*`, `frontend/src/components/system-status.tsx`, `frontend/src/lib/env.ts`, `frontend/src/lib/api/health.ts`.

**Produces:** accessible technical landing page and safe backend status, without business dashboard.

- [ ] RED: landing/status contract, valid/degraded health and invalid environment tests fail.
- [ ] GREEN: implement Server Component page, synchronous status component and server-only health helper.
- [ ] Verify lint, typecheck, tests and production build.

### Task 7: Clean-install and quality gate

**Files:** `README.md`, `INSTALLATION.md`, `CHANGELOG.md`, `PROJECT_STATUS.md`, evidence under `artifacts/quality/delivery-01/` when appropriate.

**Produces:** evidence that a new checkout can install, migrate, start and respond.

- [ ] Remove generated local environments/caches using safe explicit paths, then install from lockfiles.
- [ ] Start clean PostgreSQL 16, apply migrations, start backend/frontend and probe live/ready/root.
- [ ] Run backend format, lint, mypy, unit/integration/architecture tests and dependency audit.
- [ ] Run frontend lint, typecheck, tests, audit and build.
- [ ] Review dependency/configuration exposure and full diff.
- [ ] Update documentation with exact commands, versions, evidence and remaining Delivery 2 work.
- [ ] Request architecture/security/test/deployment review; fix Critical/Important findings and rerun the full gate.
- [ ] Confirm `git status`, `git diff --check`, commit only Delivery 1, and verify clean final status.

## Acceptance gate

Delivery 1 closes only when all commands above pass with fresh output, PostgreSQL 16 migrations have run from a genuinely empty database, both applications have started, `/health/live`, `/health/ready`, and `/` have returned successful responses, and independent review reports no unresolved Critical/Important issue.
