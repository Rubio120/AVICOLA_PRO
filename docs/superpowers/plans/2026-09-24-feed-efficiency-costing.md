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

- [ ] Present candidate definitions for posture %, feed per live bird, feed conversion, feed cost per egg, total cost per egg, channel margin and coverage days.
- [ ] Record only user-approved formulas and sample calculations; if any is unapproved, keep that metric out of code and label it pending.
- [ ] Do not start Tasks 2–4 for an unapproved metric.

### Task 2: Implement pure metric rules with executable examples

**Files:**
- Create: `backend/src/avicola_pro/modules/reporting/domain/poultry_metrics.py`
- Create: `backend/tests/unit/test_delivery13_metric_rules.py`

**Interfaces:**
- Add one named function per approved formula, each accepting typed `Decimal` facts and returning a typed result with unit/availability reason; signatures mirror only the approved formula table.

- [ ] Convert every worked business example from Task 1 into a failing unit test, including boundary, empty denominator and rounding cases.
- [ ] Run `uv run pytest tests/unit/test_delivery13_metric_rules.py -q` and confirm failures before implementation.
- [ ] Implement formulas using Decimal; no SQL, float, implicit package conversion or hidden defaults.
- [ ] Rerun tests and Ruff/Mypy on the new module.

### Task 3: Feed approved costs and egg facts through costing/reporting

**Files:**
- Modify only as required: `backend/src/avicola_pro/modules/costing/application/service.py`, `backend/src/avicola_pro/modules/reporting/infrastructure/reader.py`, `backend/src/avicola_pro/modules/reporting/api/routes.py`.
- Test: `backend/tests/integration/test_costing_service.py`, `backend/tests/unit/test_reporting_reader.py`.

**Interfaces:**
- Reporting response carries value, unit, period and availability/status for each metric; estimated results have explicit `estimated` status.

- [ ] Add PostgreSQL integration fixtures for shared costs, multiple flocks and reversals; prove reconciliation and exact approved result.
- [ ] Add regression preventing existing fake `cost=0 / margin=revenue` from being presented as actual profitability.
- [ ] Implement query-port reads and costing allocations only under approved policies; preserve module boundaries.
- [ ] Run focused costing/reporting integration tests, migration tests if schema changes, and dependency architecture checks.
