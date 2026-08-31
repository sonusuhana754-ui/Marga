"""Tests for the POST /api/v1/optimize endpoint.

The scenarios are deterministic and in-code (the solver-library registry), so
no OSMnx or graph-cache mocking is required. We test the HTTP contract and error
responses against the real registry and OR-Tools baseline.
"""

from fastapi.testclient import TestClient

from app.algorithms.scenarios import scenario_registry
from app.core.config import settings


def _url() -> str:
    return f"{settings.API_V1_STR}/optimize"


class TestOptimizeSuccess:
    """Successful solve over a named scenario."""

    def test_returns_successful_response(self, client: TestClient):
        resp = client.post(
            _url(),
            json={"scenario_id": "grid_cvrp_8", "solver": "ortools"},
        )
        assert resp.status_code == 200
        body = resp.json()

        assert body["solver"] == "ortools"
        assert body["scenario_id"] == "grid_cvrp_8"
        assert body["total_cost"] > 0
        assert body["runtime_ms"] >= 0
        assert body["vehicles_used"] >= 1
        assert len(body["routes"]) >= 1

        # Every route plan has the expected shape.
        for route in body["routes"]:
            assert route["vehicle_id"] >= 0
            assert route["stop_sequence"][0] == 0
            assert route["stop_sequence"][-1] == 0
            assert route["load"] >= 0
            assert route["distance_m"] >= 0
            assert route["time_s"] >= 0

    def test_response_has_no_placeholder_fields(self, client: TestClient):
        resp = client.post(
            _url(),
            json={"scenario_id": "grid_cvrp_6", "solver": "ortools"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "convergence" not in body
        assert "impact" not in body
        assert "run_id" not in body

    def test_vrptw_scenario_supported(self, client: TestClient):
        resp = client.post(
            _url(),
            json={"scenario_id": "grid_vrptw_8", "solver": "ortools"},
        )
        assert resp.status_code == 200
        assert resp.json()["scenario_id"] == "grid_vrptw_8"


class TestOptimizeDeterminism:
    """Same scenario + seed must be reproducible."""

    def test_same_input_same_cost(self, client: TestClient):
        payload = {"scenario_id": "grid_cvrp_8", "solver": "ortools", "seed": 42}
        r1 = client.post(_url(), json=payload).json()
        r2 = client.post(_url(), json=payload).json()
        assert r1["total_cost"] == r2["total_cost"]


class TestOptimizeValidation:
    """Clear validation responses."""

    def test_unsupported_solver_returns_422(self, client: TestClient):
        resp = client.post(
            _url(),
            json={"scenario_id": "grid_cvrp_8", "solver": "qpso"},
        )
        assert resp.status_code == 422

    def test_unknown_scenario_returns_422(self, client: TestClient):
        resp = client.post(
            _url(),
            json={"scenario_id": "does_not_exist", "solver": "ortools"},
        )
        assert resp.status_code == 422
        assert "does_not_exist" in resp.json()["detail"]

    def test_missing_required_fields_returns_422(self, client: TestClient):
        resp = client.post(_url(), json={})
        assert resp.status_code == 422

    def test_negative_seed_returns_422(self, client: TestClient):
        resp = client.post(
            _url(),
            json={"scenario_id": "grid_cvrp_8", "solver": "ortools", "seed": -1},
        )
        assert resp.status_code == 422


class TestScenarioRegistry:
    """The solver-library registry exposes known named scenarios."""

    def test_available_ids(self):
        available = scenario_registry.available_ids()
        assert "grid_cvrp_8" in available
        assert "grid_cvrp_6" in available
        assert "grid_vrptw_8" in available

    def test_get_unknown_raises(self):
        import pytest

        from app.algorithms.scenarios import scenario_registry

        with pytest.raises(KeyError):
            scenario_registry.get("nope")
