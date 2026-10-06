"""BenchmarkService – expose the real repeated-run harness over HTTP.

`app.algorithms.benchmark.run_benchmark` already existed and was tested, but was
never reachable from the API, so the dashboard's benchmark view had nothing real
to show. This service is the thin adapter that makes it callable and maps its
dataclasses onto the response schema.

Every number in the response is produced by running the solvers here and now.
"""

from __future__ import annotations

from typing import List, Optional

from app.algorithms import registry as solver_registry
from app.algorithms.benchmark import run_benchmark
from app.algorithms.scenarios import ScenarioRegistry, scenario_registry
from app.core.logging import get_logger
from app.schemas.benchmark import (
    BenchmarkRequest,
    BenchmarkResponse,
    BenchmarkRunOut,
    BenchmarkSolverResult,
)
from app.schemas.common import ConvergencePoint

logger = get_logger("marga.services.benchmark")


class BenchmarkService:
    """Run a repeated-run solver comparison on a named in-code scenario."""

    def __init__(self, scenarios: Optional[ScenarioRegistry] = None) -> None:
        self._scenarios = scenarios or scenario_registry

    def run(self, req: BenchmarkRequest) -> BenchmarkResponse:
        try:
            scenario = self._scenarios.get(req.scenario_id, seed=req.seed)
        except KeyError as exc:
            raise ValueError(f"Unknown scenario_id '{req.scenario_id}'") from exc

        unknown = [s for s in req.solvers if not solver_registry.is_known(s)]
        if unknown:
            raise ValueError(
                f"Unknown solver(s): {', '.join(unknown)}. "
                f"Available: {', '.join(solver_registry.available())}"
            )

        classes = [solver_registry.get(s) for s in req.solvers]
        summary = run_benchmark(
            classes,
            scenario,
            repeats=req.repeats,
            time_limit_ms=req.baseline_time_limit_ms,
        )

        results: List[BenchmarkSolverResult] = []
        for r in summary.results:
            results.append(
                BenchmarkSolverResult(
                    solver_id=r.solver_id,
                    cost=round(r.cost, 2),
                    best_cost=round(r.best_cost, 2),
                    convergence=[
                        ConvergencePoint(iteration=int(i), best_cost=round(float(c), 2))
                        for i, c in r.convergence
                    ],
                    gap_pct=round(r.gap_pct, 2),
                    feasible=r.feasible,
                    runtime_ms_mean=round(r.runtime_ms_mean, 2),
                    runtime_ms_min=round(r.runtime_ms_min, 2),
                    runtime_ms_max=round(r.runtime_ms_max, 2),
                    vehicles_used_min=r.vehicles_used_min,
                    vehicles_used_max=r.vehicles_used_max,
                    total_distance_m=round(r.total_distance_m, 2),
                    total_time_s=round(r.total_time_s, 2),
                    runs=[
                        BenchmarkRunOut(
                            cost=round(run.cost, 2),
                            runtime_ms=round(run.runtime_ms, 2),
                            vehicles_used=run.vehicles_used,
                        )
                        for run in r.runs
                    ],
                    violations=list(r.violations),
                )
            )

        best = min(
            (r.cost for r in summary.results if r.feasible),
            default=float("inf"),
        )

        logger.info(
            "Benchmark scenario_id=%s repeats=%d solvers=%s best=%s",
            req.scenario_id,
            req.repeats,
            req.solvers,
            best,
        )

        return BenchmarkResponse(
            scenario_id=req.scenario_id,
            scenario_seed=summary.scenario_seed,
            repeats=req.repeats,
            best_known=round(best, 2),
            fleet_utilisation=round(scenario.utilisation, 4),
            results=results,
        )