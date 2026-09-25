# Entrega 9 — Costos y rentabilidad Implementation Plan

> **For agentic workers:** Execute this plan task-by-task with TDD. No Git commit is created by this autonomous run.

**Goal:** Implement auditable, versioned costing and profitability over confirmed operational events without coupling producer modules to `costing`.

**Architecture:** The costing module owns append-only cost events, cost centers, allocations, versioned runs, batch snapshots, and profitability queries. Producers expose neutral persisted facts through foreign-key-free source references; costing snapshots only confirmed facts and never mutates inventory, production, purchasing, sales, or treasury.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, Alembic, PostgreSQL 16+, Next.js/React/TypeScript, Pytest.

**Spec:** `IMPLEMENTATION_PLAN.md`, `ARCHITECTURE.md`, `DATABASE.md`, `SECURITY.md`, `TESTING_STRATEGY.md`.

## Global Constraints

- PostgreSQL real only; no SQLite substitute.
- PYG and `Decimal`/`numeric`; no floating-point money.
- Confirmed facts are immutable; corrections are compensating events.
- Costing consumes neutral contracts and does not import producer application services.
- Closed costing runs are immutable and reproducible.
- Every protected mutation requires session, CSRF, RBAC, idempotency where applicable, and audit.

## Review Focus

- Zero denominator for per-bird cost must return an explicit unavailable state, never divide by zero.
- Allocation rounding must leave no residual cost; the final allocation receives the residual centavo.
- Late events must not silently alter a closed run; they require a new version.
- Duplicate source event/idempotency keys must not double-count cost.
- Profitability must exclude draft/reversed documents and unpublished costing runs.

### Task 1: Domain rules and failing tests

**Files:** `backend/tests/unit/test_delivery9_rules.py`, `backend/src/avicola_pro/modules/costing/domain/rules.py`

- [ ] Add tests for allocation conservation, weighted allocation, zero denominator, run state transitions, and confirmed-source filtering.
- [ ] Run the focused tests and observe the expected missing-symbol failures.
- [ ] Implement minimal pure rules using `Decimal`.
- [ ] Re-run focused tests and refactor only after green.

### Task 2: PostgreSQL models and migration

**Files:** `backend/src/avicola_pro/modules/costing/infrastructure/models.py`, `backend/src/avicola_pro/shared/infrastructure/models.py`, `backend/migrations/versions/0010_costing.py`, `backend/tests/integration/test_migrations.py`

- [ ] Add tables for `cost_centers`, `cost_events`, `cost_allocations`, `cost_runs`, `cost_run_snapshots`, and `profitability_snapshots` with checks, unique idempotency keys, append-only status constraints, and indexes.
- [ ] Register models and add `0010_costing` with downgrade.
- [ ] Test clean upgrade, downgrade/upgrade roundtrip, constraints, and metadata drift against real PostgreSQL.

### Task 3: Application service and integration tests

**Files:** `backend/src/avicola_pro/modules/costing/application/service.py`, `backend/tests/integration/test_costing_service.py`

- [ ] Implement event ingestion, weighted allocation, run creation/closure, snapshotting, reproducibility, and profitability calculation from confirmed source facts supplied as neutral dictionaries.
- [ ] Enforce idempotency and reject closed-run mutation or duplicate allocation.
- [ ] Test golden datasets, late events, zero birds, negative/invalid values, and audit-safe immutability.

### Task 4: Protected API and permissions

**Files:** `backend/src/avicola_pro/modules/costing/api/routes.py`, `backend/src/avicola_pro/bootstrap/app.py`, `backend/src/avicola_pro/modules/identity/infrastructure/seed.py`, `backend/tests/unit/test_costing_routes.py`

- [ ] Add protected endpoints for cost centers, event ingestion, run calculation/closure, and profitability read.
- [ ] Use existing session/CSRF/RBAC/audit patterns and dedicated `costs.recalculate` / `reports.profitability.read` permissions.
- [ ] Test 401/403, malformed payloads, audit calls, and no producer-module imports.

### Task 5: Frontend and frontend tests

**Files:** `frontend/src/components/costing-panel.tsx`, `frontend/src/app/page.tsx`, `frontend/tests/costing.test.tsx`

- [ ] Add a safe costing/profitability panel through the same-origin BFF, with loading/empty/error states and explicit run status.
- [ ] Add component tests; if Vitest hits the known sandbox-only esbuild `PermissionError`, retain the correct tests and run available ESLint/TypeScript/build gates.

### Task 6: Gates and documentation

- [ ] Run focused and complete backend tests with coverage, Ruff/format, mypy, clean migration and health checks on PostgreSQL 16 at `127.0.0.1:55432`.
- [ ] Run frontend tests, ESLint, TypeScript, build, dependency/security scans, and independent review.
- [ ] Update `PROJECT_STATUS.md` and `PROJECT_CONTEXT.md` only after all available gates pass; do not begin Delivery 10.
