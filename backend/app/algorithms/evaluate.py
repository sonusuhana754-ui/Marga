"""Graph-backed cost evaluation for fleet solutions.

Every leg between consecutive stops is evaluated using Dijkstra shortest path
on the *cached* road graph (read-only — the graph is never mutated). This module
also builds the pairwise cost matrices consumed by the OR-Tools solver and will
be reused by future metahurestic solvers to evaluate decoded solutions.
"""

from __future__ import annotations

from typing import List, Tuple

import networkx as nx

from app.algorithms.models import DEPOT_INDEX, Scenario, Solution
from app.graph.router import compute_shortest_path, nearest_node

_DEFAULT_SPEED_MS = 50.0 * 1000.0 / 3600.0


def leg_metrics(
    graph: nx.MultiDiGraph, origin_node: int, dest_node: int
) -> Tuple[float, float]:
    """Return ``(distance_m, time_s)`` for a single graph leg."""
    _path, distance_m, time_s, _coords = compute_shortest_path(
        graph, origin_node, dest_node, weight="travel_time"
    )
    return distance_m, time_s


def edge_cost_matrice(
    scenario: Scenario,
) -> Tuple[List[List[float]], List[List[float]]]:
    """Return ``(travel_time_matrix, distance_matrix)`` of shape (n+1, n+1).

    Index ``0`` is the depot; indices ``1..n`` are the delivery stops.
    """
    n = scenario.num_stops
    graph = scenario.graph
    nodes = [nearest_node(graph, s.lng, s.lat) for s in scenario.stops]

    time_matrix = [[0.0] * n for _ in range(n)]
    dist_matrix = [[0.0] * n for _ in range(n)]

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            _p, distance_m, time_s, _c = compute_shortest_path(
                graph, nodes[i], nodes[j], weight="travel_time"
            )
            time_matrix[i][j] = time_s
            dist_matrix[i][j] = distance_m

    return time_matrix, dist_matrix


def evaluate_solution(scenario: Scenario, solution: Solution) -> Solution:
    """Recompute distance/time/cost of a solution against the real graph.

    Returns a new :class:`Solution` with graph-backed leg metrics. Cost is
    ``distance_m + time_s`` where time is converted using the default speed so
    both terms share a consistent unit (decision: avoid double-counting traffic).
    """
    graph = scenario.graph
    stops = scenario.stops

    total_distance = 0.0
    total_time = 0.0

    for route in solution.routes:
        seq = route.stop_sequence
        route_dist = 0.0
        route_time = 0.0
        for a, b in zip(seq[:-1], seq[1:]):
            origin_node = nearest_node(graph, stops[a].lng, stops[a].lat)
            dest_node = nearest_node(graph, stops[b].lng, stops[b].lat)
            d, t = leg_metrics(graph, origin_node, dest_node)
            route_dist += d
            route_time += t
        route.distance_m = route_dist
        route.time_s = route_time
        total_distance += route_dist
        total_time += route_time
        route.load = sum(stops[i].demand for i in seq if i != DEPOT_INDEX)

    # Same time unit as the matrix: distance (m) + time (s) scaled to distance.
    total_cost = total_distance + total_time * _DEFAULT_SPEED_MS
    solution.total_distance_m = total_distance
    solution.total_time_s = total_time
    solution.total_cost = total_cost
    return solution


def validate_solution(scenario: Scenario, solution) -> Tuple[bool, List[str]]:
    violations: List[str] = []
    if not getattr(solution, "feasible", False):
        violations.append("solution.feasible is False")
        return False, violations

    stops = scenario.stops
    num_stops = scenario.num_stops

    seen = set()
    for route in solution.routes:
        seq = getattr(route, "stop_sequence", [])
        if len(seq) < 2:
            violations.append(f"route {route.vehicle_id} has invalid stop_sequence")
            continue
        if seq[0] != DEPOT_INDEX or seq[-1] != DEPOT_INDEX:
            violations.append(f"route {route.vehicle_id} must start/end at depot {DEPOT_INDEX}")
        for i, s in enumerate(seq[1:-1], start=1):
            if s == DEPOT_INDEX:
                violations.append(f"route {route.vehicle_id} contains depot in interior at pos {i}")
        for s in seq:
            if s < 0 or s >= num_stops:
                violations.append(f"stop id {s} out of range")
            seen.add(s)

    all_stops = set(range(num_stops)) if num_stops >= 0 else set()
    for sid in all_stops:
        if sid not in seen:
            violations.append(f"missing stop {sid}")
    for sid in seen:
        if sid in all_stops and sid != DEPOT_INDEX:
            count = sum(1 for r in solution.routes for s in getattr(r, "stop_sequence", []) if s == sid)
            if count != 1:
                violations.append(f"duplicate stop {sid}")

    for route in solution.routes:
        seq = getattr(route, "stop_sequence", [])
        load_recomputed = sum(stops[i].demand for i in seq if i != DEPOT_INDEX)
        if abs(getattr(route, "load", -1) - load_recomputed) > 1e-9:
            violations.append(f"route {route.vehicle_id} load mismatch")
        if hasattr(scenario, "vehicles") and route.vehicle_id < len(scenario.vehicles):
            cap = scenario.vehicles[route.vehicle_id].capacity
            if getattr(route, "load", 0) > cap + 1e-9:
                violations.append(f"route {route.vehicle_id} capacity exceeded")

    if getattr(solution, "total_distance_m", 0.0) < 0:
        violations.append("total_distance_m < 0")
    if getattr(solution, "total_time_s", 0.0) < 0:
        violations.append("total_time_s < 0")

    return len(violations) == 0, violations
