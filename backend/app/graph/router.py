"""Pure-function shortest-path router over a cached NetworkX MultiDiGraph.

All functions are stateless and operate on an ``nx.MultiDiGraph`` directly.
Parallel edges (MultiDiGraph) are handled explicitly: for each consecutive
node pair along the chosen path, the edge with the minimum weight is selected.
"""

from __future__ import annotations

import math
from typing import List, Tuple

import networkx as nx

from app.core.logging import get_logger

logger = get_logger("marga.graph.router")

_EARTH_RADIUS_M = 6_371_000.0


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _haversine_m(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """Return great-circle distance in metres between two [lng, lat] points."""
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
    )
    return _EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Nearest-node lookup
# ---------------------------------------------------------------------------

def nearest_node(
    G: nx.MultiDiGraph, lng: float, lat: float
) -> int:
    """Return the node ID in *G* closest to *(lng, lat)* by haversine distance.

    OSMnx stores node coordinates as ``x`` (longitude) and ``y`` (latitude).
    """
    best_node: int | None = None
    best_dist = math.inf

    for node, data in G.nodes(data=True):
        nx_lng = data.get("x", 0.0)
        nx_lat = data.get("y", 0.0)
        d = _haversine_m(lng, lat, nx_lng, nx_lat)
        if d < best_dist:
            best_dist = d
            best_node = node

    if best_node is None:
        raise ValueError("Graph contains no nodes")

    logger.debug(
        "nearest_node (%.6f, %.6f) → %s (%.1f m)", lng, lat, best_node, best_dist
    )
    return best_node


# ---------------------------------------------------------------------------
# Shortest path + cost accumulation over MultiDiGraph parallel edges
# ---------------------------------------------------------------------------

def _best_edge_data(
    G: nx.MultiDiGraph, u: int, v: int, weight: str
) -> dict:
    """Return the edge data dict for the parallel edge *(u, v)* with the
    minimum value of *weight*.

    Raises ``ValueError`` if no parallel edge is found.
    """
    best: dict | None = None
    best_w = math.inf

    for _key, edata in G[u][v].items():
        w = edata.get(weight, math.inf)
        if w < best_w:
            best_w = w
            best = edata

    if best is None:
        raise ValueError(f"No edge found between {u} and {v}")
    return best


def compute_shortest_path(
    G: nx.MultiDiGraph,
    source: int,
    target: int,
    weight: str = "travel_time",
) -> Tuple[List[int], float, float, List[Tuple[float, float]]]:
    """Compute the shortest path from *source* to *target*.

    Returns
    -------
    node_path : list[int]
        Ordered node IDs along the path.
    distance_m : float
        Total distance in metres (sum of ``length`` on chosen edges).
    eta_s : float
        Total travel time in seconds (sum of ``travel_time`` on chosen edges).
    coords : list[tuple[float, float]]
        ``[longitude, latitude]`` for every node in the path.
    """
    node_path: List[int] = nx.dijkstra_path(G, source, target, weight=weight)

    distance_m = 0.0
    eta_s = 0.0
    coords: List[Tuple[float, float]] = []

    for node in node_path:
        ndata = G.nodes[node]
        coords.append((ndata.get("x", 0.0), ndata.get("y", 0.0)))

    for u, v in zip(node_path[:-1], node_path[1:]):
        edata = _best_edge_data(G, u, v, weight)
        distance_m += edata.get("length", 0.0)
        eta_s += edata.get("travel_time", 0.0)

    return node_path, distance_m, eta_s, coords
