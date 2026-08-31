"""Deterministic generation of small CVRP/VRPTW scenarios.

All scenarios are built from a fixed in-code random seed and a caller-supplied
road graph, so results are reproducible without downloading any map data.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

import networkx as nx

from app.algorithms.models import Scenario, Stop, Vehicle
from app.graph.router import nearest_node


def _node_bbox(G: nx.MultiDiGraph) -> Tuple[float, float, float, float]:
    """Return (min_lng, min_lat, max_lng, max_lat) over graph nodes."""
    xs, ys = [], []
    for _node, data in G.nodes(data=True):
        xs.append(data.get("x", 0.0))
        ys.append(data.get("y", 0.0))
    if not xs:
        raise ValueError("Graph contains no nodes")
    return (min(xs), min(ys), max(xs), max(ys))


def make_scenario(
    graph: nx.MultiDiGraph,
    seed: int,
    capacity: int,
    vehicles: int,
    num_stops: int,
    time_windows: Optional[Dict[int, Tuple[float, float]]] = None,
) -> Scenario:
    """Build a deterministic static fleet scenario over `graph`.

    The depot is the graph node nearest the bounding-box centre. Delivery stops
    are random non-depot graph nodes drawn deterministically from `seed`.
    """
    rng = random.Random(seed)

    min_lng, min_lat, max_lng, max_lat = _node_bbox(graph)
    c_lng = (min_lng + max_lng) / 2.0
    c_lat = (min_lat + max_lat) / 2.0
    depot_node = nearest_node(graph, c_lng, c_lat)
    depot = _stop_from_node(graph, depot_node, id=0, demand=0)

    # Unique graph node IDs for the delivery stops.
    node_ids = list(graph.nodes())
    chosen = rng.sample(
        [n for n in node_ids if n != depot_node], k=min(num_stops, len(node_ids) - 1)
    )

    stops: List[Stop] = [depot]
    for i, nid in enumerate(chosen, start=1):
        demand = rng.randint(1, max(1, capacity // 2))
        stops.append(_stop_from_node(graph, nid, id=i, demand=demand))

    vehicle_list = [Vehicle(id=v, capacity=capacity) for v in range(vehicles)]

    return Scenario(
        graph=graph,
        stops=stops,
        vehicles=vehicle_list,
        depot=depot,
        seed=seed,
        time_windows=time_windows,
    )


def _stop_from_node(
    graph: nx.MultiDiGraph, node: int, id: int, demand: int
) -> Stop:
    data = graph.nodes[node]
    return Stop(
        id=id,
        lng=data.get("x", 0.0),
        lat=data.get("y", 0.0),
        x=data.get("x", 0.0),
        y=data.get("y", 0.0),
        demand=demand,
    )
