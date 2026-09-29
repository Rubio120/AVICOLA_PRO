# Entrega 5 - Producción avícola Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement auditable flock balances and production operations for mortality, adjustments, daily observations, and feed consumption.

**Architecture:** Add a PostgreSQL-owned `production` module with pure Decimal/domain rules, SQLAlchemy persistence, an application service coordinating one transaction, protected FastAPI routes, and a small frontend panel. Feed consumption calls the existing inventory application service through its public method and stores a production snapshot.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, Alembic, PostgreSQL 16, Pydantic v2, Next.js/React/TypeScript.

**Spec:** `DATABASE.md`, `ARCHITECTURE.md`, `SECURITY.md`, `TESTING_STRATEGY.md`, and Delivery 5 in `IMPLEMENTATION_PLAN.md`.

## Global Constraints

- Birds are quantities by flock, never individual records.
- Confirmed production events are immutable and corrections are compensating events.
- Live birds may never be negative; house capacity and active assignment periods are enforced under lock.
- PostgreSQL is the integration database; SQLite is forbidden.
- All mutations require session, CSRF, granular RBAC, transaction and functional audit.

## Review Focus

- Duplicate activation must create exactly one INITIAL event.
- Concurrent mortality/adjustment must never make a flock negative.
- House assignment must reject capacity overflow and overlapping periods.
- Closing a flock must reject non-zero balance unless an authorized adjustment is recorded.
- Feed consumption must not persist when the inventory issue rolls back.

### Task 1: Domain rules and persistence schema

**Files:**
- Create: `backend/src/avicola_pro/modules/production/domain/rules.py`
- Create: `backend/src/avicola_pro/modules/production/infrastructure/models.py`
- Modify: `backend/src/avicola_pro/shared/infrastructure/models.py`
- Create: `backend/migrations/versions/0005_production.py`
- Modify: `backend/src/avicola_pro/modules/identity/infrastructure/seed.py`
- Test: `backend/tests/unit/test_delivery5_rules.py`

Write failing Decimal and state tests, then implement quantized balance transitions, capacity validation, close validation, models, migration and permissions.

### Task 2: Application service and PostgreSQL integration

**Files:**
- Create: `backend/src/avicola_pro/modules/production/application/service.py`
- Test: `backend/tests/integration/test_production_service.py`

Implement activation, house assignment, mortality, authorized corrections, daily records, flock close, and feed consumption using row locks, append-only production events and the inventory service for feed issues. Cover migration, idempotency, rollback, immutability and negative-balance rejection.

### Task 3: Protected API and frontend

**Files:**
- Create: `backend/src/avicola_pro/modules/production/api/routes.py`
- Modify: `backend/src/avicola_pro/bootstrap/app.py`
- Create: `frontend/src/components/production-panel.tsx`
- Modify: `frontend/src/app/page.tsx`
- Test: `backend/tests/unit/test_production_routes.py`, `frontend/tests/production.test.tsx`

Expose strict DTOs and permission checks for flock operations, mortality, feed and read balances; add a minimal operational panel with safe empty/loading/error states.

### Task 4: Gates and documentation

Run focused and full backend tests, coverage, Ruff/format, Mypy, PostgreSQL clean migration/roundtrip and health checks; run frontend tests where possible plus ESLint, TypeScript and build; perform security and independent review; update `PROJECT_STATUS.md` and `PROJECT_CONTEXT.md` only after fresh evidence.
