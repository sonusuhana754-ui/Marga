"""RouteService – orchestration layer for single-vehicle routing."""

from __future__ import annotations

from typing import Optional

from app.core.logging import get_logger
from app.graph.cache import GraphCache, _normalize_key, graph_cache
from app.graph.router import compute_shortest_path, nearest_node
from app.schemas.route import RouteRequest, RouteResponse, SingleRoute

logger = get_logger("marga.services.route")


class RouteService:
    """High-level interface for computing shortest-path routes.

    Depends on a :class:`GraphCache` containing a pre-loaded road graph.
    """

    def __init__(self, cache: Optional[GraphCache] = None) -> None:
        self._cache = cache or graph_cache

    def compute(self, req: RouteRequest) -> SingleRoute:
        """Compute the Dijkstra shortest path by *travel_time*.

        Returns a :class:`SingleRoute` with path coordinates, distance, and ETA.
        Raises ``ValueError`` if the graph is not cached or no path exists.
        """
        key = _normalize_key(req.city)
        G = self._cache.get(key)
        if G is None:
            raise ValueError(f"No cached graph for city '{req.city}' (key={key})")

        origin_node = nearest_node(G, req.origin[0], req.origin[1])
        dest_node = nearest_node(G, req.destination[0], req.destination[1])

        node_path, distance_m, eta_s, coords = compute_shortest_path(
            G, origin_node, dest_node, weight="travel_time"
        )

        logger.info(
            "Route computed: %d hops, %.0fm, %.1fs",
            len(node_path) - 1,
            distance_m,
            eta_s,
        )

        return SingleRoute(
            path=coords,
            distance_m=round(distance_m, 2),
            eta_s=round(eta_s, 2),
            feasible_for_profile=True,
        )

    def route(self, req: RouteRequest) -> RouteResponse:
        """Full route response with unconstrained and best (same in baseline)."""
        single = self.compute(req)
        return RouteResponse(
            unconstrained=single,
            best=single,
            blocked_edges=[],
            method="dijkstra",
        )
