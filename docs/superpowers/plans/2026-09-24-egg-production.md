# Daily Egg Production Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task after plan approval and method selection.

**Goal:** Record traceable daily egg quantities by flock and house through the existing production module.

**Architecture:** Add production-owned append-only daily egg facts, secure FastAPI endpoints and minimal controls in the current production panel. Do not couple production writes directly to inventory tables; a later inventory plan coordinates stock posting through existing application/UnitOfWork patterns.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL 16, Next.js/React/TypeScript.

**Spec:** `docs/superpowers/specs/2026-09-23-functional-parity-design.md`

## Global Constraints

- Preserve FastAPI/PostgreSQL/Next.js and existing UI style.
- One company with multiple farms remains the supported organization model.
- Confirmed facts are auditable and corrections are compensating, never silent overwrites.
- Use session, CSRF, backend RBAC, audit, idempotency, correlation and transaction patterns already present.
- No category, package conversion, historical data or formula may be fabricated.

## Review Focus

- A daily record must reference a valid flock and the house assignment active on the recorded date.
- Count inputs must be whole eggs, within database/API precision, and accept zero only if business policy approves it.
- Repeating an idempotency key must return the prior result without duplicate rows or audit actions.
- A correction/reversal must preserve the original fact and not create negative production.
- Unauthorized, missing-CSRF, stale/closed-flock and invalid-house requests must leave no partial data.

---

### Task 1: Define and test egg-record domain rules

**Files:**
- Create: `backend/tests/unit/test_delivery13_egg_production_rules.py`
- Create: `backend/src/avicola_pro/modules/production/domain/egg_rules.py`

**Interfaces:**
- Produces: `validate_egg_count(count: int) -> None` and a pure validator for correction quantities/status rules.

- [ ] Write tests for valid positive integer, approved zero behavior, negative, fractional, and over-limit counts.
- [ ] Run `uv run pytest tests/unit/test_delivery13_egg_production_rules.py -q` from `backend/`; expect import/validation failures.
- [ ] Implement pure Decimal/integer-safe validation with stable domain exceptions; do not put SQL or HTTP logic in the domain.
- [ ] Rerun the focused tests and `uv run ruff check src/avicola_pro/modules/production/domain/egg_rules.py tests/unit/test_delivery13_egg_production_rules.py`.

### Task 2: Persist immutable daily egg facts

**Files:**
- Modify: `backend/src/avicola_pro/modules/production/infrastructure/models.py`
- Create: `backend/migrations/versions/0011_egg_production.py`
- Modify: `backend/src/avicola_pro/shared/infrastructure/models.py`
- Test: `backend/tests/integration/test_migrations.py`
- Test: `backend/tests/integration/test_production_service.py`

**Interfaces:**
- Produces: append-only `egg_production_events` with UUID, flock, house, date, nonnegative integer count, required globally unique idempotency key, optional reversal reference, actor and timestamps. Multiple records per flock/house/date are allowed; no business-level daily uniqueness rule is inferred.

- [ ] Add a migration/model regression proving required FKs, unique/idempotency constraints, nonnegative count and reversal FK.
- [ ] Run the focused persistence/migration tests and verify they fail before schema changes.
- [ ] Implement model metadata registration and Alembic upgrade/downgrade consistent with existing `0010_costing` head.
- [ ] Run migration tests from empty DB and `0010_costing` to new head and back in disposable PostgreSQL 16 databases.
- [ ] Add service tests for create, duplicate request, invalid assignment/date, reversal and transaction rollback; run `uv run pytest tests/integration/test_production_service.py -q`.

### Task 3: Expose secure API and current-style controls

**Files:**
- Modify: `backend/src/avicola_pro/modules/production/api/routes.py`
- Modify: `backend/src/avicola_pro/modules/production/application/service.py`
- Modify: `backend/src/avicola_pro/modules/identity/infrastructure/seed.py`
- Test: `backend/tests/unit/test_production_routes.py`
- Modify: `frontend/src/components/production-panel.tsx`
- Test: `frontend/tests/production.test.tsx`

**Interfaces:**
- `POST /api/v1/production/egg-records`: `{flock_id, house_id, occurred_on, egg_count, idempotency_key}`; returns created event with ID/status.
- `GET /api/v1/production/egg-records?date_from=&date_to=&flock_id=&house_id=&limit=&offset=`: paginated authorized confirmed records.
- Permissions: `production.eggs.read` and `production.eggs.record`.

- [ ] Add API tests for valid create/list, bad payload, unauthenticated, missing CSRF, forbidden, duplicate idempotency and audit record; run focused pytest and verify failures.
- [ ] Implement route/service using the existing `build_production_router`, `csrf_user`, `require`, `add_audit` and session transaction conventions.
- [ ] Add UI loading/empty/error/form states without altering global CSS/layout; test with Testing Library.
- [ ] Run `npm test -- --run tests/production.test.tsx`, `npm run lint`, and `npm run typecheck` from `frontend/`.

### Task 4: Run production regressions and document the new head

**Files:**
- Modify after verification: `DATABASE.md`, `PROJECT_STATUS.md`, `PROJECT_CONTEXT.md`, `CHANGELOG.md`.

- [ ] Run all production unit, route and PostgreSQL integration tests plus migration clean upgrade and rollback.
- [ ] Run backend Ruff, format check and Mypy; run frontend tests/lint/typecheck/build.
- [ ] Verify no import cycle or direct production-to-inventory schema coupling was introduced.
- [ ] Record exact migration head, command results, permissions and limitations; do not invent historical egg records.
