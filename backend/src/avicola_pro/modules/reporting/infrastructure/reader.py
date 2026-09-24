from __future__ import annotations

from datetime import date
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
            "select count(*) filter (where document_type = 'INVOICE') as count, "
            "coalesce(sum(case when document_type = 'CREDIT_NOTE' then -total else total end), 0) as total "
            "from commercial_documents where status = 'ISSUED' and document_type in ('INVOICE','CREDIT_NOTE')"
            + sales_clause
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
            "select id, document_date, document_type, customer_name_snapshot, "
            "case when document_type = 'CREDIT_NOTE' then -total else total end as net_total "
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
                "document_type": item["document_type"],
                "customer": item["customer_name_snapshot"],
                "revenue": Decimal(item["net_total"]),
                "cost": None,
                "margin": None,
            }
        )
    return rows, total


async def commercial_sales(
    session: Any,
    date_from: date | None = None,
    date_to: date | None = None,
    channel: str | None = None,
) -> list[dict[str, Any]]:
    if channel not in {None, "WHOLESALE", "RETAIL"}:
        raise ValueError("channel must be WHOLESALE or RETAIL")
    conditions = ["status = 'ISSUED'", "document_type in ('INVOICE','CREDIT_NOTE')"]
    params: dict[str, Any] = {}
    if date_from is not None:
        conditions.append("document_date >= :date_from")
        params["date_from"] = date_from
    if date_to is not None:
        conditions.append("document_date <= :date_to")
        params["date_to"] = date_to
    if channel is not None:
        conditions.append("channel = :channel")
        params["channel"] = channel
    statement = text(
        "select channel, "
        "count(*) filter (where document_type = 'INVOICE') as invoices, "
        "count(*) filter (where document_type = 'CREDIT_NOTE') as credit_notes, "
        "count(distinct customer_id) as customers_with_documents, "
        "coalesce(sum(case when document_type = 'CREDIT_NOTE' then -total else total end), 0) as net_revenue "
        "from commercial_documents where " + " and ".join(conditions) + " group by channel order by channel nulls last"
    )
    result = await session.execute(statement, params)
    return [
        {
            "channel": item["channel"] or "LEGACY_UNCLASSIFIED",
            "invoices": int(item["invoices"]),
            "credit_notes": int(item["credit_notes"]),
            "customers_with_documents": int(item["customers_with_documents"]),
            "net_revenue": Decimal(item["net_revenue"]),
        }
        for item in result.mappings()
    ]
