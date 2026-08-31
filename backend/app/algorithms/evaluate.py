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
