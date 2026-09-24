# Feed Efficiency and Egg Costing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task after plan approval and explicit business-rule approval.

**Goal:** Calculate proposal-aligned feed-efficiency and egg profitability metrics from confirmed production, feed, inventory and costing facts using business-approved formulas.

**Architecture:** Do not duplicate ledgers. Production/Inventory provide confirmed egg and feed facts; Costing owns confirmed costs/allocations; Reporting reads those contracts. Every formula is a pure Decimal rule with unit/period metadata and a worked acceptance fixture.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, PostgreSQL 16, Alembic, Decimal arithmetic, Next.js/TypeScript.

**Spec:** `docs/superpowers/specs/2026-09-23-functional-parity-design.md`

## Global Constraints

- No official metric is implemented until the user/business approves its unit, period, numerator, denominator, included statuses, allocation and rounding with worked examples.
- Confirmed events only; never treat a placeholder zero cost or estimated value as actual profit.
- No negative or zero denominators may produce infinity, NaN or an invented zero.
- Use Decimal and the project's established monetary rounding; maintain costing immutability and compensating reversals.
- No undocumented cross-module imports; reporting remains read-only.

## Review Focus

- No birds, no eggs or no feed in a period returns an explicit unavailable/not-applicable result, not a fabricated ratio.
- A period boundary includes each event exactly once under the approved timezone/date policy.
- Reversed feed/cost/production events are excluded or compensated exactly once.
- Costs shared by multiple flocks/granjas reconcile to their original confirmed total under the approved allocation policy.
- Rounding each line versus only the final aggregate matches the signed worked examples.

---

### Task 1: Freeze business formula examples before code

**Files:**
- Modify: `docs/superpowers/specs/2026-09-23-functional-parity-design.md` only after written user/business decisions.
- Test fixture owner: `backend/tests/unit/test_delivery13_metric_rules.py` (created in Task 2).

**Interfaces:**
- Approved formula record includes metric name, unit, date range behavior, numerator, denominator, status inclusion, allocation rule, precision/rounding, empty-period result and at least one worked input/output example.

- [x] Present and record the user-approved formulas: eggs per average live bird (without inventing a percentage), feed kg per average live bird, kg/dozen, confirmed feed cost/saleable egg, average ticket and 30-day stock coverage.
- [x] Keep unavailable inputs explicitly unavailable and do not invent values.
- [x] Keep posture percentage normalization, total cost per egg and channel margin pending; do not calculate them before their period/allocation/returns policies are approved.

### Task 2: Implement pure metric rules with executable examples

**Files:**
- Create: `backend/src/avicola_pro/modules/reporting/domain/poultry_metrics.py`
- Create: `backend/tests/unit/test_delivery13_metric_rules.py`

**Interfaces:**
- Add one named function per approved formula, each accepting typed `Decimal` facts and returning a typed result with unit/availability reason; signatures mirror only the approved formula table.

- [x] Add executable formula, empty-denominator, invalid-input and count-type tests for the approved pure rules.
- [x] Use the test-first workflow before implementation.
- [x] Implement approved pure formulas using Decimal and explicit units/availability reasons.
- [x] Rerun focused tests, Ruff and MyPy; the full backend suite is recorded below.

### Task 3: Feed approved costs and egg facts through costing/reporting

**Files:**
- Modify only as required: `backend/src/avicola_pro/modules/costing/application/service.py`, `backend/src/avicola_pro/modules/reporting/infrastructure/reader.py`, `backend/src/avicola_pro/modules/reporting/api/routes.py`.
- Test: `backend/tests/integration/test_costing_service.py`, `backend/tests/unit/test_reporting_reader.py`.

**Interfaces:**
- Reporting response carries value, unit, period and availability/status for each metric; estimated results have explicit `estimated` status.

- [ ] Add repeatable PostgreSQL integration fixtures for metric aggregation, multiple flocks and reversal boundaries; current SQL received a local PostgreSQL smoke test but is not yet covered by dedicated integration fixtures.
- [x] Keep total cost/egg and margin unavailable rather than presenting placeholder `cost=0` or `margin=revenue` as profitability.
- [x] Implement read-only reporting queries over confirmed facts, with unknown inputs represented as unavailable.
- [x] Run dependency architecture checks and the complete backend suite; focused PostgreSQL smoke passed. Dedicated metric integration fixtures remain open.

## Validation snapshot — 2026-09-24

- Backend: 316 tests passed; 80.09% total coverage (minimum 80%).
- Frontend: 56 tests passed, 87.97% statements / 80.55% branches; lint, TypeScript and production build passed.
- D11/D12 remain open until a fresh remote CI verifies the exact pushed commit, image scans, Compose startup and backup/restore, plus the release bundle verification.
- No production deployment was performed. Historical coverage gaps and pending business formulas are not represented as closed.
