from __future__ import annotations

from datetime import date, timedelta
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
    stock_coverage_days,
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
    if filters.channel is not None:
        sales_clause += " and channel = :channel"
        params["channel"] = filters.channel
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
    metric_params: dict[str, Any] = {
        "date_from": filters.date_from or date.min,
        "date_to": filters.date_to or date.max,
        "channel_filter_enabled": filters.channel is not None,
        "channel": filters.channel or "",
    }
    coverage_to = filters.date_to or date.today()
    metric_params["coverage_from"] = coverage_to - timedelta(days=29)
    metric_params["coverage_to"] = coverage_to
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
               join inventory_movements im on im.id = fc.inventory_movement_id
               join inventory_documents d on d.id = im.document_id
               where d.status = 'CONFIRMED' and im.movement_type = 'ISSUE'
                 and im.reversal_of_id is null
                 and fc.occurred_on >= :date_from
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
                 and not exists (
                   select 1 from inventory_documents reversed_document
                   where reversed_document.id = c.inventory_document_id
                     and reversed_document.status = 'REVERSED'
                 )
                 and not exists (select 1 from egg_production_events reversal where reversal.reversal_of_id = pe.id)
                 and pe.occurred_on >= :date_from
                 and pe.occurred_on <= :date_to) as saleable_egg_count,
              (select count(*) from (
                 select distinct on (customer_id) customer_id, document_date as first_invoice,
                        channel as first_channel
                 from commercial_documents
                 where status = 'ISSUED' and document_type = 'INVOICE' and customer_id is not null
                 order by customer_id, document_date, id
               ) first_invoices
                 where first_invoice >= :date_from
                 and first_invoice <= :date_to
                 and (not :channel_filter_enabled or first_channel = :channel)
               ) as new_customer_count,
              (select count(*) from commercial_documents
               where status = 'ISSUED' and document_type = 'INVOICE' and customer_id is null
                 and document_date <= :date_to
                 and (not :channel_filter_enabled or channel = :channel)) as unassigned_invoice_count,
              (select coalesce(sum(ib.quantity), 0) from inventory_balances ib
               join products p on p.id = ib.product_id
               join egg_categories ec on ec.product_id = p.id
               where p.base_unit_code = 'unit' and ec.is_saleable and ec.is_active) as saleable_egg_stock,
              (select coalesce(sum(
                 case when d.document_type = 'CREDIT_NOTE' then -line.quantity else line.quantity end
               ), 0)
               from commercial_documents d
               join commercial_document_lines line on line.commercial_document_id = d.id
               join products p on p.id = line.product_id
               join egg_categories ec on ec.product_id = p.id
               where d.status = 'ISSUED' and d.document_type in ('INVOICE', 'CREDIT_NOTE')
                 and p.base_unit_code = 'unit' and ec.is_saleable and ec.is_active
                 and d.document_date >= :coverage_from and d.document_date <= :coverage_to
                 and (not :channel_filter_enabled or d.channel = :channel)) as net_egg_sales_30d
            """
        ),
        metric_params,
    )
    metric_row = metrics.one()
    egg_count = int(metric_row.egg_count)
    saleable_egg_stock = Decimal(metric_row.saleable_egg_stock)
    net_egg_sales_30d = Decimal(metric_row.net_egg_sales_30d)
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
        "stock_coverage": (
            MetricResult(None, "days", False, "net_egg_sales_last_30_days_nonpositive")
            if net_egg_sales_30d < 0
            else stock_coverage_days(saleable_egg_stock, net_egg_sales_30d)
        ),
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

    mortality_result = await session.execute(
        text(
            """
            select occurred_on, sum(quantity) as deaths
            from mortality_events event
            where event.status = 'CONFIRMED' and event.reversal_of_id is null
              and not exists (
                select 1 from mortality_events reversal
                where reversal.reversal_of_id = event.id and reversal.status = 'CONFIRMED'
              )
              and event.occurred_on >= :date_from and event.occurred_on <= :date_to
            group by occurred_on
            order by occurred_on
            """
        ),
        {"date_from": filters.date_from or date.min, "date_to": filters.date_to or date.max},
    )
    values["daily_mortality"] = [
        {"occurred_on": item["occurred_on"], "deaths": Decimal(item["deaths"])}
        for item in mortality_result.mappings()
    ]

    age_as_of = date.today()
    flock_result = await session.execute(
        text("select code, entry_date from flocks where status = 'ACTIVE' and entry_date <= :as_of order by code"),
        {"as_of": age_as_of},
    )
    values["active_flock_ages"] = [
        {
            "flock_code": item["code"],
            "days_since_entry": (age_as_of - item["entry_date"]).days,
            "as_of": age_as_of,
        }
        for item in flock_result.mappings()
    ]
    feed_by_house_result = await session.execute(
        text(
            """
            select h.code as house_code, p.base_unit_code as unit_code, sum(fc.quantity) as quantity
            from feed_consumption fc
            join products p on p.id = fc.product_id
            join inventory_movements im on im.id = fc.inventory_movement_id
            join inventory_documents d on d.id = im.document_id
            left join houses h on h.id = fc.house_id
            where d.status = 'CONFIRMED' and im.movement_type = 'ISSUE'
              and im.reversal_of_id is null
              and fc.occurred_on >= :date_from and fc.occurred_on <= :date_to
            group by h.code, p.base_unit_code
            order by h.code nulls last, p.base_unit_code
            """
        ),
        {"date_from": filters.date_from or date.min, "date_to": filters.date_to or date.max},
    )
    values["feed_consumption_by_house"] = [
        {
            "house_code": item["house_code"],
            "unit_code": item["unit_code"],
            "quantity": Decimal(item["quantity"]),
        }
        for item in feed_by_house_result.mappings()
    ]
    return values


async def profitability(session: Any, filters: ReportFilter) -> tuple[list[dict[str, Any]], int]:
    clause, params = _date_clause("document_date", filters)
    if filters.channel is not None:
        clause += " and channel = :channel"
        params["channel"] = filters.channel
    count_result = await session.execute(
        text("select count(*) from commercial_documents where status = 'ISSUED'" + clause),  # noqa: S608
        params.copy(),
    )
    total = int(count_result.scalar_one())
    page_params = params | {"offset": filters.offset, "limit": filters.limit}
    result = await session.execute(
        text(
            "select id, document_date, document_type, channel, customer_name_snapshot, "
            "case when document_type = 'CREDIT_NOTE' then -total else total end as net_total "
            "from commercial_documents where status = 'ISSUED'"
            + clause
            + " order by document_date desc, id desc offset :offset limit :limit"
        ),
        page_params,
    )
    rows = []
    for item in result.mappings():
        rows.append(
            {
                "id": item["id"],
                "date": item["document_date"],
                "document_type": item["document_type"],
                "channel": item["channel"] or "LEGACY_UNCLASSIFIED",
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

