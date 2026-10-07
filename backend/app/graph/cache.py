"""Thread-safe graph cache: in-memory store with optional disk persistence.

The in-memory dict is the whole cache under plain uvicorn. Serverless hosts
(Vercel, Cloud Run) recycle processes and run several of them side by side, so
a graph loaded in one instance is invisible to the next request. Setting
``GRAPH_CACHE_DIR`` (e.g. ``/tmp/marga-graphs``) persists every graph to that
directory: ``put`` writes it, and ``get`` repopulates memory from disk on a
miss, so a cold instance self-heals instead of returning 404. Empty setting
(the default) keeps the original memory-only behaviour exactly.
"""

from __future__ import annotations

import hashlib
import json
import pickle
import re
import threading
from pathlib import Path
from typing import Dict, List, Optional

import networkx as nx

from app.core.config import settings
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
    Store for loaded NetworkX graphs keyed by normalized place name.

    All public methods are protected by a reentrant lock so concurrent
    FastAPI request handlers can safely read and mutate the cache. Disk
    access is guarded by the same lock: graphs are a few MB, so the write
    stays inside the request that loaded them.
    """

    def __init__(self) -> None:
        self._graphs: Dict[str, nx.MultiDiGraph] = {}
        self._metadata: Dict[str, GraphMetadata] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Disk helpers (active only when GRAPH_CACHE_DIR is set)
    # ------------------------------------------------------------------

    def _dir(self) -> Optional[Path]:
        """Return the configured persistence directory, or ``None`` for memory-only."""
        raw = settings.GRAPH_CACHE_DIR
        return Path(raw) if raw else None

    @staticmethod
    def _paths(root: Path, key: str) -> tuple[Path, Path]:
        """Return (graph, metadata) paths for *key*; the hash keeps any key filename-safe."""
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return root / f"{digest}.graph.pkl", root / f"{digest}.meta.json"

    def _load_from_disk(self, key: str) -> Optional[nx.MultiDiGraph]:
        """Read *key*'s graph from disk. Any failure logs and returns ``None``."""
        root = self._dir()
        if root is None:
            return None
        graph_path, _ = self._paths(root, key)
        try:
            with open(graph_path, "rb") as fh:
                graph = pickle.load(fh)
        except FileNotFoundError:
            return None
        except Exception:
            logger.warning("Could not read cached graph %s", graph_path, exc_info=True)
            return None
        if not isinstance(graph, nx.MultiDiGraph):
            logger.warning("Discarding non-multigraph payload for key=%s", key)
            return None
        return graph

    def _load_metadata_for_key(self, key: str) -> Optional[GraphMetadata]:
        """Read *key*'s metadata sidecar. Any failure logs and returns ``None``."""
        root = self._dir()
        if root is None:
            return None
        _, meta_path = self._paths(root, key)
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
            return GraphMetadata.model_validate(payload["metadata"])
        except FileNotFoundError:
            return None
        except Exception:
            logger.warning("Ignoring unreadable metadata sidecar %s", meta_path, exc_info=True)
            return None

    def _load_metadata_from_disk(self) -> Dict[str, GraphMetadata]:
        """Return every metadata sidecar in the persistence directory."""
        root = self._dir()
        if root is None or not root.is_dir():
            return {}
        found: Dict[str, GraphMetadata] = {}
        for meta_path in sorted(root.glob("*.meta.json")):
            try:
                payload = json.loads(meta_path.read_text(encoding="utf-8"))
                found[payload["key"]] = GraphMetadata.model_validate(payload["metadata"])
            except Exception:
                logger.warning("Ignoring unreadable metadata sidecar %s", meta_path, exc_info=True)
        return found

    # ------------------------------------------------------------------
    # Lookup / listing
    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[nx.MultiDiGraph]:
        """Return the cached graph for *key*, or ``None`` if absent.

        On a memory miss the disk copy is loaded and re-populates memory, which
        is what lets a freshly started serverless instance serve a graph key it
        never saw loaded.
        """
        with self._lock:
            graph = self._graphs.get(key)
            if graph is not None:
                return graph
            graph = self._load_from_disk(key)
            if graph is not None:
                self._graphs[key] = graph
                meta = self._load_metadata_for_key(key)
                if meta is not None:
                    self._metadata[key] = meta
                logger.info("Rehydrated graph key=%s from disk", key)
            return graph

    def get_metadata(self, key: str) -> Optional[GraphMetadata]:
        """Return metadata for *key*, falling back to the disk sidecar."""
        with self._lock:
            meta = self._metadata.get(key)
            if meta is not None:
                return meta
            return self._load_metadata_for_key(key)

    def list_metadata(self) -> List[GraphMetadata]:
        """Return metadata for every cached graph, memory and disk combined."""
        with self._lock:
            combined = self._load_metadata_from_disk()
            combined.update(self._metadata)
            return list(combined.values())

    def keys(self) -> List[str]:
        """Return all cached keys, memory and disk combined."""
        with self._lock:
            return sorted(set(self._graphs) | set(self._metadata) | set(self._load_metadata_from_disk()))

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def put(self, key: str, graph: nx.MultiDiGraph, metadata: GraphMetadata) -> None:
        """Store *graph* and *metadata* under *key*, on memory and (if configured) disk."""
        with self._lock:
            self._graphs[key] = graph
            self._metadata[key] = metadata
            root = self._dir()
            if root is not None:
                try:
                    root.mkdir(parents=True, exist_ok=True)
                    graph_path, meta_path = self._paths(root, key)
                    tmp_path = graph_path.with_suffix(".tmp")
                    with open(tmp_path, "wb") as fh:
                        pickle.dump(graph, fh, protocol=pickle.HIGHEST_PROTOCOL)
                    tmp_path.replace(graph_path)
                    meta_path.write_text(
                        json.dumps(
                            {"key": key, "metadata": json.loads(metadata.model_dump_json())},
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                except Exception:
                    # Persistence is an accelerator, never a reason to fail a load.
                    logger.warning("Could not persist graph key=%s", key, exc_info=True)
            logger.info("Cached graph key=%s (nodes=%d, edges=%d)", key, metadata.nodes, metadata.edges)

    def remove(self, key: str) -> bool:
        """Remove *key* from the cache.  Returns ``True`` if it existed."""
        with self._lock:
            existed = key in self._graphs
            self._graphs.pop(key, None)
            self._metadata.pop(key, None)
            root = self._dir()
            if root is not None:
                graph_path, meta_path = self._paths(root, key)
                for path in (graph_path, meta_path):
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        logger.warning("Could not delete %s", path, exc_info=True)
            if existed:
                logger.info("Evicted graph key=%s", key)
            return existed

    def clear(self) -> None:
        """Remove all cached graphs from memory and the persistence directory."""
        with self._lock:
            self._graphs.clear()
            self._metadata.clear()
            root = self._dir()
            if root is not None and root.is_dir():
                for path in root.glob("*.graph.pkl"):
                    path.unlink(missing_ok=True)
                for path in root.glob("*.meta.json"):
                    path.unlink(missing_ok=True)
            logger.info("Graph cache cleared")


# Module-level singleton shared across the application.
graph_cache = GraphCache()
