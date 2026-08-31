"""GraphService – sole orchestration layer consumed by HTTP endpoints."""

from __future__ import annotations

from typing import List, Optional

import networkx as nx

from app.core.logging import get_logger
from app.graph.cache import GraphCache, _normalize_key, graph_cache
from app.graph.schemas import DEFAULT_SPEED_KMH, GraphMetadata
from app.schemas.graph import GraphLoadResponse

logger = get_logger("marga.services.graph")


def _build_metadata(place: str, key: str, G: nx.MultiDiGraph) -> GraphMetadata:
    """Derive :class:`GraphMetadata` from a loaded NetworkX graph."""
    total_length = 0.0
    total_travel_time = 0.0
    edge_count = 0

    for _, _, data in G.edges(data=True):
        total_length += data.get("length", 0.0)
        total_travel_time += data.get("travel_time", 0.0)
        edge_count += 1

    node_count = G.number_of_nodes()

    # Strongly-connected component analysis
    is_scc: Optional[bool] = None
    scc_size: Optional[int] = None
    if node_count > 0:
        scc = nx.number_strongly_connected_components(G)
        largest_scc_nodes = len(max(nx.strongly_connected_components(G), key=len))
        scc_size = largest_scc_nodes
        is_scc = scc == 1

    avg_tt = total_travel_time / edge_count if edge_count > 0 else 0.0
    total_length_km = total_length / 1000.0

    return GraphMetadata(
        graph_key=key,
        place=place,
        nodes=node_count,
        edges=edge_count,
        total_length_km=round(total_length_km, 2),
        avg_travel_time_s=round(avg_tt, 2),
        default_speed_kmh=DEFAULT_SPEED_KMH,
        is_strongly_connected=is_scc,
        scc_node_count=scc_size,
    )


class GraphService:
    """
    High-level interface for graph loading and cache management.

    All OSMnx network calls are delegated to :func:`load_graph` and are
    expected to run inside a thread-pool executor so the async event loop
    is never blocked.
    """

    def __init__(self, cache: Optional[GraphCache] = None) -> None:
        self._cache = cache or graph_cache

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, place: str, force_reload: bool = False) -> GraphLoadResponse:
        """
        Load a drivable graph for *place*, using the cache when possible.

        Returns a :class:`GraphLoadResponse` with the graph's metadata.
        Raises ``ValueError`` if the underlying OSMnx call fails (typically
        a network error or unknown place name).
        """
        key = _normalize_key(place)
        existing = self._cache.get(key)

        if existing is not None and not force_reload:
            logger.info("Graph cache hit for key=%s", key)
            metadata = self._cache.get_metadata(key)
            return GraphLoadResponse(
                message="Graph loaded from cache",
                graph_key=key,
                metadata=metadata,  # type: ignore[arg-type]
            )

        if force_reload:
            self._cache.remove(key)
            logger.info("Force-reloading graph for place=%s", place)

        try:
            from app.graph.loader import load_graph
            G = load_graph(place)
        except Exception as exc:
            logger.error("Failed to load graph for place=%s: %s", place, exc)
            raise ValueError(f"Could not load graph for '{place}': {exc}") from exc

        metadata = _build_metadata(place, key, G)
        self._cache.put(key, G, metadata)

        return GraphLoadResponse(
            message="Graph loaded successfully",
            graph_key=key,
            metadata=metadata,
        )

    def get_metadata(self, graph_key: str) -> Optional[GraphMetadata]:
        """Return cached metadata for *graph_key*, or ``None``."""
        return self._cache.get_metadata(graph_key)

    def list_metadata(self) -> List[GraphMetadata]:
        """Return metadata for every cached graph."""
        return self._cache.list_metadata()
