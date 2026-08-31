"""Tests for the OR-Tools static CVRP/VRPTW baseline solver."""

import networkx as nx
import pytest

from app.algorithms.models import DEPOT_INDEX, Scenario, Stop, Vehicle
from app.algorithms.ortools_solver import ORToolsSolver, solve_cvrp, solve_vrptw


def _grid_graph(num_nodes: int = 8) -> nx.MultiDiGraph:
    """A small deterministic directed grid graph with known edges."""
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
        if (v, u, length) not in [(e[0], e[1], e[2]) for e in edges]:
            G.add_edge(v, u, length=length, travel_time=tt)
    return G


def _make_cvrp_scenario(
    capacity: int = 10,
    vehicles: int = 3,
    demands=None,
    num_nodes: int = 8,
) -> Scenario:
    G = _grid_graph(num_nodes)
    if demands is None:
        demands = {0: 0, 1: 3, 2: 4, 3: 2, 4: 5, 5: 1, 6: 2, 7: 3}
    stops = [
        Stop(
            id=i,
            lng=G.nodes[i]["x"],
            lat=G.nodes[i]["y"],
            x=G.nodes[i]["x"],
            y=G.nodes[i]["y"],
            demand=demands.get(i, 0),
        )
        for i in range(num_nodes)
    ]
    return Scenario(
        graph=G,
        stops=stops,
        vehicles=[Vehicle(id=v, capacity=capacity) for v in range(vehicles)],
        depot=stops[0],
        seed=7,
    )


class TestCVRPSolver:
    """Capacity-constrained static fleet solution."""

    def test_cvrp_returns_feasible_solution(self):
        scenario = _make_cvrp_scenario()
        solution = solve_cvrp(scenario)

        assert solution.feasible is True
        assert solution.vehicles_used > 0
        assert solution.total_cost > 0
        assert len(solution.routes) <= scenario.num_vehicles

    def test_cvrp_all_stops_covered_once(self):
        scenario = _make_cvrp_scenario()
        solution = solve_cvrp(scenario)

        covered: set[int] = set()
        for route in solution.routes:
            for stop in route.stop_sequence[1:-1]:
                assert stop != DEPOT_INDEX
                assert stop not in covered, f"stop {stop} assigned twice"
                covered.add(stop)
        # Every non-depot stop is served.
        assert covered == {i for i in range(1, scenario.num_stops)}

    def test_cvrp_capacity_not_exceeded(self):
        scenario = _make_cvrp_scenario(capacity=7)
        solution = solve_cvrp(scenario)

        assert solution.feasible is True
        for route in solution.routes:
            load = route.load
            capacity = scenario.vehicles[route.vehicle_id].capacity
            assert load <= capacity

    def test_cvrp_is_deterministic(self):
        scenario = _make_cvrp_scenario()
        s1 = solve_cvrp(scenario)
        s2 = solve_cvrp(scenario)
        assert s1.total_cost == pytest.approx(s2.total_cost)


class TestVRPTWSolver:
    """Time-window constrained static fleet solution."""

    def test_vrptw_returns_feasible_with_windows(self):
        scenario = _make_cvrp_scenario()
        # Give all non-depot stops generous windows so it stays feasible.
        scenario.time_windows = {
            i: (0.0, 500.0) for i in range(0, scenario.num_stops)
        }
        solution = solve_vrptw(scenario)

        assert solution.feasible is True
        assert solution.vehicles_used > 0

    def test_vrptw_respects_tight_depot_origin(self):
        scenario = _make_cvrp_scenario(capacity=10, vehicles=2)
        # Depot window [0,0]: must depart immediately at t=0.
        scenario.time_windows = {0: (0.0, 0.0)}
        for i in range(1, scenario.num_stops):
            scenario.time_windows[i] = (0.0, 1000.0)
        solution = solve_vrptw(scenario)
        assert solution.feasible is True
        assert solution.total_cost >= 0


class TestORToolsModelConstruction:
    """The internal OR-Tools routing model builds without error."""

    def test_build_routing_model_cvrp(self):
        from app.algorithms.ortools_solver import _build_routing_model

        scenario = _make_cvrp_scenario()
        manager, routing = _build_routing_model(scenario)
        assert routing is not None
        assert manager.GetNumberOfNodes() == scenario.num_stops

    def test_ortools_solver_id(self):
        scenario = _make_cvrp_scenario()
        solver = ORToolsSolver(scenario)
        assert solver.solver_id == "ortools"
