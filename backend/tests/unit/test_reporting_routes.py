from decimal import Decimal

from avicola_pro.modules.reporting.api.routes import DashboardResponse, dashboard_payload
from avicola_pro.modules.reporting.domain.poultry_metrics import MetricResult


def test_dashboard_payload_preserves_counts_and_serializes_available_and_missing_metrics() -> None:
    payload = dashboard_payload(
        {
            "sales_documents": 4,
            "sales_total": Decimal("125.50"),
            "inventory_value": Decimal("50"),
            "live_birds": Decimal("1000"),
            "accounts_payable": Decimal("0"),
            "accounts_receivable": Decimal("0"),
            "cash_balance": Decimal("0"),
            "confirmed_costs": Decimal("125"),
            "poultry_metrics": {
                "posture": MetricResult(Decimal("0.9"), "eggs/bird/period", True),
                "feed_per_bird": MetricResult(None, "kg/bird/period", False, "feed_data_missing"),
            },
        }
    )

    response = DashboardResponse(**payload)

    assert response.sales_documents == 4
    assert response.sales_total == "125.50"
    assert response.poultry_metrics["posture"].value == "0.9"
    assert response.poultry_metrics["feed_per_bird"].value is None
    assert response.poultry_metrics["feed_per_bird"].reason == "feed_data_missing"
