"""Live traffic endpoints: probe the current speeds over a loaded graph."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.core.logging import get_logger
from app.schemas.optimize import TrafficSnapshot
from app.schemas.traffic import TrafficSnapshotResponse
from app.services.runtime import graph_service, traffic_feed

router = APIRouter()
logger = get_logger("marga.api.v1.traffic")


@router.get(
    "/traffic/snapshot",
    response_model=TrafficSnapshotResponse,
    status_code=status.HTTP_200_OK,
    summary="Read live traffic speeds over a loaded graph",
    description=(
        "Probes the road segments nearest to a spread of graph nodes and "
        "returns TomTom's current vs free-flow speeds with a timestamp. "
        "Returns `configured: false` when no API key is set, and `snapshot: "
        "null` when the feed could not be read — the response never contains "
        "simulated speeds."
    ),
)
def traffic_snapshot(
    graph_key: str = Query(
        ..., description="Key of a graph already loaded via POST /graphs/load"
    ),
    points: int = Query(
        8, ge=1, le=12, description="How many nodes to probe across the graph"
    ),
) -> TrafficSnapshotResponse:
    metadata = graph_service.get_metadata(graph_key)
    if metadata is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No cached graph found for key '{graph_key}'.",
        )

    if not traffic_feed.configured:
        return TrafficSnapshotResponse(
            configured=False,
            graph_key=graph_key,
            detail="No traffic feed configured (TOMTOM_API_KEY is empty). "
            "Volatility stays unmeasured and beta sits at its floor.",
        )

    graph = graph_service.get_graph(graph_key)
    if graph is None or graph.number_of_nodes() == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Graph '{graph_key}' is cached without node data.",
        )

    # Deterministic spread over the graph: insertion order is stable, so two
    # calls with the same arguments probe the same junctions.
    nodes = list(graph.nodes())
    step = max(1, len(nodes) // points)
    coords = []
    for node in nodes[::step][:points]:
        data = graph.nodes[node]
        lng, lat = data.get("x"), data.get("y")
        if lng is None or lat is None:
            continue
        coords.append((float(lng), float(lat)))

    observation = traffic_feed.snapshot(coords)
    if observation is None:
        return TrafficSnapshotResponse(
            configured=True,
            graph_key=graph_key,
            detail="Traffic feed returned no readings for these coordinates "
            "(upstream outage, quota, or no segment data).",
        )

    return TrafficSnapshotResponse(
        configured=True,
        graph_key=graph_key,
        snapshot=TrafficSnapshot(
            source=observation.source,
            observed_at=observation.observed_at,
            probes=observation.probes,
            failed=observation.failed,
            mean_current_kmh=round(observation.mean_current_kmh, 2),
            mean_free_flow_kmh=round(observation.mean_free_flow_kmh, 2),
            readings=observation.readings,
        ),
    )
