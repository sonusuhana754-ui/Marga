"""Tests for the deterministic benchmark runner."""

import networkx as nx
import pytest

from app.algorithms.base import Solver
from app.algorithms.benchmark import run_benchmark
from app.algorithms.models import RoutePlan, Scenario, Solution, Stop, Vehicle
from app.algorithms.ortools_solver import ORToolsSolver
from app.algorithms.scenario import make_scenario


def _grid_graph(num_nodes: int = 8) -> nx.MultiDiGraph:
    G = nx.MultiDiGraph()
    side = 3
    for idx in range(num_nodes):
        x = (idx % side) * 0.001
        y = (idx // side) * 0.001
        G.add_node(idx, x=x, y=y)
    edges = [
        (0, 1, 100.0), (1, 2, 100.0), (3, 4, 100.0), (4, 5, 100.0),
        (6, 7, 100.0), (0, 3, 100.0), (1, 4, 100.0), (2, 5, 100.0),
        (3, 6, 100.0), (4, 7, 100.0),
    ]
    for u, v, length in edges:
        tt = length / (50.0 * 1000.0 / 3600.0)
        G.add_edge(u, v, length=length, travel_time=tt)
        G.add_edge(v, u, length=length, travel_time=tt)
    return G


class _ConstantSolver(Solver):
    """A fake solver with a deterministic, constant cost."""

    solver_id = "constant"

    def __init__(self, scenario: Scenario, cost: float = 100.0) -> None:
        super().__init__(scenario)
        self._cost = cost

    def solve(self) -> Solution:
        return Solution(
            routes=[
                RoutePlan(
                    vehicle_id=0,
                    stop_sequence=[0, 1, 0],
                    load=1,
                    distance_m=100.0,
                    time_s=10.0,
                )
            ],
            total_cost=self._cost,
            total_distance_m=100.0,
            total_time_s=10.0,
            feasible=True,
        )


class _WorseSolver(_ConstantSolver):
    """A fake solver always worse than _ConstantSolver."""

    solver_id = "worse"

    def __init__(self, scenario: Scenario) -> None:
        super().__init__(scenario, cost=150.0)


class TestBenchmarkRunner:
    """Deterministic repeated-run metrics and fair comparison."""

    def test_scenario_is_deterministic_given_seed(self):
        G = _grid_graph()
        s1 = make_scenario(G, seed=11, capacity=10, vehicles=2, num_stops=4)
        s2 = make_scenario(G, seed=11, capacity=10, vehicles=2, num_stops=4)
        assert [st.id for st in s1.stops] == [st.id for st in s2.stops]
        assert [st.demand for st in s1.stops] == [st.demand for st in s2.stops]
        assert s1.depot == s2.depot

    def test_best_known_is_minimum_across_solvers(self):
        G = _grid_graph()
        scenario = make_scenario(G, seed=5, capacity=10, vehicles=3, num_stops=5)
        summary = run_benchmark(
            [_WorseSolver, _ConstantSolver],
            scenario,
            repeats=2,
        )
        # 100.0 is the constant cheaper cost; worse is 150.0
        assert summary.best_known == 100.0
        result_by_id = {r.solver_id: r for r in summary.results}
        assert result_by_id["constant"].gap_pct == pytest.approx(0.0)
        assert result_by_id["worse"].gap_pct == pytest.approx(50.0)  # (150-100)/100*100

    def test_gap_pct_formula(self):
        G = _grid_graph()
        scenario = make_scenario(G, seed=9, capacity=10, vehicles=2, num_stops=3)
        summary = run_benchmark([_WorseSolver, _ConstantSolver], scenario, repeats=1)
        worse = [r for r in summary.results if r.solver_id == "worse"][0]
        assert worse.cost == 150.0
        assert worse.gap_pct == 50.0

    def test_runs_aggregate_mean_and_std(self):
        G = _grid_graph()
        scenario = make_scenario(G, seed=3, capacity=10, vehicles=2, num_stops=3)
        summary = run_benchmark([_ConstantSolver], scenario, repeats=3)
        result = summary.results[0]
        assert len(result.runs) == 3
        # All runs identical for the constant solver.
        assert all(r.cost == 100.0 for r in result.runs)
        assert result.cost_std == 0.0
        assert result.cost_mean == 100.0

    def test_ortools_runs_in_benchmark(self):
        G = _grid_graph()
        scenario = make_scenario(G, seed=13, capacity=10, vehicles=2, num_stops=3)
        summary = run_benchmark([ORToolsSolver], scenario, repeats=2)
        result = summary.results[0]
        assert result.solver_id == "ortools"
        assert result.feasible is True
        assert len(result.runs) == 2
        assert result.cost > 0
        assert result.runtime_ms >= 0
