"""Versioned route endpoint: compute shortest-path route for a single vehicle."""

from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, status

from app.core.logging import get_logger
from app.schemas.route import RouteRequest, RouteResponse
from app.services.route_service import RouteService

router = APIRouter()
logger = get_logger("marga.api.v1.route")

_route_service = RouteService()
_executor = ThreadPoolExecutor(max_workers=2)


@router.post(
    "/route",
    response_model=RouteResponse,
    status_code=status.HTTP_200_OK,
    summary="Compute shortest-path route",
    description="Dijkstra shortest path by travel_time over the cached road graph. "
    "Origin and destination are [lng, lat] pairs snapped to the nearest road node.",
)
def compute_route(body: RouteRequest) -> RouteResponse:
    try:
        future = _executor.submit(_route_service.route, body)
        result = future.result(timeout=30)
    except ValueError as exc:
        detail = str(exc)
        if "No cached graph" in detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Graph not loaded for city '{body.city}'. Load it first via POST /api/v1/graphs/load.",
            )
        if "No path" in detail or "Node" in detail:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=detail,
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
        )
    except Exception:
        logger.exception("Unexpected error computing route for city=%s", body.city)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while computing the route.",
        )
    return result
