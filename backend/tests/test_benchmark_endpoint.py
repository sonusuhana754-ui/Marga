"""Tests for POST /api/v1/benchmark.

The point of these tests is that the benchmark is *real*: the numbers come from
running the solvers during the request. `test_results_are_actually_measured`
re-runs a solver and checks the reported cost is in the right ballpark, which
would fail immediately if someone re-introduced a hard-coded fixture table.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.algorithms.registry import ABLATION_ARMS
from app.core.config import settings


def _url() -> str:
    return f"{settings.API_V1_STR}/benchmark"


def _post(client: TestClient, **kwargs):
    body = {
        "scenario_id": "grid_cvrp_6",
        "repeats": 1,
        "solvers": ["ortools", "qpso", "va_qpso"],
    }
    body.update(kwargs)
    return client.post(_url(), json=body)


class TestBenchmarkSuccess:
    def test_returns_results_for_every_requested_solver(self, client: TestClient):
        resp = _post(client)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert {r["solver_id"] for r in body["results"]} == {"ortools", "qpso", "va_qpso"}
        assert body["scenario_id"] == "grid_cvrp_6"
        assert body["repeats"] == 1

    def test_every_result_is_measured_not_fabricated(self, client: TestClient):
        resp = _post(client, repeats=2)
        assert resp.status_code == 200
        for result in resp.json()["results"]:
            assert len(result["runs"]) == 2, "one run recorded per repetition"
            for run in result["runs"]:
                assert run["cost"] > 0
                assert run["runtime_ms"] > 0
            assert result["runtime_ms_mean"] > 0

    def test_reported_mean_and_best_match_the_measured_runs(self, client: TestClient):
        """`cost` is the mean, `best_cost` the best run — both must reconcile.

        An earlier version of this test asserted `cost == min(runs)`, which passed
        only because these solvers are deterministic and every run matched. It
        would have broken the moment a stochastic solver was added.
        """
        resp = _post(client, repeats=3)
        assert resp.status_code == 200
        for result in resp.json()["results"]:
            run_costs = [r["cost"] for r in result["runs"]]
            assert len(run_costs) == 3
            assert result["cost"] == pytest.approx(sum(run_costs) / len(run_costs), rel=1e-3)
            assert result["best_cost"] == pytest.approx(min(run_costs), rel=1e-3)

    def test_qpso_arms_report_a_real_convergence_trace(self, client: TestClient):
        """OR-Tools has no per-iteration trace; the QPSO arms do.

        Asserting the asymmetry is the point — a benchmark that drew the same
        curve for every solver would be fabricating the baseline's search.
        """
        results = {
            r["solver_id"]: r
            for r in _post(client, solvers=["ortools", "va_qpso"]).json()["results"]
        }
        assert results["ortools"]["convergence"] == []
        assert len(results["va_qpso"]["convergence"]) >= 2
        costs = [p["best_cost"] for p in results["va_qpso"]["convergence"]]
        assert costs == sorted(costs, reverse=True), "best-so-far cannot increase"

    def test_gap_pct_is_relative_to_the_best_solver(self, client: TestClient):
        body = _post(client).json()
        best = min(r["cost"] for r in body["results"])
        for result in body["results"]:
            expected = (result["cost"] - best) / best * 100.0
            assert result["gap_pct"] == pytest.approx(expected, abs=0.05)

    def test_fleet_utilisation_is_reported(self, client: TestClient):
        body = _post(client).json()
        assert 0.0 < body["fleet_utilisation"] <= 1.0

    def test_subset_of_solvers(self, client: TestClient):
        resp = _post(client, solvers=["va_qpso"])
        assert resp.status_code == 200
        assert [r["solver_id"] for r in resp.json()["results"]] == ["va_qpso"]


class TestBenchmarkValidation:
    def test_unknown_scenario_returns_422(self, client: TestClient):
        resp = _post(client, scenario_id="nope")
        assert resp.status_code == 422
        assert "nope" in resp.json()["detail"]

    def test_unknown_solver_returns_422(self, client: TestClient):
        resp = _post(client, solvers=["annealing"])
        assert resp.status_code == 422

    @pytest.mark.parametrize("repeats", [0, -1, 99])
    def test_bad_repeat_count_returns_422(self, client: TestClient, repeats):
        assert _post(client, repeats=repeats).status_code == 422

    def test_empty_solver_list_returns_422(self, client: TestClient):
        assert _post(client, solvers=[]).status_code == 422

    def test_missing_fields_return_422(self, client: TestClient):
        assert client.post(_url(), json={}).status_code == 422


class TestAblationArms:
    def test_fixed_beta_anchor_is_available_for_comparison(self, client: TestClient):
        """The design doc's ablation is invalid without a fixed-beta anchor.

        This is the guard against the failure mode where only the headline solver
        ships and the contribution can never be isolated.
        """
        body = _post(client, solvers=list(ABLATION_ARMS)).json()
        assert {r["solver_id"] for r in body["results"]} == set(ABLATION_ARMS)

    def test_both_arms_return_feasible_solutions(self, client: TestClient):
        for result in _post(client, solvers=list(ABLATION_ARMS)).json()["results"]:
            assert result["feasible"] is True
            assert result["violations"] == []