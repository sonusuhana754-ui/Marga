"""OptimizeService – render a named scenario and run a solver over it.

Bridges the solver library (``ScenarioRegistry`` + ``ORToolsSolver``) to the
optimize request/response schemas. No optimization logic lives here; this layer
only resolves the scenario and maps results.
"""

from __future__ import annotations

from typing import Optional

from app.algorithms.ortools_solver import ORToolsSolver
from app.algorithms.scenarios import ScenarioRegistry, scenario_registry
from app.core.logging import get_logger
from app.schemas.optimize import OptimizeRequest, OptimizeResponse, OptimizeRoute

logger = get_logger("marga.services.optimize")


class OptimizeService:
    """Run a named in-code scenario through a supported solver."""

    def __init__(
        self,
        scenarios: Optional[ScenarioRegistry] = None,
        time_limit_ms: int = 10_000,
    ) -> None:
        self._scenarios = scenarios or scenario_registry
        self.time_limit_ms = time_limit_ms

    def optimize(self, req: OptimizeRequest) -> OptimizeResponse:
        """Solve the requested named scenario and return the route plan.

        Raises ``KeyError`` for an unknown scenario id and ``ValueError`` if
        the solver cannot produce a feasible solution.
        """
        try:
            scenario = self._scenarios.get(req.scenario_id, seed=req.seed)
        except KeyError as exc:
            raise ValueError(f"Unknown scenario_id '{req.scenario_id}'") from exc

        solution = ORToolsSolver(
            scenario, time_limit_ms=self.time_limit_ms
        ).solve()

        if not solution.feasible:
            raise ValueError(
                f"No feasible routing solution for scenario '{req.scenario_id}'"
            )

        runtime_ms = round(getattr(solution, "_runtime_ms", 0.0), 2)

        routes = [
            OptimizeRoute(
                vehicle_id=r.vehicle_id,
                stop_sequence=r.stop_sequence,
                load=r.load,
                distance_m=round(r.distance_m, 2),
                time_s=round(r.time_s, 2),
            )
            for r in solution.routes
        ]

        logger.info(
            "Optimized scenario_id=%s solver=%s cost=%.2f vehicles=%d",
            req.scenario_id,
            req.solver,
            solution.total_cost,
            solution.vehicles_used,
        )

        return OptimizeResponse(
            solver=req.solver,
            scenario_id=req.scenario_id,
            total_cost=round(solution.total_cost, 2),
            runtime_ms=runtime_ms,
            vehicles_used=solution.vehicles_used,
            routes=routes,
        )
