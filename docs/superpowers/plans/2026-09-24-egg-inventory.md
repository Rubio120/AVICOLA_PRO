# Egg Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task after plan approval and method selection.

**Goal:** Track saleable egg stock by approved category and presentation through the existing inventory ledger, linking confirmed production and sales atomically.

**Architecture:** Inventory owns categories/presentation conversions and stock movement; production emits confirmed daily egg facts; authorized application services coordinate one UnitOfWork for stock receipt and reversal. Sales deliveries continue to remove stock through existing inventory documents.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, Alembic, PostgreSQL 16, Next.js/React/TypeScript.

**Spec:** `docs/superpowers/specs/2026-09-23-functional-parity-design.md`

## Global Constraints

- Do not assume egg grades, pack sizes, tray conversion, waste rules, or historical quantities; use only user-approved configuration.
- The base quantity is an individual egg; conversions are explicit, exact and versioned so old documents remain reproducible.
- Inventory ledger remains the single source of stock truth; stock cannot go negative.
- Confirmed movements are immutable and corrected with compensating documents.
- Protect all reads/writes with backend RBAC, CSRF, audit and idempotency.
- Each egg category maps to exactly one existing inventory product whose base unit the business configured as an individual egg; the migration creates no categories, products, warehouses, package sizes or conversion values.
- A daily production event remains unclassified until category allocations sum exactly to egg_count. Incomplete or mismatched classification must never post stock.
- The receiving warehouse is explicitly chosen when classified; no implicit warehouse is selected.
- Egg-specific boundaries enforce whole eggs while the existing general inventory keeps its numeric quantity precision.

## Review Focus

- Missing category or conversion blocks confirmation with no partial stock change.
- Fractional eggs, zero/negative conversion, overflow and unit mismatch are rejected.
- Concurrent sale/adjustment cannot oversell stock; assert with PostgreSQL row-lock integration tests.
- Reversal restores the exact original quantity/value and does not duplicate on retry.
- Updating a configured conversion must not reinterpret existing ledger entries or historical documents.

---

### Task 1: Add pure category and package conversion rules

**Files:**
- Create: `backend/src/avicola_pro/modules/inventory/domain/egg_units.py`
- Create: `backend/tests/unit/test_egg_inventory_rules.py`

**Interfaces:**
- `to_base_egg_units(quantity: Decimal, units_per_package: int) -> int`
- `from_base_egg_units(egg_count: int, units_per_package: int) -> tuple[int, int]` returning full packages and remaining eggs.

- [ ] Write tests for exact conversion, remainder, invalid zero/negative factor, fractional resulting egg units and integer overflow; synthetic fixture values are examples only, never operational defaults.
- [ ] Run focused test and verify it fails before implementation.
- [ ] Implement pure Decimal/integer conversions with no implicit rounding of egg units.
- [ ] Rerun tests and Ruff.

### Task 2: Persist approved egg categories and conversion versions

**Files:**
- Modify: `backend/src/avicola_pro/modules/inventory/infrastructure/models.py`
- Create: `backend/migrations/versions/0012_egg_inventory.py`
- Modify: `backend/src/avicola_pro/shared/infrastructure/models.py`
- Test: `backend/tests/integration/test_migrations.py`
- Test: `backend/tests/integration/test_inventory_service.py`

**Interfaces:**
- Category configuration carries code/name, a unique existing product mapping, saleable flag and active state; no default category or product is seeded.
- Presentation conversion carries category, display unit, positive integer base units and immutable version/effective metadata. A later transaction stores the applied conversion version and exact base quantity.

- [ ] Add model/migration tests for uniqueness (category↔product is one-to-one), positive conversions, FK behavior and immutable historical conversion snapshots.
- [ ] Run focused migration tests and observe failure.
- [ ] Implement Alembic migration after `0011_egg_production`; register models centrally.
- [ ] Verify fresh migration, upgrade from previous head and downgrade only on disposable PostgreSQL 16 databases.

### Task 3: Receive production and issue sales through one stock ledger

**Files:**
- Modify: `backend/src/avicola_pro/modules/inventory/application/service.py`
- Modify: `backend/src/avicola_pro/modules/production/application/service.py`
- Modify: `backend/src/avicola_pro/modules/production/api/routes.py`
- Test: `backend/tests/integration/test_production_service.py`
- Test: `backend/tests/integration/test_inventory_service.py`
- Test: `backend/tests/integration/test_sales_service.py`

**Interfaces:**
- A production event remains an unclassified total until one or more category allocations sum exactly to egg_count. An explicit warehouse is required. Receipt document(s), allocations and source links are written in the caller's transaction; retry by production event ID cannot duplicate stock.
- Existing sales delivery issues the mapped egg product in its configured base unit. Before accepting any non-base presentation quantity, the applied conversion version and exact base quantity must be stored immutably.
- Invalid/inactive category or product, incomplete/mismatched classification, fractional egg, missing warehouse, insufficient stock or database failure leaves both classification and inventory unchanged.

- [ ] Add integration tests for production-to-stock, unclassified and incomplete/mismatched classification, sale-to-stock, no-stock, concurrent issue, reversal and retry; verify they fail before service changes.
- [ ] Implement coordination using existing neutral application ports/UnitOfWork patterns; do not add cyclic imports or duplicate stock balance tables.
- [ ] Verify each transaction has one commit boundary and audit entries correlate to the source event/document.
- [ ] Run all three focused PostgreSQL test files.

### Task 4: Add minimal configuration and balance controls

**Files:**
- Modify: `backend/src/avicola_pro/modules/inventory/api/routes.py`
- Modify: `backend/src/avicola_pro/modules/identity/infrastructure/seed.py`
- Modify: `frontend/src/components/inventory-panel.tsx`
- Create: `backend/tests/unit/test_inventory_egg_routes.py`
- Test: `frontend/tests/inventory.test.tsx`

- [ ] Add protected category/presentation management endpoints with `inventory.egg_categories.manage` and read-only balance endpoint scoped to the existing inventory permissions. Require explicit product/unit mapping; do not infer category from product name.
- [ ] Test session, CSRF, RBAC, audit, validation and disabled-category behavior; no secret or real-farm fixture data.
- [ ] Add controls in the existing inventory panel for approved config and categorized balances, preserving current CSS/design language.
- [ ] Run backend focused tests and frontend tests/lint/typecheck.

## Approval boundary

The user approved this configurable model and integrated method. Operational setup still requires business-provided category names, category-to-product mappings, approved package units/sizes, and a receiving warehouse. No report may silently classify counts or select defaults. This plan does not invent those values.
