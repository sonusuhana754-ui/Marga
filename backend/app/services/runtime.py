"""Process-wide service instances shared by the HTTP endpoints.

A rolling volatility window only means anything if it survives across
requests — its whole purpose is to accumulate observations over time — so the
feed, graph cache, and optimize service are built once here instead of per
request.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.feeds.tomtom import TomTomFlow
from app.services.graph_service import GraphService
from app.services.optimize_service import OptimizeService

settings = get_settings()

#: Shared OSM graph cache (key → NetworkX graph).
graph_service = GraphService()

#: Live traffic feed. Unconfigured when ``TOMTOM_API_KEY`` is empty, in which
#: case every call returns ``None`` and the API reports no traffic.
traffic_feed = TomTomFlow(settings.TOMTOM_API_KEY)

#: Optimizer bound to the shared feed and graph cache. Its per-graph rolling
#: windows accumulate real observations across requests.
optimize_service = OptimizeService(feed=traffic_feed, graph_service=graph_service)
