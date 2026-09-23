from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable

PSQL = "/usr/lib/postgresql/16/bin/psql"

CHECKS: tuple[tuple[str, str], ...] = (
    (
        "inventory movement quantities and values match balance projections",
        """
        WITH ledger AS (
            SELECT warehouse_id, product_id, inventory_lot_id,
                   sum(quantity_delta) AS quantity, sum(value_delta) AS inventory_value
            FROM inventory_movements
            GROUP BY warehouse_id, product_id, inventory_lot_id
        )
        SELECT count(*)
        FROM inventory_balances AS b
        FULL OUTER JOIN ledger AS l
          ON b.warehouse_id = l.warehouse_id
         AND b.product_id = l.product_id
         AND b.inventory_lot_id IS NOT DISTINCT FROM l.inventory_lot_id
        WHERE abs(coalesce(b.quantity, 0) - coalesce(l.quantity, 0)) > 0.00005
           OR abs(coalesce(b.inventory_value, 0) - coalesce(l.inventory_value, 0)) > 0.005
        """,
    ),
    (
        "flock balances match supported bird, mortality and adjustment events",
        """
        WITH event_deltas AS (
            SELECT flock_id,
                   CASE movement_type
                       WHEN 'INITIAL' THEN quantity
                       WHEN 'TRANSFER_IN' THEN quantity
                       WHEN 'TRANSFER_OUT' THEN -quantity
                       WHEN 'SALE' THEN -quantity
                       WHEN 'SLAUGHTER' THEN -quantity
                   END AS delta
            FROM bird_movement_events
            WHERE status <> 'REVERSED' AND movement_type <> 'OTHER'
            UNION ALL
            SELECT flock_id, -quantity FROM mortality_events WHERE status <> 'REVERSED'
            UNION ALL
            SELECT flock_id,
                   CASE adjustment_type
                       WHEN 'CORRECTION_IN' THEN quantity
                       WHEN 'CORRECTION_OUT' THEN -quantity
                   END
            FROM bird_adjustment_events
        ), expected AS (
            SELECT flock_id, sum(delta) AS live_birds
            FROM event_deltas GROUP BY flock_id
        )
        SELECT count(*)
        FROM flock_balances AS b
        FULL OUTER JOIN expected AS e USING (flock_id)
        WHERE abs(coalesce(b.live_birds, 0) - coalesce(e.live_birds, 0)) > 0.00005
        """,
    ),
    (
        "flock event stream contains no directionless OTHER movement",
        "SELECT count(*) FROM bird_movement_events WHERE movement_type = 'OTHER' AND status <> 'REVERSED'",
    ),
    (
        "closed cash session expected balances match signed cash movements",
        """
        SELECT count(*)
        FROM cash_sessions AS s
        LEFT JOIN (
            SELECT cash_session_id,
                   sum(CASE direction WHEN 'IN' THEN amount ELSE -amount END) AS movement_total
            FROM cash_movements GROUP BY cash_session_id
        ) AS m ON m.cash_session_id = s.id
        WHERE s.status = 'CLOSED'
          AND (s.expected_balance IS NULL
               OR abs(s.expected_balance - (s.opening_balance + coalesce(m.movement_total, 0))) > 0.005)
        """,
    ),
    (
        "accounts payable balances equal original less applied amounts",
        "SELECT count(*) FROM accounts_payable WHERE abs(balance - (original_amount - applied_amount)) > 0.005",
    ),
    (
        "accounts receivable balances equal original less applied amounts",
        "SELECT count(*) FROM accounts_receivable WHERE abs(balance - (original_amount - applied_amount)) > 0.005",
    ),
    (
        "accounts payable applied amounts match confirmed payment allocations",
        """
        SELECT count(*)
        FROM accounts_payable AS a
        LEFT JOIN (
            SELECT x.accounts_payable_id,
                   sum(CASE WHEN p.reversal_of_id IS NULL THEN x.amount ELSE -x.amount END) AS allocated
            FROM supplier_payment_allocations AS x
            JOIN supplier_payments AS p ON p.id = x.payment_id
            WHERE p.status IN ('CONFIRMED', 'REVERSED')
            GROUP BY x.accounts_payable_id
        ) AS x ON x.accounts_payable_id = a.id
        WHERE abs(a.applied_amount - coalesce(x.allocated, 0)) > 0.005
        """,
    ),
    (
        "accounts receivable applied amounts match confirmed payment allocations",
        """
        SELECT count(*)
        FROM accounts_receivable AS a
        LEFT JOIN (
            SELECT x.accounts_receivable_id, sum(x.amount) AS allocated
            FROM customer_payment_allocations AS x
            JOIN customer_payments AS p ON p.id = x.payment_id
            WHERE p.status = 'CONFIRMED'
            GROUP BY x.accounts_receivable_id
        ) AS x ON x.accounts_receivable_id = a.id
        WHERE abs(a.applied_amount - coalesce(x.allocated, 0)) > 0.005
        """,
    ),
    (
        "audit and security event schema constraints exist and are validated",
        """
        SELECT CASE
            WHEN (SELECT count(*) FROM pg_constraint
                  WHERE conrelid = 'audit_events'::regclass AND contype = 'c' AND convalidated
                    AND conname = ANY(ARRAY[
                        'ck_audit_events_outcome_valid',
                        'ck_audit_events_before_data_object', 'ck_audit_events_after_data_object',
                        'ck_audit_events_before_data_allowlist', 'ck_audit_events_after_data_allowlist',
                        'ck_audit_events_before_data_scalar_shape', 'ck_audit_events_after_data_scalar_shape'
                    ])) = 7
             AND (SELECT count(*) FROM pg_constraint
                  WHERE conrelid = 'security_events'::regclass AND contype = 'c' AND convalidated
                    AND conname = ANY(ARRAY[
                        'ck_security_events_outcome_valid', 'ck_security_events_metadata_object',
                        'ck_security_events_metadata_allowlist', 'ck_security_events_metadata_scalar_shape'
                    ])) = 4
            THEN 0 ELSE 1 END
        """,
    ),
)


class RestoreVerificationError(RuntimeError):
    pass


def verify_database(query_scalar: Callable[[str], int]) -> list[str]:
    failures = [name for name, query in CHECKS if query_scalar(query) > 0]
    if failures:
        raise RestoreVerificationError("Restore reconciliation failed: " + "; ".join(failures))
    return [name for name, _ in CHECKS]


def _psql_scalar(query: str) -> int:
    result = subprocess.run(  # noqa: S603 - executable and query come from fixed image code.
        [
            PSQL,
            "--no-psqlrc",
            "--tuples-only",
            "--no-align",
            "--set=ON_ERROR_STOP=1",
            "--dbname=service=restore",
            "--command",
            query,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        timeout=60,
    )
    if result.returncode != 0:
        raise RestoreVerificationError("Database integrity query failed")
    try:
        return int(result.stdout.strip())
    except ValueError:
        raise RestoreVerificationError("Database integrity query returned an invalid result") from None


def main() -> int:
    try:
        completed = verify_database(_psql_scalar)
    except (RestoreVerificationError, OSError, subprocess.TimeoutExpired):
        print("Restore verification failed; details withheld", file=sys.stderr)
        return 1
    print(f"Restore reconciliation passed ({len(completed)} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
