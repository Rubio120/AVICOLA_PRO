# AVICOLA PRO Functional Parity Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement these plans task-by-task after the user approves the plans and selects execution method. Keep each subsystem independently testable.

**Goal:** Complete AVICOLA PRO's poultry-specific business functions from the approved design while preserving its current stack and visual style, and close D11/D12 with exact-commit CI evidence.

**Architecture:** Extend the existing modular FastAPI/PostgreSQL backend and Next.js same-origin BFF/UI. Production owns egg-production facts, Inventory owns stock ledger, Sales owns channels and documents, Costing owns confirmed cost allocations, and Reporting remains read-only. Use a dependency-ordered set of implementation plans so each module can be reviewed and verified independently.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, Alembic, PostgreSQL 16, Next.js/React/TypeScript, Docker/Compose, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-23-functional-parity-design.md`

## Global Constraints

- Keep FastAPI, PostgreSQL and Next.js; do not migrate to Laravel/MySQL.
- Keep the current visual style; add only the controls required for new workflows.
- Preserve the one-company/multiple-farms decision; do not introduce multi-company tenancy.
- Use confirmed events/documents for official metrics; label estimates and never fabricate history.
- Preserve session, CSRF, backend RBAC, audit, idempotency, transactional boundaries and compensating corrections.
- Categories and package conversions are configurable and require approved values; never assume a tray size.
- Do not publish images or deploy to production; no production deployment is in scope.
- Do not treat local CI as remote CI; release closure requires all jobs green for the exact candidate SHA and a verified release bundle.

## Review Focus

- Zero or very large egg counts must be rejected/accepted according to an explicit approved rule; pin this in production domain tests.
- Duplicate daily submissions and correction/reversal requests must not duplicate production or inventory; pin idempotency and concurrency in production/inventory PostgreSQL tests.
- Missing category/conversion configuration must fail clearly without creating stock; pin this in inventory service/API tests.
- Credit notes, reversals, and draft documents must not inflate revenue, ticket average, or margin; pin this in Sales/Reporting integration tests.
- Empty periods, zero denominators, and absent approved formulas must not yield misleading infinities or fabricated KPIs; pin this in Costing/Reporting domain tests.

---

## Plan set and dependency order

1. `2026-09-24-delivery-11-12-ci-closeout.md` — independent deployment build/scan/Compose/backup/restore/release gate.
2. `2026-09-24-egg-production.md` — daily egg facts and secure production API/UI.
3. `2026-09-24-egg-inventory.md` — approved categories/presentations and inventory ledger integration; depends on egg production.
4. `2026-09-24-sales-channels.md` — wholesale/retail attribution and customer/ticket metrics; depends on productized egg stock.
5. `2026-09-24-feed-efficiency-costing.md` — approved efficiency and egg-cost formulas; depends on egg production and cost attribution decisions.
6. `2026-09-24-dashboard-xlsx.md` — proposal KPIs and audited Excel workbook; depends on the preceding metric/data plans.

## Cross-plan completion gates

- Before implementing a metric, record its approved unit, period, numerator/denominator, included statuses, rounding, and a worked example in the spec or an approved ADR.
- Each code task follows TDD, has focused PostgreSQL-backed tests where persistence/concurrency is involved, and ends with its relevant lint/type/build checks.
- Run the full backend PostgreSQL gate, frontend unit/lint/type/build gates, migrations from empty and prior head, security audits, and complete GitHub Actions after the final code SHA.
- Capture a genuine running-app screenshot with synthetic data and no secrets.
- Create the final source ZIP only after tests and secret/exclusion checks; email it with the completion summary to `arrietatobis741@gmail.com` only after all deliverables pass.
- Never deploy. State clearly if staging/off-host restore or human RBAC/formula approvals remain open.
