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

    # Extent of the loaded area, so the map can fly to it without the client
    # having to know which part of the world was fetched.
    xs = [d.get("x", 0.0) for _n, d in G.nodes(data=True)]
    ys = [d.get("y", 0.0) for _n, d in G.nodes(data=True)]
    bounds: Optional[List[float]] = None
    center: Optional[List[float]] = None
    if xs and ys:
        bounds = [min(xs), min(ys), max(xs), max(ys)]
        center = [(min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0]

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
        center=center,
        bounds=bounds,
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

    def load(
        self,
        place: Optional[str] = None,
        force_reload: bool = False,
        *,
        center: Optional[List[float]] = None,
        dist_m: int = 1200,
    ) -> GraphLoadResponse:
        """
        Load a drivable graph for *place* or around *center* ``[lng, lat]``,
        using the cache when possible.

        ``center`` is how any point on Earth is loaded without knowing its
        administrative name: the cache key is derived from the rounded
        coordinates instead of the place string.

        Returns a :class:`GraphLoadResponse` with the graph's metadata.
        Raises ``ValueError`` if neither argument is given or if the
        underlying OSMnx call fails (typically a network error or unknown
        place name).
        """
        if center is not None and len(center) != 2:
            raise ValueError("center must be [lng, lat]")
        if center is None and not place:
            raise ValueError("provide a place name or a center point")

        if center is not None:
            lng, lat = float(center[0]), float(center[1])
            label = f"point {lng:.4f},{lat:.4f} ±{int(dist_m)}m"
            key = _normalize_key(f"{lng:.3f},{lat:.3f},{int(dist_m)}m")
        else:
            label = place or ""
            key = _normalize_key(label)

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
            logger.info("Force-reloading graph for key=%s", key)

        try:
            from app.graph.loader import load_graph
            G = load_graph(place, center=center, dist_m=float(dist_m))
        except Exception as exc:
            logger.error("Failed to load graph for %s: %s", label, exc)
            raise ValueError(f"Could not load graph for '{label}': {exc}") from exc

        metadata = _build_metadata(label, key, G)
        self._cache.put(key, G, metadata)

        return GraphLoadResponse(
            message="Graph loaded successfully",
            graph_key=key,
            metadata=metadata,
        )

    def get_metadata(self, graph_key: str) -> Optional[GraphMetadata]:
        """Return cached metadata for *graph_key*, or ``None``."""
        return self._cache.get_metadata(graph_key)

    def get_graph(self, graph_key: str) -> Optional[nx.MultiDiGraph]:
        """Return the cached NetworkX graph for *graph_key*, or ``None``."""
        return self._cache.get(key=graph_key)

    def list_metadata(self) -> List[GraphMetadata]:
        """Return metadata for every cached graph."""
        return self._cache.list_metadata()
