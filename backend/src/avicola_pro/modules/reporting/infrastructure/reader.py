from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from avicola_pro.modules.reporting.domain.poultry_metrics import (
    MetricResult,
    average_ticket,
    feed_conversion,
    feed_cost_per_egg,
    feed_per_bird,
    posture_rate,
)
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
    metric_params = {
        "date_from": filters.date_from or date.min,
        "date_to": filters.date_to or date.max,
    }
    metrics = await session.execute(
        text(
            """
            select
              (select coalesce(sum(pe.egg_count), 0) from egg_production_events pe
               where pe.reversal_of_id is null
                 and not exists (select 1 from egg_production_events reversal where reversal.reversal_of_id = pe.id)
                 and pe.occurred_on >= :date_from
                 and pe.occurred_on <= :date_to) as egg_count,
              (select avg(daily.live_birds) from (
                 select fdr.record_date, sum(fdr.observed_birds) as live_birds
                 from flock_daily_records fdr
                 where fdr.record_date >= :date_from and fdr.record_date <= :date_to
                 group by fdr.record_date
               ) daily) as average_live_birds,
              (select count(*) from feed_consumption fc
               where fc.occurred_on >= :date_from
                 and fc.occurred_on <= :date_to) as feed_records,
              (select count(*) from feed_consumption fc join products p on p.id = fc.product_id
               join inventory_movements im on im.id = fc.inventory_movement_id
               join inventory_documents d on d.id = im.document_id
               where p.base_unit_code = 'kg' and d.status = 'CONFIRMED' and im.movement_type = 'ISSUE'
                 and im.reversal_of_id is null
                 and fc.occurred_on >= :date_from
                 and fc.occurred_on <= :date_to) as feed_records_in_kg,
              (select count(*) from feed_consumption fc join products p on p.id = fc.product_id
               join inventory_movements im on im.id = fc.inventory_movement_id
               join inventory_documents d on d.id = im.document_id
               where p.base_unit_code = 'kg' and d.status = 'CONFIRMED' and im.movement_type = 'ISSUE'
                 and im.reversal_of_id is null and im.unit_cost > 0
                 and fc.occurred_on >= :date_from
                 and fc.occurred_on <= :date_to) as costed_feed_records,
              (select coalesce(sum(fc.quantity), 0) from feed_consumption fc
               join products p on p.id = fc.product_id
               join inventory_movements im on im.id = fc.inventory_movement_id
               join inventory_documents d on d.id = im.document_id
               where p.base_unit_code = 'kg' and d.status = 'CONFIRMED' and im.movement_type = 'ISSUE'
                 and im.reversal_of_id is null
                 and fc.occurred_on >= :date_from
                 and fc.occurred_on <= :date_to) as feed_kg,
              (select coalesce(sum(-im.value_delta), 0) from feed_consumption fc
               join products p on p.id = fc.product_id
               join inventory_movements im on im.id = fc.inventory_movement_id
               join inventory_documents d on d.id = im.document_id
               where p.base_unit_code = 'kg' and d.status = 'CONFIRMED' and im.movement_type = 'ISSUE'
                 and im.reversal_of_id is null
                 and fc.occurred_on >= :date_from
                 and fc.occurred_on <= :date_to) as confirmed_feed_cost,
              (select coalesce(sum(a.egg_count), 0) from egg_production_allocations a
               join egg_production_classifications c on c.id = a.classification_id
               join egg_production_events pe on pe.id = c.production_event_id
               join egg_categories ec on ec.id = a.category_id
               where ec.is_saleable and pe.reversal_of_id is null
                 and not exists (select 1 from egg_production_events reversal where reversal.reversal_of_id = pe.id)
                 and pe.occurred_on >= :date_from
                 and pe.occurred_on <= :date_to) as saleable_egg_count,
              (select count(*) from (
                 select customer_id, min(document_date) as first_invoice from commercial_documents
                 where status = 'ISSUED' and document_type = 'INVOICE' and customer_id is not null
                 group by customer_id
               ) first_invoices
               where first_invoice >= :date_from
                 and first_invoice <= :date_to) as new_customer_count,
               (select count(*) from commercial_documents
               where status = 'ISSUED' and document_type = 'INVOICE' and customer_id is null
                 and document_date <= :date_to) as unassigned_invoice_count
            """
        ),
        metric_params,
    )
    metric_row = metrics.one()
    egg_count = int(metric_row.egg_count)
    feed_records = int(metric_row.feed_records)
    feed_records_in_kg = int(metric_row.feed_records_in_kg)
    costed_feed_records = int(metric_row.costed_feed_records)
    average_birds = None if metric_row.average_live_birds is None else Decimal(metric_row.average_live_birds)
    feed_kg = Decimal(metric_row.feed_kg)
    confirmed_feed_cost = Decimal(metric_row.confirmed_feed_cost)
    if feed_records == 0:
        feed_bird_metric = MetricResult(None, "kg/bird/period", False, "feed_data_missing")
        feed_conversion_metric = MetricResult(None, "kg/dozen", False, "feed_data_missing")
        feed_cost_metric = MetricResult(None, "currency/egg", False, "feed_data_missing")
    elif feed_records_in_kg != feed_records:
        feed_bird_metric = MetricResult(None, "kg/bird/period", False, "feed_unit_not_kg_or_unconfirmed")
        feed_conversion_metric = MetricResult(None, "kg/dozen", False, "feed_unit_not_kg_or_unconfirmed")
        feed_cost_metric = MetricResult(None, "currency/egg", False, "feed_unit_not_kg_or_unconfirmed")
    else:
        feed_bird_metric = (
            MetricResult(None, "kg/bird/period", False, "average_live_birds_missing")
            if average_birds is None
            else feed_per_bird(feed_kg, average_birds)
        )
        feed_conversion_metric = feed_conversion(feed_kg, egg_count)
        feed_cost_metric = (
            MetricResult(None, "currency/egg", False, "feed_cost_unconfirmed")
            if costed_feed_records != feed_records
            else feed_cost_per_egg(confirmed_feed_cost, int(metric_row.saleable_egg_count))
        )
    values["poultry_metrics"] = {
        "posture": (
            MetricResult(None, "eggs/bird/period", False, "average_live_birds_missing")
            if average_birds is None
            else posture_rate(egg_count, average_birds)
        ),
        "feed_per_bird": feed_bird_metric,
        "feed_conversion": feed_conversion_metric,
        "feed_cost_per_egg": feed_cost_metric,
        "average_ticket": average_ticket(Decimal(row.total), int(row.count)),
        "new_customers": (
            MetricResult(None, "customers", False, "customer_identity_missing")
            if int(metric_row.unassigned_invoice_count) > 0
            else MetricResult(Decimal(metric_row.new_customer_count), "customers", True)
        ),
        "stock_coverage": MetricResult(None, "days", False, "historical_sales_conversion_missing"),
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
