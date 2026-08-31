"""Tests for the graph-engine endpoints (OSMnx is fully mocked)."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from app.core.config import settings
from app.graph.cache import _normalize_key


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_graph():
    """Return a small mock NetworkX MultiDiGraph with travel_time on every edge."""
    import networkx as nx

    G = nx.MultiDiGraph()
    G.add_node(1, x=0.0, y=0.0)
    G.add_node(2, x=0.001, y=0.001)
    G.add_node(3, x=0.002, y=0.002)
    G.add_edge(1, 2, length=200.0, travel_time=14.4)
    G.add_edge(2, 3, length=350.0, travel_time=25.2)
    G.add_edge(2, 1, length=200.0, travel_time=14.4)
    return G


PLACE = "Testville, Wonderland"
GRAPH_KEY = _normalize_key(PLACE)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGraphLoad:
    """POST /api/v1/graphs/load"""

    @patch("app.graph.loader.load_graph")
    def test_load_returns_metadata(self, mock_load: MagicMock, client: TestClient):
        """Loading a graph returns correct metadata fields."""
        mock_load.return_value = _make_fake_graph()

        resp = client.post(
            f"{settings.API_V1_STR}/graphs/load",
            json={"place": PLACE, "force_reload": True},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["graph_key"] == GRAPH_KEY
        assert body["metadata"]["nodes"] == 3
        assert body["metadata"]["edges"] == 3
        assert body["metadata"]["place"] == PLACE
        assert body["metadata"]["total_length_km"] > 0
        assert body["metadata"]["avg_travel_time_s"] > 0
        mock_load.assert_called_once()

    @patch("app.graph.loader.load_graph")
    def test_repeated_load_uses_cache(self, mock_load: MagicMock, client: TestClient):
        """A second load without force_reload must NOT call load_graph again."""
        mock_load.return_value = _make_fake_graph()

        # First load – hits OSMnx
        resp1 = client.post(
            f"{settings.API_V1_STR}/graphs/load",
            json={"place": PLACE, "force_reload": True},
        )
        assert resp1.status_code == 200
        assert mock_load.call_count == 1

        # Second load – should come from cache
        resp2 = client.post(
            f"{settings.API_V1_STR}/graphs/load",
            json={"place": PLACE, "force_reload": False},
        )
        assert resp2.status_code == 200
        assert mock_load.call_count == 1  # still 1
        assert resp2.json()["message"] == "Graph loaded from cache"

    @patch("app.graph.loader.load_graph")
    def test_force_reload_fetches_again(self, mock_load: MagicMock, client: TestClient):
        """force_reload=True must invoke load_graph even if cached."""
        mock_load.return_value = _make_fake_graph()

        client.post(
            f"{settings.API_V1_STR}/graphs/load",
            json={"place": PLACE, "force_reload": True},
        )
        client.post(
            f"{settings.API_V1_STR}/graphs/load",
            json={"place": PLACE, "force_reload": True},
        )
        assert mock_load.call_count == 2


class TestGraphList:
    """GET /api/v1/graphs"""

    @patch("app.graph.loader.load_graph")
    def test_list_returns_cached_entries(self, mock_load: MagicMock, client: TestClient):
        """List endpoint returns metadata for all cached graphs."""
        mock_load.return_value = _make_fake_graph()

        client.post(
            f"{settings.API_V1_STR}/graphs/load",
            json={"place": PLACE, "force_reload": True},
        )

        resp = client.get(f"{settings.API_V1_STR}/graphs")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] >= 1
        assert any(g["graph_key"] == GRAPH_KEY for g in body["graphs"])


class TestGraphGetByKey:
    """GET /api/v1/graphs/{graph_key}"""

    @patch("app.graph.loader.load_graph")
    def test_get_existing_key(self, mock_load: MagicMock, client: TestClient):
        """Fetching an existing key returns 200 with metadata."""
        mock_load.return_value = _make_fake_graph()

        client.post(
            f"{settings.API_V1_STR}/graphs/load",
            json={"place": PLACE, "force_reload": True},
        )

        resp = client.get(f"{settings.API_V1_STR}/graphs/{GRAPH_KEY}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["graph_key"] == GRAPH_KEY
        assert body["metadata"]["place"] == PLACE

    def test_get_missing_key_returns_404(self, client: TestClient):
        """Fetching a nonexistent key returns 404."""
        resp = client.get(f"{settings.API_V1_STR}/graphs/nonexistent_key_123")
        assert resp.status_code == 404


class TestGraphLoadError:
    """Error handling for graph loading."""

    @patch("app.graph.loader.load_graph")
    def test_load_failure_returns_502(self, mock_load: MagicMock, client: TestClient):
        """A ValueError from the service (OSMnx failure) maps to 502."""
        mock_load.side_effect = ValueError("Unable to retrieve data")

        resp = client.post(
            f"{settings.API_V1_STR}/graphs/load",
            json={"place": "Faketown, Nowhere", "force_reload": True},
        )
        assert resp.status_code == 502
        assert "could not be fetched" in resp.json()["detail"].lower()


class TestNormalization:
    """Unit tests for cache key normalization."""

    def test_keys_are_deterministic(self):
        """Same input always produces the same key."""
        assert _normalize_key(PLACE) == _normalize_key(PLACE)

    def test_keys_are_case_insensitive(self):
        """Case differences do not produce different keys."""
        assert _normalize_key("San Francisco") == _normalize_key("san francisco")

    def test_whitespace_is_normalized(self):
        """Extra whitespace is collapsed before hashing."""
        assert _normalize_key("  San  Francisco  ") == _normalize_key("San Francisco")
