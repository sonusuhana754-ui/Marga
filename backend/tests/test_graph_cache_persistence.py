"""Disk persistence of GraphCache — the cold-start path on serverless hosts.

GRAPH_CACHE_DIR makes put() write the graph and a metadata sidecar, and lets a
brand-new GraphCache (an instance that never saw the load) repopulate from disk.
That is what a Vercel function instance does after a cold start.
"""

import networkx as nx
import pytest

from app.core.config import settings
from app.graph.cache import GraphCache, _normalize_key
from app.graph.schemas import GraphMetadata

PLACE = "Diskville, Wonderland"
KEY = _normalize_key(PLACE)


def _make_graph() -> nx.MultiDiGraph:
    G = nx.MultiDiGraph()
    G.add_node(1, x=0.0, y=0.0)
    G.add_node(2, x=0.001, y=0.001)
    G.add_edge(1, 2, length=200.0, travel_time=14.4)
    return G


def _make_metadata() -> GraphMetadata:
    return GraphMetadata(
        graph_key=KEY,
        place=PLACE,
        nodes=2,
        edges=2,
        total_length_km=0.4,
        avg_travel_time_s=14.4,
    )


@pytest.fixture
def disk_dir(tmp_path, monkeypatch):
    """Point the singleton settings at a throwaway directory for one test."""
    monkeypatch.setattr(settings, "GRAPH_CACHE_DIR", str(tmp_path))
    return tmp_path


class TestDiskPersistence:
    def test_put_writes_graph_and_metadata_sidecars(self, disk_dir):
        GraphCache().put(KEY, _make_graph(), _make_metadata())

        assert len(list(disk_dir.glob("*.graph.pkl"))) == 1
        assert len(list(disk_dir.glob("*.meta.json"))) == 1

    def test_fresh_instance_rehydrates_graph(self, disk_dir):
        """A cold instance that never saw the load serves the same graph key."""
        GraphCache().put(KEY, _make_graph(), _make_metadata())

        cold = GraphCache()  # empty memory, as after a process restart
        graph = cold.get(KEY)

        assert graph is not None
        assert graph.number_of_nodes() == 2
        assert graph.number_of_edges() == 1
        # Rehydration is cached: a second hit does not touch disk again.
        assert cold.get(KEY) is graph

    def test_fresh_instance_sees_metadata_and_keys(self, disk_dir):
        GraphCache().put(KEY, _make_graph(), _make_metadata())

        cold = GraphCache()
        assert cold.get_metadata(KEY) is not None
        assert cold.get_metadata(KEY).place == PLACE
        assert KEY in cold.keys()
        assert any(m.graph_key == KEY for m in cold.list_metadata())

    def test_remove_deletes_both_sidecars(self, disk_dir):
        GraphCache().put(KEY, _make_graph(), _make_metadata())

        cold = GraphCache()
        assert cold.remove(KEY) is False  # was not in this instance's memory

        assert not list(disk_dir.glob("*.graph.pkl"))
        assert not list(disk_dir.glob("*.meta.json"))
        assert cold.get(KEY) is None

    def test_corrupt_sidecar_is_ignored_not_fatal(self, disk_dir):
        GraphCache().put(KEY, _make_graph(), _make_metadata())
        for path in disk_dir.glob("*.graph.pkl"):
            path.write_bytes(b"not a pickle")

        assert GraphCache().get(KEY) is None

    def test_clear_empties_the_directory(self, disk_dir):
        GraphCache().put(KEY, _make_graph(), _make_metadata())

        GraphCache().clear()

        assert not list(disk_dir.glob("*.graph.pkl"))
        assert not list(disk_dir.glob("*.meta.json"))


class TestMemoryOnlyDefault:
    def test_default_setting_is_memory_only(self):
        """Unset GRAPH_CACHE_DIR keeps the original uvicorn behaviour."""
        assert settings.GRAPH_CACHE_DIR == ""

    def test_no_disk_write_and_no_cold_start_rehydration(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "GRAPH_CACHE_DIR", "")

        GraphCache().put(KEY, _make_graph(), _make_metadata())

        assert not list(tmp_path.glob("*.graph.pkl"))
        assert GraphCache().get(KEY) is None  # separate instance, memory only
