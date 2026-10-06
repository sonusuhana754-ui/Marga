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


def _draw_demands(
    rng: random.Random,
    num_stops: int,
    capacity: int,
    vehicles: int,
    target_utilisation: float,
) -> List[int]:
    """Draw per-stop demands that the fleet can actually carry.

    Draws a random *shape* first, then scales it down to a target fleet
    utilisation. Without this, `demand = randint(1, capacity // 2)` overflows the
    fleet as soon as `num_stops` grows past roughly `2 * vehicles`, producing
    instances no solver can serve — every candidate is infeasible and the
    comparison measures nothing.

    Returns demands in ``1..capacity``, preserving relative sizes, summing to at
    most ``target_utilisation * vehicles * capacity``. Deterministic in `rng`.
    """
    fleet_capacity = vehicles * capacity
    budget = max(num_stops, int(fleet_capacity * target_utilisation))
    budget = min(budget, fleet_capacity, num_stops * capacity)

    if num_stops <= 0:
        return []

    # Random weights, then integer apportionment that keeps every stop >= 1.
    weights = [rng.uniform(0.5, 1.5) for _ in range(num_stops)]
    total_weight = sum(weights)
    raw = [w / total_weight * budget for w in weights]

    demands = [max(1, min(capacity, int(value))) for value in raw]

    # Trim or top up to land on the budget without creating an unservable tail.
    while sum(demands) > budget:
        i = max(range(num_stops), key=lambda j: demands[j])
        if demands[i] <= 1:
            break
        demands[i] -= 1
    deficit = budget - sum(demands)
    while deficit > 0:
        for i in range(num_stops):
            if deficit == 0:
                break
            if demands[i] < capacity:
                demands[i] += 1
                deficit -= 1
        else:
            break

    # If the fleet cannot carry num_stops at minimum load, the instance is
    # infeasible by construction; `make_scenario` surfaces that to the caller.
    return demands


def make_scenario(
    graph: nx.MultiDiGraph,
    seed: int,
    capacity: int,
    vehicles: int,
    num_stops: int,
    time_windows: Optional[Dict[int, Tuple[float, float]]] = None,
    target_utilisation: float = 0.9,
) -> Scenario:
    """Build a deterministic static fleet scenario over `graph`.

    The depot is the graph node nearest the bounding-box centre. Delivery stops
    are random non-depot graph nodes drawn deterministically from `seed`.

    Demands are scaled so the fleet can carry them at roughly
    `target_utilisation`; see :func:`_draw_demands`.
    """
    if capacity < 1:
        raise ValueError("capacity must be >= 1")
    if vehicles < 1:
        raise ValueError("vehicles must be >= 1")
    if num_stops < 1:
        raise ValueError("num_stops must be >= 1")
    if not 0 < target_utilisation <= 1.0:
        raise ValueError("target_utilisation must be in (0, 1]")

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
    demands = _draw_demands(rng, len(chosen), capacity, vehicles, target_utilisation)

    stops: List[Stop] = [depot]
    for i, (nid, demand) in enumerate(zip(chosen, demands), start=1):
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
