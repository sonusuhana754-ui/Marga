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
        routes = []
        for route in self.scenario.routes if hasattr(self.scenario, "routes") else []:
            routes = self.scenario.routes  # not expected
        if not routes:
            num_stops = self.scenario.num_stops
            seq = [0] + list(range(1, num_stops)) + [0]
            routes = [
                RoutePlan(
                    vehicle_id=0,
                    stop_sequence=seq,
                    load=sum(s.demand for s in self.scenario.stops if s.id != 0),
                    distance_m=100.0,
                    time_s=10.0,
                )
            ]
        return Solution(
            routes=routes,
            total_cost=self._cost,
            total_distance_m=100.0,
            total_time_s=10.0,
            feasible=True,
        )
