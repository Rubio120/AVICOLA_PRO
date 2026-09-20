from types import SimpleNamespace

from avicola_pro.modules.costing.api.routes import build_costing_router


def test_costing_router_exposes_protected_run_and_snapshot_endpoints() -> None:
    router = build_costing_router(SimpleNamespace(), SimpleNamespace(), SimpleNamespace(), SimpleNamespace(), "session")
    paths = {route.path for route in router.routes}
    assert {
        "/api/v1/costing/events",
        "/api/v1/costing/events/{event_id}/reverse",
        "/api/v1/costing/centers",
        "/api/v1/costing/runs",
        "/api/v1/costing/runs/{run_id}/calculate",
        "/api/v1/costing/runs/{run_id}/close",
        "/api/v1/costing/runs/{run_id}/profitability",
        "/api/v1/costing/runs/{run_id}/snapshots",
    } <= paths
