"""Tests for the common solver interface contract."""

import networkx as nx
import pytest

from app.algorithms.base import Solver
from app.algorithms.models import DEPOT_INDEX, RoutePlan, Scenario, Solution, Stop, Vehicle


class TestSolverInterface:
    """A minimal fake solver must satisfy the single static contract."""

    def test_interface_requires_solve(self):
        """A subclass that does not override solve() cannot be instantiated."""
        class Incomplete(Solver):
            solver_id = "incomplete"

        with pytest.raises(TypeError):
            Incomplete(None)  # type: ignore[arg-type]

    def test_solver_binds_scenario(self):
        """Solver stores the scenario it is constructed with."""
        scenario = _dummy_scenario()

        class DummySolver(Solver):
            solver_id = "dummy"

            def solve(self) -> Solution:
                return Solution(feasible=True)

        dummy = DummySolver(scenario)
        assert dummy.scenario is scenario

    def test_solver_id_and_solve_contract(self):
        """solve() returns a Solution with a depot-first/last route shape."""
        scenario = _dummy_scenario()

        class DummySolver(Solver):
            solver_id = "dummy"

            def solve(self) -> Solution:
                return Solution(
                    routes=[RoutePlan(vehicle_id=0, stop_sequence=[0, 1, 2, 0], load=5)],
                    total_cost=10.0,
                    total_distance_m=100.0,
                    total_time_s=10.0,
                    feasible=True,
                )

        sol = DummySolver(scenario).solve()
        assert sol.feasible is True
        assert sol.vehicles_used == 1
        assert sol.routes[0].stop_sequence[0] == DEPOT_INDEX
        assert sol.routes[0].stop_sequence[-1] == DEPOT_INDEX


def _dummy_scenario() -> Scenario:
    G = nx.MultiDiGraph()
    for nid, (x, y) in [(0, (0.0, 0.0)), (1, (0.001, 0.001)), (2, (0.002, 0.002))]:
        G.add_node(nid, x=x, y=y)
    G.add_edge(0, 1, length=100.0, travel_time=7.2)
    G.add_edge(1, 2, length=100.0, travel_time=7.2)
    G.add_edge(1, 0, length=100.0, travel_time=7.2)
    G.add_edge(2, 1, length=100.0, travel_time=7.2)
    stops = [
        Stop(id=0, lng=0.0, lat=0.0, x=0.0, y=0.0, demand=0),
        Stop(id=1, lng=0.001, lat=0.001, x=0.001, y=0.001, demand=3),
        Stop(id=2, lng=0.002, lat=0.002, x=0.002, y=0.002, demand=4),
    ]
    return Scenario(
        graph=G,
        stops=stops,
        vehicles=[Vehicle(id=0, capacity=10)],
        depot=stops[0],
        seed=42,
    )
