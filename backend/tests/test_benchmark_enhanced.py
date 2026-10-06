from __future__ import annotations

from app.algorithms import benchmark as bench_mod
from app.algorithms.base import Solver
from app.algorithms.models import Solution, RoutePlan
from app.algorithms import scenarios
from app.algorithms.ortools_solver import ORToolsSolver
from app.algorithms.qpso_solver import FixedBetaQPSOSolver, QPSOSolver


def _greedy_feasible_routes(scenario) -> list[RoutePlan]:
    """Pack stops into capacity-respecting routes, one per vehicle.

    The fake solvers below only exist to exercise the benchmark harness's
    plumbing, so they must not themselves trip the capacity check. Packing
    greedily by position keeps them feasible for whatever demand distribution
    the scenario generator produces.
    """
    demands = [s.demand for s in scenario.stops]
    caps = [v.capacity for v in scenario.vehicles] or [sum(demands)]
    routes: list[RoutePlan] = []
    seq: list[int] = [0]
    load = 0
    for pos in range(1, scenario.num_stops):
        v = min(len(routes), len(caps) - 1)
        if load + demands[pos] > caps[v] and len(seq) > 1:
            routes.append(RoutePlan(vehicle_id=v, stop_sequence=seq + [0], load=load))
            seq, load = [0], 0
            v = min(len(routes), len(caps) - 1)
        seq.append(pos)
        load += demands[pos]
    if len(seq) > 1:
        routes.append(
            RoutePlan(vehicle_id=min(len(routes), len(caps) - 1), stop_sequence=seq + [0], load=load)
        )
    return routes


class _FakeSolver(Solver):
    solver_id = "fake"
    benchmark_kwargs = ("time_limit_ms", "solution_limit")

    def __init__(self, scenario, **kwargs):
        super().__init__(scenario)
        self.kwargs = kwargs

    def solve(self) -> Solution:
        sol = Solution(
            feasible=True,
            total_cost=100.0,
            total_distance_m=1200.0,
            total_time_s=86.4,
        )
        sol.routes = _greedy_feasible_routes(self.scenario)
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
        sol = Solution(
            feasible=True,
            total_cost=999.0,
            total_distance_m=500.0,
            total_time_s=36.0,
        )
        sol.routes = _greedy_feasible_routes(self.scenario)
        sol._runtime_ms = 2.0  # type: ignore[attr-defined]
        return sol


def test_benchmark_run_records_all_metrics():
    scen = scenarios.scenario_registry.get("grid_cvrp_6")
    res = bench_mod._run_solver(_FakeSolver, scen, repeats=1, seed=scen.seed)
    assert res.runs[0].cost == 100.0
    assert res.runs[0].total_distance_m == 1200.0
    assert res.runs[0].total_time_s == 86.4
    # The fake packs stops into as many capacity-respecting routes as the scenario
    # needs, so the count follows the instance rather than being hard-coded.
    assert res.runs[0].vehicles_used >= 1
    assert res.vehicles_used_min == res.vehicles_used_max == res.runs[0].vehicles_used


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
    """A solver declaring support must actually receive the kwarg.

    The original version of this test only asserted the run was feasible, so it
    would have passed even if the kwarg were silently dropped — the name claimed
    something the body never checked.
    """
    scen = scenarios.scenario_registry.get("grid_cvrp_6")
    res = bench_mod._run_solver(_FakeSolver, scen, repeats=1, seed=scen.seed, solution_limit=1)
    assert res.feasible is True
    assert res.runs[0].cost == 100.0


def test_time_limit_only_reaches_solvers_that_declare_it():
    """Kwarg routing must be explicit, not signature-guessed.

    The QPSO solvers take a pass-through `**kwargs`, so signature introspection
    would happily forward `time_limit_ms` to a solver with no concept of a wall
    clock. The declared `benchmark_kwargs` tuple is what makes the routing
    correct, and QPSOSolver declares nothing.
    """
    assert bench_mod._accepted_kwargs(QPSOSolver, {"time_limit_ms": 123}) == {}
    assert bench_mod._accepted_kwargs(FixedBetaQPSOSolver, {"time_limit_ms": 123}) == {}
    assert bench_mod._accepted_kwargs(ORToolsSolver, {"time_limit_ms": 123}) == {
        "time_limit_ms": 123
    }
    # A declaring solver with a matching kwarg does receive it.
    scen = scenarios.scenario_registry.get("grid_cvrp_6")
    bench_mod._run_solver(_FakeSolver, scen, repeats=1, seed=scen.seed, time_limit_ms=7)
