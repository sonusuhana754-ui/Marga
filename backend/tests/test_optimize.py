"""Tests for the POST /api/v1/optimize endpoint.

The scenarios are deterministic and in-code (the solver-library registry), so
no OSMnx or graph-cache mocking is required. We test the HTTP contract and error
responses against the real registry and OR-Tools baseline.
"""

import pytest
from fastapi.testclient import TestClient

from app.algorithms.scenarios import scenario_registry
from app.core.config import settings


def _url() -> str:
    return f"{settings.API_V1_STR}/optimize"


class TestSolverAvailability:
    """Every registered solver id must actually be runnable end to end.

    This is the test that would have caught the original problem: the headline
    algorithm existed only in documentation while the API advertised a single
    solver and returned 422 for its own name.
    """

    @pytest.mark.parametrize("solver", ["ortools", "qpso", "va_qpso"])
    def test_solver_runs(self, client: TestClient, solver):
        resp = client.post(
            _url(),
            json={"mode": "named", "scenario_id": "grid_cvrp_8", "solver": solver},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["solver"] == solver
        assert body["feasible"] is True
        assert body["total_cost"] > 0
        assert body["runtime_ms"] > 0
        assert len(body["routes"]) >= 1

    def test_solver_listing_endpoint(self, client: TestClient):
        resp = client.get("/api/v1/benchmark/solvers")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == {"ortools", "qpso", "va_qpso"}
        assert body["va_qpso"]["is_metaheuristic"] is True
        assert body["ortools"]["is_metaheuristic"] is False


class TestOptimizeSuccess:
    """Successful solve over a named scenario."""

    def test_returns_successful_response(self, client: TestClient):
        resp = client.post(
            _url(),
            json={"mode": "named", "scenario_id": "grid_cvrp_8", "solver": "ortools"},
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
        """No fabricated telemetry fields.

        `impact` and `run_id` are never synthesised. `convergence` is present only
        when a solver reported a real trace, and empty for OR-Tools, which
        produces no per-iteration trace — an empty list, not a fabricated curve.
        """
        resp = client.post(
            _url(),
            json={"mode": "named", "scenario_id": "grid_cvrp_6", "solver": "ortools"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["convergence"] == []
        assert "impact" not in body
        assert "run_id" not in body

    def test_qpso_reports_measured_convergence(self, client: TestClient):
        """The QPSO variants report a real, monotonically non-increasing trace."""
        resp = client.post(
            _url(),
            json={"mode": "named", "scenario_id": "grid_cvrp_6", "solver": "va_qpso"},
        )
        assert resp.status_code == 200
        body = resp.json()
        trace = body["convergence"]
        assert len(trace) >= 2, "expected a per-iteration trace"
        costs = [p["best_cost"] for p in trace]
        assert costs == sorted(costs, reverse=True), "best-so-far cannot increase"
        assert costs[-1] >= 0.0
        assert body["solver_diagnostics"]["iterations"] == len(trace) - 1

    def test_vrptw_scenario_supported(self, client: TestClient):
        resp = client.post(
            _url(),
            json={"mode": "named", "scenario_id": "grid_vrptw_8", "solver": "ortools"},
        )
        assert resp.status_code == 200
        assert resp.json()["scenario_id"] == "grid_vrptw_8"


class TestOptimizeDeterminism:
    """Same scenario + seed must be reproducible."""

    def test_same_input_same_cost(self, client: TestClient):
        payload = {"mode": "named", "scenario_id": "grid_cvrp_8", "solver": "ortools", "seed": 42}
        r1 = client.post(_url(), json=payload).json()
        r2 = client.post(_url(), json=payload).json()
        assert r1["total_cost"] == r2["total_cost"]


class TestOptimizeValidation:
    """Clear validation responses."""

    def test_unsupported_solver_returns_422(self, client: TestClient):
        resp = client.post(
            _url(),
            json={"mode": "named", "scenario_id": "grid_cvrp_8", "solver": "dijkstra_astar"},
        )
        assert resp.status_code == 422

    def test_unknown_scenario_returns_422(self, client: TestClient):
        resp = client.post(
            _url(),
            json={"mode": "named", "scenario_id": "does_not_exist", "solver": "ortools"},
        )
        assert resp.status_code == 422
        assert "does_not_exist" in resp.json()["detail"]

    def test_missing_required_fields_returns_422(self, client: TestClient):
        resp = client.post(_url(), json={})
        assert resp.status_code == 422

    def test_negative_seed_returns_422(self, client: TestClient):
        resp = client.post(
            _url(),
            json={"mode": "named", "scenario_id": "grid_cvrp_8", "solver": "ortools", "seed": -1},
        )
        assert resp.status_code == 422


class TestCustomOptimizeSuccess:
    """Successful solve over a custom static scenario."""

    def test_custom_cvrp_simple(self, client: TestClient):
        payload = {
            "mode": "custom",
            "solver": "ortools",
            "seed": 123,
            "depot": {"id": 0, "lng": -74.006, "lat": 40.7128, "demand": 0},
            "stops": [
                {"id": 1, "lng": -74.001, "lat": 40.7138, "demand": 2},
                {"id": 2, "lng": -74.011, "lat": 40.7118, "demand": 3},
            ],
            "vehicles": [
                {"id": 0, "capacity": 5},
                {"id": 1, "capacity": 5},
            ],
        }
        resp = client.post(_url(), json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["solver"] == "ortools"
        assert body["scenario_id"] == "custom"
        assert body["total_cost"] > 0
        assert body["runtime_ms"] >= 0
        assert body["vehicles_used"] >= 1
        assert len(body["routes"]) >= 1
        for route in body["routes"]:
            assert route["vehicle_id"] >= 0
            assert route["stop_sequence"][0] == 0
            assert route["stop_sequence"][-1] == 0
            assert route["load"] >= 0
            assert route["distance_m"] >= 0
            assert route["time_s"] >= 0

    def test_custom_cvrp_uniform_capacities_all_stops_covered(self, client: TestClient):
        payload = {
            "mode": "custom",
            "solver": "ortools",
            "depot": {"id": 0, "lng": 0.0, "lat": 0.0, "demand": 0},
            "stops": [
                {"id": 1, "lng": 0.001, "lat": 0.0, "demand": 1},
                {"id": 2, "lng": 0.0, "lat": 0.001, "demand": 2},
                {"id": 3, "lng": -0.001, "lat": 0.0, "demand": 1},
            ],
            "vehicles": [
                {"id": 0, "capacity": 10},
            ],
        }
        resp = client.post(_url(), json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["vehicles_used"] >= 1

    def test_custom_vrptw_valid(self, client: TestClient):
        payload = {
            "mode": "custom",
            "solver": "ortools",
            "seed": 42,
            "depot": {"id": 0, "lng": 0.0, "lat": 0.0, "demand": 0},
            "stops": [
                {"id": 1, "lng": 0.002, "lat": 0.0, "demand": 1},
                {"id": 2, "lng": 0.0, "lat": 0.002, "demand": 1},
            ],
            "vehicles": [
                {"id": 0, "capacity": 5},
            ],
            "time_windows": [
                {"stop_id": 0, "earliest": 0.0, "latest": 1000.0},
                {"stop_id": 1, "earliest": 0.0, "latest": 1000.0},
                {"stop_id": 2, "earliest": 0.0, "latest": 1000.0},
            ],
        }
        resp = client.post(_url(), json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["scenario_id"] == "custom"

    def test_custom_determinism(self, client: TestClient):
        payload = {
            "mode": "custom",
            "solver": "ortools",
            "seed": 7,
            "depot": {"id": 0, "lng": 1.0, "lat": 2.0, "demand": 0},
            "stops": [
                {"id": 1, "lng": 1.001, "lat": 2.0, "demand": 3},
                {"id": 2, "lng": 1.0, "lat": 2.001, "demand": 2},
            ],
            "vehicles": [
                {"id": 0, "capacity": 10},
            ],
        }
        r1 = client.post(_url(), json=payload).json()
        r2 = client.post(_url(), json=payload).json()
        assert r1["total_cost"] == r2["total_cost"]


class TestCustomOptimizeValidation:
    """Validation for custom scenarios."""

    def test_negative_capacity_rejected(self, client: TestClient):
        payload = {
            "mode": "custom",
            "solver": "ortools",
            "depot": {"id": 0, "lng": 0.0, "lat": 0.0, "demand": 0},
            "stops": [
                {"id": 1, "lng": 0.001, "lat": 0.0, "demand": 1},
            ],
            "vehicles": [
                {"id": 0, "capacity": -5},
            ],
        }
        resp = client.post(_url(), json=payload)
        assert resp.status_code == 422

    def test_zero_capacity_rejected(self, client: TestClient):
        payload = {
            "mode": "custom",
            "solver": "ortools",
            "depot": {"id": 0, "lng": 0.0, "lat": 0.0, "demand": 0},
            "stops": [
                {"id": 1, "lng": 0.001, "lat": 0.0, "demand": 1},
            ],
            "vehicles": [
                {"id": 0, "capacity": 0},
            ],
        }
        resp = client.post(_url(), json=payload)
        assert resp.status_code == 422

    def test_depot_demand_nonzero_rejected(self, client: TestClient):
        payload = {
            "mode": "custom",
            "solver": "ortools",
            "depot": {"id": 0, "lng": 0.0, "lat": 0.0, "demand": 5},
            "stops": [
                {"id": 1, "lng": 0.001, "lat": 0.0, "demand": 1},
            ],
            "vehicles": [
                {"id": 0, "capacity": 10},
            ],
        }
        resp = client.post(_url(), json=payload)
        assert resp.status_code == 422

    def test_total_capacity_less_than_demand_rejected(self, client: TestClient):
        payload = {
            "mode": "custom",
            "solver": "ortools",
            "depot": {"id": 0, "lng": 0.0, "lat": 0.0, "demand": 0},
            "stops": [
                {"id": 1, "lng": 0.001, "lat": 0.0, "demand": 5},
            ],
            "vehicles": [
                {"id": 0, "capacity": 3},
            ],
        }
        resp = client.post(_url(), json=payload)
        assert resp.status_code == 422

    def test_invalid_time_window_earliest_greater_than_latest_rejected(self, client: TestClient):
        payload = {
            "mode": "custom",
            "solver": "ortools",
            "depot": {"id": 0, "lng": 0.0, "lat": 0.0, "demand": 0},
            "stops": [
                {"id": 1, "lng": 0.001, "lat": 0.0, "demand": 1},
            ],
            "vehicles": [
                {"id": 0, "capacity": 5},
            ],
            "time_windows": [
                {"stop_id": 1, "earliest": 100.0, "latest": 50.0},
            ],
        }
        resp = client.post(_url(), json=payload)
        assert resp.status_code == 422

    def test_time_window_references_unknown_stop_rejected(self, client: TestClient):
        payload = {
            "mode": "custom",
            "solver": "ortools",
            "depot": {"id": 0, "lng": 0.0, "lat": 0.0, "demand": 0},
            "stops": [
                {"id": 1, "lng": 0.001, "lat": 0.0, "demand": 1},
            ],
            "vehicles": [
                {"id": 0, "capacity": 5},
            ],
            "time_windows": [
                {"stop_id": 99, "earliest": 0.0, "latest": 100.0},
            ],
        }
        resp = client.post(_url(), json=payload)
        assert resp.status_code == 422

    def test_duplicate_stop_ids_rejected(self, client: TestClient):
        payload = {
            "mode": "custom",
            "solver": "ortools",
            "depot": {"id": 0, "lng": 0.0, "lat": 0.0, "demand": 0},
            "stops": [
                {"id": 0, "lng": 0.001, "lat": 0.0, "demand": 1},
            ],
            "vehicles": [
                {"id": 0, "capacity": 5},
            ],
        }
        resp = client.post(_url(), json=payload)
        assert resp.status_code == 422

    def test_duplicate_vehicle_ids_rejected(self, client: TestClient):
        payload = {
            "mode": "custom",
            "solver": "ortools",
            "depot": {"id": 0, "lng": 0.0, "lat": 0.0, "demand": 0},
            "stops": [
                {"id": 1, "lng": 0.001, "lat": 0.0, "demand": 1},
            ],
            "vehicles": [
                {"id": 0, "capacity": 5},
                {"id": 0, "capacity": 5},
            ],
        }
        resp = client.post(_url(), json=payload)
        assert resp.status_code == 422

    def test_invalid_latitude_rejected(self, client: TestClient):
        payload = {
            "mode": "custom",
            "solver": "ortools",
            "depot": {"id": 0, "lng": 0.0, "lat": 91.0, "demand": 0},
            "stops": [],
            "vehicles": [{"id": 0, "capacity": 5}],
        }
        resp = client.post(_url(), json=payload)
        assert resp.status_code == 422

    def test_invalid_longitude_rejected(self, client: TestClient):
        payload = {
            "mode": "custom",
            "solver": "ortools",
            "depot": {"id": 0, "lng": 181.0, "lat": 0.0, "demand": 0},
            "stops": [],
            "vehicles": [{"id": 0, "capacity": 5}],
        }
        resp = client.post(_url(), json=payload)
        assert resp.status_code == 422

    def test_negative_time_window_values_rejected(self, client: TestClient):
        payload = {
            "mode": "custom",
            "solver": "ortools",
            "depot": {"id": 0, "lng": 0.0, "lat": 0.0, "demand": 0},
            "stops": [{"id": 1, "lng": 0.001, "lat": 0.0, "demand": 1}],
            "vehicles": [{"id": 0, "capacity": 5}],
            "time_windows": [{"stop_id": 1, "earliest": -1.0, "latest": 10.0}],
        }
        resp = client.post(_url(), json=payload)
        assert resp.status_code == 422

    def test_duplicate_time_window_rejected(self, client: TestClient):
        payload = {
            "mode": "custom",
            "solver": "ortools",
            "depot": {"id": 0, "lng": 0.0, "lat": 0.0, "demand": 0},
            "stops": [{"id": 1, "lng": 0.001, "lat": 0.0, "demand": 1}],
            "vehicles": [{"id": 0, "capacity": 5}],
            "time_windows": [
                {"stop_id": 1, "earliest": 0.0, "latest": 10.0},
                {"stop_id": 1, "earliest": 0.0, "latest": 20.0},
            ],
        }
        resp = client.post(_url(), json=payload)
        assert resp.status_code == 422
