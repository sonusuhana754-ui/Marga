"""Versioned optimize endpoint: run a solver over named or custom scenarios."""

from concurrent.futures import ThreadPoolExecutor
from typing import Annotated

from fastapi import APIRouter, HTTPException, status, Body

from app.core.logging import get_logger
from app.schemas.optimize import OptimizeRequest, OptimizeResponse
from app.services.runtime import optimize_service as _optimize_service

router = APIRouter()
logger = get_logger("marga.api.v1.optimize")

_executor = ThreadPoolExecutor(max_workers=2)


@router.post(
    "/optimize",
    response_model=OptimizeResponse,
    status_code=status.HTTP_200_OK,
    summary="Optimize a scenario (named, custom, or graph)",
    description=(
        "Run a solver over an in-code scenario (mode='named'), a custom static "
        "scenario (mode='custom'), or a fleet instance generated from a real "
        "OSM road network (mode='graph'). Solvers: 'ortools' (classical "
        "baseline), 'qpso' (fixed-β QPSO), 'va_qpso' (volatility-adaptive QPSO). "
        "Graph mode returns road-following route geometry and, when a traffic "
        "feed is configured, the live readings used to drive adaptive β. "
        "Custom scenarios use a straight-line, haversine travel-time "
        "approximation — not real road routing."
    ),
)
def optimize(body: OptimizeRequest) -> OptimizeResponse:
    try:
        future = _executor.submit(_optimize_service.optimize, body)
        result = future.result(timeout=60)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Solver did not finish within the time limit.",
        )
    except Exception:
        try:
            scenario_id = getattr(body, "scenario_id", None)
        except Exception:
            scenario_id = None
        logger.exception("Unexpected error optimizing scenario_id=%s", scenario_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while optimizing the scenario.",
        )
    return result
