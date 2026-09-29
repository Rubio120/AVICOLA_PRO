# Sales Channels and Customer Metrics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task after plan approval and method selection.

**Goal:** Attribute commercial documents to the proposal's wholesale/retail channels and report customer activity and ticket averages without changing existing order semantics.

**Architecture:** Sales owns the channel on the commercial order/document snapshot. Reporting reads issued sales plus approved compensating documents and uses one shared filter/status policy for dashboard and exports.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, Alembic, PostgreSQL 16, Next.js/React/TypeScript.

**Spec:** `docs/superpowers/specs/2026-09-23-functional-parity-design.md`

## Global Constraints

- Use only wholesale/retail channels named in the proposal unless the user approves additional channels.
- Preserve issued-document, delivery, accounts-receivable, payment and credit-note invariants.
- Draft, cancelled, reversed or compensated documents must not be counted as positive revenue twice.
- Use date filters and read-only parameterized reporting queries; exports remain RBAC-protected and audited.
- Keep current UI style and avoid personal customer data in fixtures.

## Review Focus

- Missing channel on a required commercial document is rejected before issue; old rows receive an explicitly approved migration value or remain marked legacy, never silently guessed.
- Wholesale/retail filters return disjoint and reconcilable revenue totals.
- “New customer” uses an approved first-qualified-event rule and stable date window.
- Ticket average handles zero issued documents and credit notes without division errors or double-counting.
- Partial deliveries and payments do not create extra sales documents or inflate ticket count.

---

### Task 1: Define channel and customer metric domain rules

**Files:**
- Modify: `backend/src/avicola_pro/modules/sales/domain/rules.py`
- Modify: `backend/tests/unit/test_delivery7_rules.py`
- Modify: `backend/src/avicola_pro/modules/reporting/domain/rules.py`
- Modify: `backend/tests/unit/test_reporting_rules.py`

**Interfaces:**
- `SalesChannel` allowed values: `WHOLESALE`, `RETAIL`.
- `calculate_ticket_average(net_issued_sales: Decimal, issued_document_count: int) -> Decimal | None`.

- [ ] Add tests for both valid channels, invalid/missing channel, zero document count and exact Decimal behavior; run focused tests and observe failure.
- [ ] Add a pure first-time-customer predicate based on an approved event and period definition; encode those examples from the spec review decision.
- [ ] Implement rules without SQL and rerun focused pytest plus Ruff.

### Task 2: Persist channel on orders and issued documents

**Files:**
- Modify: `backend/src/avicola_pro/modules/sales/infrastructure/models.py`
- Create: `backend/migrations/versions/0013_sales_channel.py`
- Modify: `backend/src/avicola_pro/shared/infrastructure/models.py`
- Test: `backend/tests/integration/test_migrations.py`
- Test: `backend/tests/integration/test_sales_service.py`

**Interfaces:**
- `SalesOrder.channel` and commercial-document channel snapshot use `WHOLESALE|RETAIL`.
- Order creation API requires `channel` on new orders; existing issued documents retain stable historical meaning via an explicit reviewed backfill policy.

- [ ] Add migration and service tests for new channel, immutable issued snapshot, legacy records and rejected invalid values.
- [ ] Run focused tests and confirm failure before schema/service changes.
- [ ] Implement migration from the then-current Alembic head, maintain the one-commit transaction and update response schemas.
- [ ] Verify no new dependency cycle using `backend/tests/architecture/test_dependency_rules.py`.

### Task 3: Expose channel in the existing Sales workflow

**Files:**
- Modify: `backend/src/avicola_pro/modules/sales/api/routes.py`
- Modify: `frontend/src/components/sales-panel.tsx`
- Test: `backend/tests/unit/test_sales_routes.py`
- Create: `frontend/tests/sales-channel.test.tsx`

- [ ] Add API tests for missing/invalid channel, authorization, CSRF and audit.
- [ ] Add channel selection to the existing order flow without visual restyling; preserve same-origin BFF requests.
- [ ] Add tests for loading/empty/error and channel selection; run frontend tests, lint and typecheck.

### Task 4: Report channel/customer aggregates

**Files:**
- Modify: `backend/src/avicola_pro/modules/reporting/infrastructure/reader.py`
- Modify: `backend/src/avicola_pro/modules/reporting/api/routes.py`
- Modify: `backend/src/avicola_pro/modules/reporting/domain/rules.py`
- Test: `backend/tests/unit/test_reporting_reader.py`
- Test: `backend/tests/unit/test_reporting_rules.py`

**Interfaces:**
- `GET /api/v1/reports/commercial?date_from=&date_to=&channel=` returns issued revenue, document count, customer count, new customers, and ticket average with period/channel included in response.

- [ ] Write reader/API tests over synthetic issued, draft, reversed and credit-note records and verify expected totals manually.
- [ ] Implement parameterized read-only queries and shared inclusion rules; all fields remain `Decimal` until serialized.
- [ ] Test pagination/date filters and malformed ranges; run focused reader/routes and architecture tests.
