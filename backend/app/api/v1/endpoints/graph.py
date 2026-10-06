"""Versioned graph endpoints: load, list, and retrieve cached graph metadata."""

from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import APIRouter, HTTPException, status

from app.core.logging import get_logger
from app.schemas.graph import GraphLoadRequest, GraphLoadResponse, GraphMetadataListResponse
from app.services.graph_service import GraphService

router = APIRouter()
logger = get_logger("marga.api.v1.graph")

_graph_service = GraphService()
_executor = ThreadPoolExecutor(max_workers=2)

_LOADING_ERROR_DETAIL = "OpenStreetMap data could not be fetched. Verify the place name and try again."


@router.post(
    "/graphs/load",
    response_model=GraphLoadResponse,
    status_code=status.HTTP_200_OK,
    summary="Load an OSM road graph",
    description="Fetch a drivable road graph for the given place name from OpenStreetMap. "
    "The result is cached in memory for subsequent requests.",
)
def load_graph(body: GraphLoadRequest) -> GraphLoadResponse:
    """
    Blocking OSMnx call is dispatched to a thread pool so the async event
    loop stays responsive.
    """
    try:
        future = _executor.submit(
            _graph_service.load, body.place, body.force_reload
        )
        result = future.result(timeout=120)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_LOADING_ERROR_DETAIL,
        )
    except Exception:
        logger.exception("Unexpected error loading graph for place=%s", body.place)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="An unexpected error occurred while loading graph data.",
        )
    return result


@router.get(
    "/graphs",
    response_model=GraphMetadataListResponse,
    status_code=status.HTTP_200_OK,
    summary="List cached graphs",
    description="Return metadata for every graph currently held in the in-memory cache.",
)
def list_graphs() -> GraphMetadataListResponse:
    """Return metadata for all cached graphs."""
    metadata = _graph_service.list_metadata()
    return GraphMetadataListResponse(graphs=metadata, count=len(metadata))


@router.get(
    "/graphs/{graph_key}",
    response_model=GraphLoadResponse,
    status_code=status.HTTP_200_OK,
    summary="Get cached graph metadata",
    description="Return metadata for a single cached graph identified by its deterministic key.",
)
def get_graph(graph_key: str) -> GraphLoadResponse:
    """Return cached metadata for a specific graph key, or 404."""
    metadata = _graph_service.get_metadata(graph_key)
    if metadata is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No cached graph found for key '{graph_key}'.",
        )
    return GraphLoadResponse(
        message="Graph metadata retrieved",
        graph_key=graph_key,
        metadata=metadata,
    )
