"""Tests for the route endpoint (OSMnx is fully mocked)."""

from unittest.mock import MagicMock, patch

import networkx as nx
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.graph.cache import _normalize_key, graph_cache

# ---------------------------------------------------------------------------
# Helpers – test graphs
# ---------------------------------------------------------------------------

PLACE = "Testville, Wonderland"
GRAPH_KEY = _normalize_key(PLACE)


def _make_linear_graph() -> nx.MultiDiGraph:
    """A → B → C  (3 nodes, 2 edges, unique paths)."""
    G = nx.MultiDiGraph()
    G.add_node("A", x=77.620, y=12.930)
    G.add_node("B", x=77.625, y=12.935)
    G.add_node("C", x=77.630, y=12.940)
    G.add_edge("A", "B", length=600.0, travel_time=43.2)
    G.add_edge("B", "C", length=800.0, travel_time=57.6)
    return G


def _make_diamond_graph() -> nx.MultiDiGraph:
    """A → B (short-distance, long-time) vs A → C → B (long-distance, short-time).

    Dijkstra by travel_time must pick A → C → B.
    """
    G = nx.MultiDiGraph()
    G.add_node("A", x=77.620, y=12.930)
    G.add_node("B", x=77.630, y=12.940)
    G.add_node("C", x=77.622, y=12.938)
    G.add_edge("A", "B", length=500.0, travel_time=120.0)
    G.add_edge("A", "C", length=900.0, travel_time=30.0)
    G.add_edge("C", "B", length=400.0, travel_time=20.0)
    return G


def _make_parallel_edge_graph() -> nx.MultiDiGraph:
    """A → B with two parallel edges: the faster one wins."""
    G = nx.MultiDiGraph()
    G.add_node("A", x=77.620, y=12.930)
    G.add_node("B", x=77.625, y=12.935)
    G.add_edge("A", "B", length=300.0, travel_time=60.0, key="slow")
    G.add_edge("A", "B", length=600.0, travel_time=15.0, key="fast")
    return G


def _populate_cache(G: nx.MultiDiGraph) -> None:
    """Insert *G* into the module-level graph_cache under PLACE."""
    from app.graph.schemas import GraphMetadata

    meta = GraphMetadata(
        graph_key=GRAPH_KEY,
        place=PLACE,
        nodes=G.number_of_nodes(),
        edges=G.number_of_edges(),
        total_length_km=1.0,
        avg_travel_time_s=10.0,
        default_speed_kmh=50.0,
        is_strongly_connected=True,
        scc_node_count=G.number_of_nodes(),
    )
    graph_cache.put(GRAPH_KEY, G, meta)


# ---------------------------------------------------------------------------
# Unit tests – nearest_node
# ---------------------------------------------------------------------------

class TestNearestNode:
    """app.graph.router.nearest_node"""

    def test_returns_closest_node(self):
        from app.graph.router import nearest_node

        G = _make_linear_graph()
        # Query point almost exactly on node A
        node = nearest_node(G, 77.620, 12.930)
        assert node == "A"

    def test_midpoint_snaps_to_nearer_node(self):
        from app.graph.router import nearest_node

        G = _make_linear_graph()
        # Midway between A and B but slightly closer to B
        node = nearest_node(G, 77.6235, 12.934)
        assert node == "B"


# ---------------------------------------------------------------------------
# Unit tests – compute_shortest_path
# ---------------------------------------------------------------------------

class TestComputeShortestPath:
    """app.graph.router.compute_shortest_path"""

    def test_linear_path_distance_and_time(self):
        from app.graph.router import compute_shortest_path

        G = _make_linear_graph()
        path, dist, eta, coords = compute_shortest_path(G, "A", "C")

        assert path == ["A", "B", "C"]
        assert dist == 1400.0  # 600 + 800
        assert eta == pytest.approx(100.8)
        assert len(coords) == 3
        assert coords[0] == (77.620, 12.930)
        assert coords[-1] == (77.630, 12.940)

    def test_diamond_picks_faster_route(self):
        from app.graph.router import compute_shortest_path

        G = _make_diamond_graph()
        path, dist, eta, _coords = compute_shortest_path(G, "A", "B")

        # Shortest by travel_time: A → C → B (30 + 20 = 50s)
        assert path == ["A", "C", "B"]
        assert eta == 50.0
        assert dist == 1300.0  # 900 + 400

    def test_parallel_edges_picks_faster(self):
        from app.graph.router import compute_shortest_path

        G = _make_parallel_edge_graph()
        path, dist, eta, _coords = compute_shortest_path(G, "A", "B")

        assert path == ["A", "B"]
        assert eta == 15.0  # fast edge wins
        assert dist == 600.0  # fast edge distance (not 300)


