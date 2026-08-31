"""OR-Tools static CVRP/VRPTW solver (baseline).

Wraps the Google OR-Tools routing solver for a single static fleet instance.
Supports capacity-only CVRP and, when time windows are present, VRPTW. Uses a
guided 2-opt local-search neighbourhood only (3-opt is intentionally deferred).

This is a baseline reference: its purpose is to be compared fairly against
future metahurestic solvers, not to claim optimality.
"""

from __future__ import annotations

import time
from typing import List

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from app.algorithms.base import Solver
from app.algorithms.evaluate import edge_cost_matrice, evaluate_solution
from app.algorithms.models import DEPOT_INDEX, RoutePlan, Scenario, Solution


def _build_routing_model(scenario: Scenario):
    """Build and return ``(manager, routing)`` for OR-Tools."""
    time_matrix, _dist_matrix = edge_cost_matrice(scenario)

    num_nodes = scenario.num_stops
    manager = pywrapcp.RoutingIndexManager(num_nodes, scenario.num_vehicles, DEPOT_INDEX)
    routing = pywrapcp.RoutingModel(manager)

    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(time_matrix[from_node][to_node])

    transit_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Capacity dimension.
    demands = [0] * num_nodes
    for stop in scenario.stops:
        demands[stop.id] = stop.demand

    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return demands[from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  # no slack
        [v.capacity for v in scenario.vehicles],
        True,  # start cumul to zero
        "Capacity",
    )

    # Time-window dimension (VRPTW only).
    if scenario.time_windowed:
        time_windows = scenario.time_windows or {}
        horizon = max(
            (tw[1] for tw in time_windows.values()), default=1_000_000.0
        )
        horizon = max(horizon, 1_000_000.0)
        time_dim = routing.AddDimension(
            transit_callback_index,
            int(horizon),  # slack capacity
            int(horizon),  # max total time per vehicle
            True,
            "Time",
        )
        time_dimension = routing.GetDimensionOrDie("Time")
        for stop in scenario.stops:
            index = manager.NodeToIndex(stop.id)
            if stop.id in time_windows:
                earliest, latest = time_windows[stop.id]
                time_dimension.CumulVar(index).SetRange(int(earliest), int(latest))
            else:
                time_dimension.CumulVar(index).SetRange(0, int(horizon))
        for vehicle in range(scenario.num_vehicles):
            end = routing.End(vehicle)
            time_dimension.CumulVar(end).SetRange(0, int(horizon))

    return manager, routing


class ORToolsSolver(Solver):
    """Static CVRP/VRPTW baseline via Google OR-Tools."""

    solver_id = "ortools"

    def __init__(
        self,
        scenario: Scenario,
        time_limit_ms: int = 10_000,
    ) -> None:
        super().__init__(scenario)
        self.time_limit_ms = time_limit_ms

    def solve(self) -> Solution:
        scenario = self.scenario
        manager, routing = _build_routing_model(scenario)

        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.time_limit.seconds = max(1, self.time_limit_ms // 1000)
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        # 2-opt guided local search only (3-opt intentionally deferred).
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )

        start = time.perf_counter()
        assignment = routing.SolveWithParameters(search_parameters)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        if assignment is None:
            return Solution(feasible=False, total_cost=float("inf"))

        solution = Solution(feasible=True)
        for vehicle in range(scenario.num_vehicles):
            index = routing.Start(vehicle)
            seq: List[int] = []
            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                seq.append(node)
                index = assignment.Value(routing.NextVar(index))
            end_node = manager.IndexToNode(index)
            seq.append(end_node)
            # Drop single-node (depot-only) vehicles.
            if len(seq) > 2:
                solution.routes.append(
                    RoutePlan(vehicle_id=vehicle, stop_sequence=seq, load=0)
                )

        compute_time = time.perf_counter()
        solution = evaluate_solution(scenario, solution)
        elapsed_ms += (time.perf_counter() - compute_time) * 1000.0
        solution._runtime_ms = elapsed_ms  # type: ignore[attr-defined]
        return solution


def solve_cvrp(scenario: Scenario, **kwargs) -> Solution:
    """Convenience: solve a capacity-only scenario."""
    return ORToolsSolver(scenario, **kwargs).solve()


def solve_vrptw(scenario: Scenario, **kwargs) -> Solution:
    """Convenience: solve a time-windowed scenario (static full reopt)."""
    return ORToolsSolver(scenario, **kwargs).solve()
