"""Versioned benchmark endpoint: real repeated-run solver comparison."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Body, HTTPException, status

from app.core.logging import get_logger
from app.schemas.benchmark import BenchmarkRequest, BenchmarkResponse
from app.services.benchmark_service import BenchmarkService

router = APIRouter()
logger = get_logger("marga.api.v1.benchmark")

_benchmark_service = BenchmarkService()
# Solvers run inside this pool because OR-Tools holds the GIL for long stretches
# and a benchmark request is comparatively heavy.
_executor = ThreadPoolExecutor(max_workers=2)


@router.post(
    "/benchmark",
    response_model=BenchmarkResponse,
    status_code=status.HTTP_200_OK,
    summary="Benchmark registered solvers on a named scenario",
    description=(
        "Runs each requested solver `repeats` times on a deterministic in-code "
        "scenario and reports best cost, gap versus the best solver, runtime "
        "spread, and any constraint violations. Every value is measured during "
        "this request — nothing is hard-coded or cached."
    ),
)
def benchmark(body: BenchmarkRequest = Body(...)) -> BenchmarkResponse:
    try:
        future = _executor.submit(_benchmark_service.run, body)
        result = future.result(timeout=120)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Benchmark did not finish within the time limit.",
        )
    except Exception:
        logger.exception("Unexpected error benchmarking scenario_id=%s", body.scenario_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while running the benchmark.",
        )
    return result


@router.get(
    "/benchmark/solvers",
    summary="List registered solvers",
    description="Solver ids accepted by /optimize and /benchmark, with metadata.",
)
def list_solvers() -> dict:
    from app.algorithms.registry import describe

    return describe()