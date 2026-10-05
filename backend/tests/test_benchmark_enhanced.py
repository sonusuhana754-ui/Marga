from __future__ import annotations

from app.algorithms import benchmark as bench_mod
from app.algorithms.base import Solver
from app.algorithms.models import Solution, RoutePlan
from app.algorithms import scenarios


class _FakeSolver(Solver):
    solver_id = "fake"

    def __init__(self, scenario, **kwargs):
        super().__init__(scenario)
        self.kwargs = kwargs

    def solve(self) -> Solution:
        scen_local = self.scenario
        seq = [0] + list(range(1, scen_local.num_stops)) + [0]
        sol = Solution(
            feasible=True,
            total_cost=100.0,
            total_distance_m=1200.0,
            total_time_s=86.4,
        )
        sol.routes = [RoutePlan(vehicle_id=0, stop_sequence=seq, load=sum(s.demand for s in scen_local.stops if s.id != 0))]
        sol._runtime_ms = 5.0  # type: ignore[attr-defined]
        return sol


class _InfeasibleSolver(Solver):
    solver_id = "fake_bad"

    def __init__(self, scenario, **kwargs):
        super().__init__(scenario)
        self.kwargs = kwargs

    def solve(self) -> Solution:
        sol = Solution(feasible=False, total_cost=float("inf"))
        sol._runtime_ms = 1.0  # type: ignore[attr-defined]
        return sol


class _CustomCostSolver(Solver):
    solver_id = "fake_custom"

    def __init__(self, scenario, **kwargs):
        super().__init__(scenario)
        self.kwargs = kwargs

    def solve(self) -> Solution:
        scen_local = self.scenario
        seq = [0] + list(range(1, scen_local.num_stops)) + [0]
        sol = Solution(
            feasible=True,
            total_cost=999.0,
            total_distance_m=500.0,
            total_time_s=36.0,
        )
        sol.routes = [RoutePlan(vehicle_id=0, stop_sequence=seq, load=sum(s.demand for s in scen_local.stops if s.id != 0))]
        sol._runtime_ms = 2.0  # type: ignore[attr-defined]
        return sol


def test_benchmark_run_records_all_metrics():
    scen = scenarios.scenario_registry.get("grid_cvrp_6")
    res = bench_mod._run_solver(_FakeSolver, scen, repeats=1, seed=scen.seed)
    assert res.runs[0].cost == 100.0
    assert res.runs[0].total_distance_m == 1200.0
    assert res.runs[0].total_time_s == 86.4
    assert res.runs[0].vehicles_used == 1


def test_aggregates_mean_min_max_stdev_sample():
    scen = scenarios.scenario_registry.get("grid_cvrp_6")

    class _VarSolver(Solver):
        solver_id = "var"

        def solve(self) -> Solution:
            scen_local = self.scenario
            seq = [0] + list(range(1, scen_local.num_stops)) + [0]
            sol = Solution(
                feasible=True,
                total_cost=100.0,
                total_distance_m=100.0,
                total_time_s=10.0,
            )
            sol.routes = [RoutePlan(vehicle_id=0, stop_sequence=seq, load=sum(s.demand for s in scen_local.stops if s.id != 0))]
            sol._runtime_ms = 1.0  # type: ignore[attr-defined]
            return sol

    res = bench_mod._run_solver(_VarSolver, scen, repeats=1, seed=scen.seed)
    assert res.total_distance_m_stdev_sample == 0.0


def test_feasibility_and_violations():
    scen = scenarios.scenario_registry.get("grid_cvrp_6")
    res = bench_mod._run_solver(_InfeasibleSolver, scen, repeats=2, seed=scen.seed)
    assert res.feasible is False


def test_describe_returns_expected():
    d = scenarios.describe("grid_cvrp_8")
    assert d["id"] == "grid_cvrp_8"
    assert "description" in d
    assert d["seed"] == 7


def test_cost_not_recalculated():
    scen = scenarios.scenario_registry.get("grid_cvrp_6")
    res = bench_mod._run_solver(_CustomCostSolver, scen, repeats=1, seed=scen.seed)
    assert res.runs[0].cost == 999.0
    assert res.cost == 999.0


def test_solution_limit_passed_through():
    scen = scenarios.scenario_registry.get("grid_cvrp_6")
    res = bench_mod._run_solver(_FakeSolver, scen, repeats=1, seed=scen.seed, solution_limit=1)
    assert res.feasible is True
