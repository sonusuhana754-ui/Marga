"""OSMnx graph loading and enrichment."""

from typing import Optional

import networkx as nx

from app.core.logging import get_logger
from app.graph.schemas import DEFAULT_SPEED_KMH

logger = get_logger("marga.graph.loader")


def load_graph(place: str, speed_kmh: float = DEFAULT_SPEED_KMH) -> nx.MultiDiGraph:
    """
    Fetch a drivable road graph for *place* from OpenStreetMap via OSMnx.

    Returns a directed multigraph where every edge carries:
      - ``length``: road segment length in metres (preserved from OSM).
      - ``travel_time``: estimated traversal time in seconds derived from
        ``length`` / (``speed_kmh`` * 1000 / 3600).

    The network type ``drive`` restricts the graph to roads accessible by
    motor vehicles.
    """
    import osmnx as ox

    logger.info("Loading drivable graph for place=%s", place)
    G = ox.graph_from_place(place, network_type="drive")

    # Ensure length is present on every edge (OSMnx ≥1.3 sets it)
    for _, _, data in G.edges(data=True):
        if "length" not in data:
            data["length"] = 0.0

    # Add deterministic travel_time based on length and default speed
    speed_ms = speed_kmh * 1000 / 3600  # km/h → m/s
    for _, _, data in G.edges(data=True):
        length: float = data.get("length", 0.0)
        data["travel_time"] = length / speed_ms if speed_ms > 0 else 0.0

    logger.info(
        "Graph loaded: %d nodes, %d edges",
        G.number_of_nodes(),
        G.number_of_edges(),
    )
    return G
