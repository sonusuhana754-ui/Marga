"""Thread-safe in-memory cache for loaded graphs and their metadata."""

from __future__ import annotations

import hashlib
import re
import threading
from typing import Dict, List, Optional

import networkx as nx

from app.core.logging import get_logger
from app.graph.schemas import GraphMetadata

logger = get_logger("marga.graph.cache")


def _normalize_key(place: str) -> str:
    """Return a deterministic lowercase-hashed key derived from *place*."""
    normalized = re.sub(r"\s+", " ", place.strip()).lower()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return f"{normalized.replace(' ', '_')}_{digest}"


class GraphCache:
    """
    In-memory store for loaded NetworkX graphs keyed by normalized place name.

    All public methods are protected by a reentrant lock so concurrent
    FastAPI request handlers can safely read and mutate the cache.
    """

    def __init__(self) -> None:
        self._graphs: Dict[str, nx.MultiDiGraph] = {}
        self._metadata: Dict[str, GraphMetadata] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Lookup / listing
    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[nx.MultiDiGraph]:
        """Return the cached graph for *key*, or ``None`` if absent."""
        with self._lock:
            return self._graphs.get(key)

    def get_metadata(self, key: str) -> Optional[GraphMetadata]:
        """Return metadata for *key*, or ``None`` if absent."""
        with self._lock:
            return self._metadata.get(key)

    def list_metadata(self) -> List[GraphMetadata]:
        """Return metadata for every cached graph."""
        with self._lock:
            return list(self._metadata.values())

    def keys(self) -> List[str]:
        """Return all cached keys."""
        with self._lock:
            return list(self._graphs.keys())

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def put(self, key: str, graph: nx.MultiDiGraph, metadata: GraphMetadata) -> None:
        """Store *graph* and *metadata* under *key*."""
        with self._lock:
            self._graphs[key] = graph
            self._metadata[key] = metadata
            logger.info("Cached graph key=%s (nodes=%d, edges=%d)", key, metadata.nodes, metadata.edges)

    def remove(self, key: str) -> bool:
        """Remove *key* from the cache.  Returns ``True`` if it existed."""
        with self._lock:
            existed = key in self._graphs
            self._graphs.pop(key, None)
            self._metadata.pop(key, None)
            if existed:
                logger.info("Evicted graph key=%s", key)
            return existed

    def clear(self) -> None:
        """Remove all cached graphs."""
        with self._lock:
            self._graphs.clear()
            self._metadata.clear()
            logger.info("Graph cache cleared")


# Module-level singleton shared across the application.
graph_cache = GraphCache()
