"""Versioned optimize endpoint: run a solver over a named in-code scenario."""

from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, status

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
    summary="Optimize a named scenario",
    description="Run a solver (currently 'ortools') over one of the deterministic "
    "in-code scenarios by scenario_id with an optional seed.",
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
        logger.exception("Unexpected error optimizing scenario_id=%s", body.scenario_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while optimizing the scenario.",
        )
    return result
