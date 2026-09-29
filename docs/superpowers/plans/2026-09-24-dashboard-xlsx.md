# Proposal Dashboard and XLSX Reporting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task after upstream metric plans and plan approval.

**Goal:** Extend the existing Dashboard and reports with proposal metrics and a secure `.xlsx` export while preserving the current page style.

**Architecture:** Reporting remains read-only and consumes approved metric/query contracts. Dashboard and XLSX share one service/filter/status policy to avoid mismatched totals. The current panel gains only the required metric groups and accessible controls.

**Tech Stack:** Python 3.13/FastAPI/SQLAlchemy/PostgreSQL, Next.js/React/TypeScript, a locked and audited Python XLSX writer selected during dependency review.

**Spec:** `docs/superpowers/specs/2026-09-23-functional-parity-design.md`

## Global Constraints

- Do not redesign the existing interface; add only proposal metrics and functional filters.
- Use confirmed facts and approved formulas; include unit, period and status in returned metric contract.
- Dashboard and export enforce same RBAC, date filters and document inclusion policy.
- Exports are bounded, audited, safe for user-entered text, and contain no credentials/PII beyond fields authorized for the report.
- CI must test dependency locks and vulnerability audit after adding the XLSX library.

## Review Focus

- Different dashboard/export date filters must be impossible; use one validated `ReportFilter` in both tests.
- Empty datasets and unavailable formulas render a clear state rather than zero-valued false claims.
- Spreadsheet cells beginning with formula markers remain text; exercise `=`, `+`, `-`, `@` payloads.
- Large date ranges honor row/size limits and fail before unbounded memory use.
- A forbidden user cannot obtain data by calling the export endpoint directly or through the BFF.

---

### Task 1: Extend the reporting contract and dashboard reader

**Files:**
- Modify: `backend/src/avicola_pro/modules/reporting/infrastructure/reader.py`
- Modify: `backend/src/avicola_pro/modules/reporting/api/routes.py`
- Test: `backend/tests/unit/test_reporting_reader.py`
- Test: `backend/tests/unit/test_reporting_rules.py`

**Interfaces:**
- `GET /api/v1/reports/dashboard?date_from=&date_to=` returns existing fields plus approved egg production, posture, mortality, flock age, feed efficiency, egg cost, channel margin and inventory coverage fields with units/availability metadata.

- [ ] Add tests that reconcile every returned metric to known synthetic confirmed records; assert drafts/reversals excluded.
- [ ] Add query count/limit tests and parameterized filter edge tests; verify fail before reader changes.
- [ ] Implement read-only query ports; do not import internal models from other bounded contexts.
- [ ] Run reporting reader/API tests and dependency-rule tests.

### Task 2: Add minimal current-style dashboard controls and states

**Files:**
- Modify: `frontend/src/components/reporting-panel.tsx`
- Modify: `frontend/tests/reporting.test.tsx`

- [ ] Add accessible date/channel filters and sections for the approved poultry, efficiency, profitability, commercial and inventory metrics.
- [ ] Test values with units, missing/estimated statuses, loading, no-data and API error cases.
- [ ] Preserve existing cards, CSS tokens, typography and navigation; do not reproduce the reference screenshot layout.
- [ ] Run frontend tests, ESLint, typecheck and production build.

### Task 3: Add audited XLSX export

**Files:**
- Modify: `backend/pyproject.toml`, `backend/uv.lock` after selecting a compatible audited writer.
- Modify: `backend/src/avicola_pro/modules/reporting/domain/rules.py`
- Modify: `backend/src/avicola_pro/modules/reporting/api/routes.py`
- Modify: `backend/src/avicola_pro/modules/audit/application/writer.py` only if existing event shape cannot represent xlsx format.
- Test: `backend/tests/unit/test_reporting_rules.py`
- Test: `backend/tests/unit/test_reporting_reader.py`

**Interfaces:**
- `GET /api/v1/reports/profitability.xlsx?date_from=&date_to=&channel=` returns an OpenXML workbook with bounded rows and the same filters/values as the JSON report.

- [ ] Add failing tests for valid OpenXML workbook, sheet/column headers, formats, formula-injection strings, maximum rows, unauthorized and audit event format.
- [ ] Select the writer by compatibility with Python 3.13, supported OpenXML output, lockfile reproducibility and clean `pip-audit`; pin and commit the exact resolved version only after that check.
- [ ] Implement streaming/bounded workbook output; escape all untrusted string cells as text and avoid formulas/macros/external links.
- [ ] Require `reports.export`, transactionally record `report.export` with format `xlsx`, and test BFF path.
- [ ] Run reporting tests, `uv lock --check`, dependency audit and full backend/frontend gates.
