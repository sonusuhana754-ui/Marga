"""Versioned optimize endpoint: run a solver over named or custom scenarios."""

from concurrent.futures import ThreadPoolExecutor
from typing import Annotated

from fastapi import APIRouter, HTTPException, status, Body

from app.core.logging import get_logger
from app.schemas.optimize import OptimizeRequest, OptimizeResponse
from app.services.optimize_service import OptimizeService

router = APIRouter()
logger = get_logger("marga.api.v1.optimize")

_optimize_service = OptimizeService()
_executor = ThreadPoolExecutor(max_workers=2)


@router.post(
    "/optimize",
    response_model=OptimizeResponse,
    status_code=status.HTTP_200_OK,
    summary="Optimize a scenario (named or custom)",
    description=(
        "Run a solver over either a deterministic in-code scenario (mode='named') "
        "or a custom static scenario (mode='custom'). Solvers: 'ortools' (classical "
        "baseline), 'qpso' (fixed-schedule QPSO), 'va_qpso' (volatility-adaptive QPSO). "
        "QPSO responses include a measured convergence trace. "
        "Custom scenarios use a synthetic, straight-line travel-time approximation "
        "(complete in-memory graph with haversine distances and the existing default speed) "
        "— not real road-network routing."
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