# ---------------------------------------------------------------------------
# Endpoint tests – POST /api/v1/route
# ---------------------------------------------------------------------------

class TestRouteSuccess:
    """Basic successful route computation."""

    def test_returns_200_with_correct_shape(self, client: TestClient):
        _populate_cache(_make_linear_graph())

        resp = client.post(
            f"{settings.API_V1_STR}/route",
            json={
                "city": PLACE,
                "origin": [77.620, 12.930],
                "destination": [77.630, 12.940],
                "vehicle_profile": {"vehicle_class": "car"},
                "traffic_aware": False,
            },
        )
        assert resp.status_code == 200
        body = resp.json()

        assert body["method"] == "dijkstra"
        assert body["blocked_edges"] == []

        unconstrained = body["unconstrained"]
        assert len(unconstrained["path"]) == 3
        assert unconstrained["distance_m"] == 1400.0
        assert unconstrained["eta_s"] == 100.8
        assert unconstrained["feasible_for_profile"] is True

        # best == unconstrained in baseline
        assert body["best"] == body["unconstrained"]

    def test_path_coords_are_lng_lat(self, client: TestClient):
        _populate_cache(_make_linear_graph())

        resp = client.post(
            f"{settings.API_V1_STR}/route",
            json={
                "city": PLACE,
                "origin": [77.620, 12.930],
                "destination": [77.630, 12.940],
            },
        )
        body = resp.json()
        first = body["unconstrained"]["path"][0]
        last = body["unconstrained"]["path"][-1]
        assert first == [77.620, 12.930]
        assert last == [77.630, 12.940]


class TestRouteWeightSelection:
    """Dijkstra picks shortest-by-travel_time, not shortest-by-distance."""

    def test_diamond_prefers_faster_path(self, client: TestClient):
        _populate_cache(_make_diamond_graph())

        resp = client.post(
            f"{settings.API_V1_STR}/route",
            json={
                "city": PLACE,
                "origin": [77.620, 12.930],
                "destination": [77.630, 12.940],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        route = body["unconstrained"]

        # Via C: travel_time = 30 + 20 = 50s (faster), distance = 900 + 400 = 1300m
        assert route["eta_s"] == 50.0
        assert route["distance_m"] == 1300.0
        # Path goes through intermediate node C
        assert len(route["path"]) == 3


class TestRouteParallelEdges:
    """MultiDiGraph parallel edges: fastest edge selected."""

    def test_uses_faster_parallel_edge(self, client: TestClient):
        _populate_cache(_make_parallel_edge_graph())

        resp = client.post(
            f"{settings.API_V1_STR}/route",
            json={
                "city": PLACE,
                "origin": [77.620, 12.930],
                "destination": [77.625, 12.935],
            },
        )
        assert resp.status_code == 200
        route = resp.json()["unconstrained"]
        assert route["eta_s"] == 15.0  # fast edge
        assert route["distance_m"] == 600.0  # fast edge distance


class TestRouteGraphNotFound:
    """Missing graph returns 404."""

    def test_returns_404_when_graph_not_loaded(self, client: TestClient):
        resp = client.post(
            f"{settings.API_V1_STR}/route",
            json={
                "city": "Unloaded City, Nowhere",
                "origin": [77.0, 12.0],
                "destination": [77.1, 12.1],
            },
        )
        assert resp.status_code == 404
        assert "not loaded" in resp.json()["detail"].lower()


class TestRouteFeasibility:
    """Baseline always marks routes as feasible."""

    def test_feasible_for_profile_is_true(self, client: TestClient):
        _populate_cache(_make_linear_graph())

        resp = client.post(
            f"{settings.API_V1_STR}/route",
            json={
                "city": PLACE,
                "origin": [77.620, 12.930],
                "destination": [77.630, 12.940],
                "vehicle_profile": {
                    "vehicle_class": "heavy_truck",
                    "weight_t": 40.0,
                    "height_m": 4.5,
                },
            },
        )
        assert resp.status_code == 200
        assert resp.json()["unconstrained"]["feasible_for_profile"] is True
        assert resp.json()["best"]["feasible_for_profile"] is True
