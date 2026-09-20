from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import text

from avicola_pro.modules.reporting.domain.rules import ReportFilter


def _date_clause(column: str, filters: ReportFilter) -> tuple[str, dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}
    if filters.date_from:
        clauses.append(f"{column} >= :date_from")
        params["date_from"] = filters.date_from
    if filters.date_to:
        clauses.append(f"{column} <= :date_to")
        params["date_to"] = filters.date_to
    return (" and " + " and ".join(clauses)) if clauses else "", params


async def dashboard(session: Any, filters: ReportFilter) -> dict[str, Any]:
    sales_clause, params = _date_clause("document_date", filters)
    sales = await session.execute(
        text(
            "select count(*) as count, coalesce(sum(total), 0) as total "
            "from commercial_documents where status = 'ISSUED'" + sales_clause
        ),
        params,
    )
    row = sales.one()
    values = {
        "sales_documents": int(row.count),
        "sales_total": Decimal(row.total),
    }
    for key, query in {
        "inventory_value": "select coalesce(sum(inventory_value), 0) as value from inventory_balances",
        "live_birds": "select coalesce(sum(live_birds), 0) as value from flock_balances",
        "accounts_payable": "select coalesce(sum(balance), 0) as value from accounts_payable where status = 'OPEN'",
        "accounts_receivable": (
            "select coalesce(sum(balance), 0) as value from accounts_receivable where status = 'OPEN'"
        ),
        "cash_balance": (
            "select coalesce(sum(case when direction = 'IN' then amount else -amount end), 0) as value "
            "from cash_movements where status = 'CONFIRMED'"
        ),
        "confirmed_costs": "select coalesce(sum(amount), 0) as value from cost_events where status = 'CONFIRMED'",
    }.items():
        result = await session.execute(text(query))
        values[key] = Decimal(result.scalar_one())
    return values


async def profitability(session: Any, filters: ReportFilter) -> tuple[list[dict[str, Any]], int]:
    clause, params = _date_clause("document_date", filters)
    count_result = await session.execute(
        text("select count(*) from commercial_documents where status = 'ISSUED'" + clause),  # noqa: S608
        params,
    )
    total = int(count_result.scalar_one())
    params.update({"offset": filters.offset, "limit": filters.limit})
    result = await session.execute(
        text(
            "select id, document_date, customer_name_snapshot, total "
            "from commercial_documents where status = 'ISSUED'"
            + clause
            + " order by document_date desc, id desc offset :offset limit :limit"
        ),
        params,
    )
    rows = []
    for item in result.mappings():
        rows.append(
            {
                "id": item["id"],
                "date": item["document_date"],
                "customer": item["customer_name_snapshot"],
                "revenue": Decimal(item["total"]),
                "cost": Decimal("0"),
                "margin": Decimal(item["total"]),
            }
        )
    return rows, total
