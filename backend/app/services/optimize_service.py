"""OptimizeService – render a named or custom scenario and run a solver over it.

Bridges the solver library (``ScenarioRegistry`` + ``ORToolsSolver``) to the
optimize request/response schemas. No optimization logic lives here; this layer
only resolves the scenario and maps results.
"""

from __future__ import annotations

import math
from typing import Optional

import networkx as nx

from app.algorithms.models import Scenario, Stop, Vehicle
from app.algorithms.ortools_solver import ORToolsSolver
from app.algorithms.scenarios import ScenarioRegistry, scenario_registry
from app.core.logging import get_logger
from app.schemas.optimize import (
    CustomScenarioRequest,
    NamedScenarioRequest,
    OptimizeRequest,
    OptimizeResponse,
    OptimizeRoute,
)

logger = get_logger("marga.services.optimize")

_EARTH_RADIUS_M = 6_371_000.0
_DEFAULT_SPEED_MS = 50.0 * 1000.0 / 3600.0  # 50 km/h


def _haversine_m(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
    )
    return _EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class OptimizeService:
    """Run a named or custom scenario through a supported solver."""

    def __init__(
        self,
        scenarios: Optional[ScenarioRegistry] = None,
        time_limit_ms: int = 10_000,
    ) -> None:
        self._scenarios = scenarios or scenario_registry
        self.time_limit_ms = time_limit_ms

    def _build_custom_scenario(self, req: CustomScenarioRequest) -> Scenario:
        depot = req.depot
        stops_list = list(req.stops)

        all_points = [(depot.lng, depot.lat, depot.id, depot.demand)]
        for s in stops_list:
            all_points.append((s.lng, s.lat, s.id, s.demand))

        graph = nx.MultiDiGraph()
        for idx, (lng, lat, pid, _d) in enumerate(all_points):
            graph.add_node(idx, x=lng, y=lat, pid=pid)

        n = len(all_points)
        for i in range(n):
            lng1, lat1, _pid1, _d1 = all_points[i]
            for j in range(n):
                if i == j:
                    continue
                lng2, lat2, _pid2, _d2 = all_points[j]
                length_m = _haversine_m(lng1, lat1, lng2, lat2)
                travel_time_s = length_m / _DEFAULT_SPEED_MS if _DEFAULT_SPEED_MS > 0 else 0.0
                graph.add_edge(i, j, length=length_m, travel_time=travel_time_s)
                graph.add_edge(j, i, length=length_m, travel_time=travel_time_s)

        pid_to_gnode = {p[2]: idx for idx, p in enumerate(all_points)}
        gnode_to_pid = {idx: p[2] for idx, p in enumerate(all_points)}

        scenario_stops = []
        for gnode, (lng, lat, pid, demand) in enumerate(all_points):
            scenario_stops.append(
                Stop(
                    id=pid,
                    lng=lng,
                    lat=lat,
                    x=lng,
                    y=lat,
                    demand=demand,
                )
            )

        vehicles = [
            Vehicle(id=v.id, capacity=v.capacity) for v in req.vehicles
        ]

        depot_stop = next((s for s in scenario_stops if s.id == depot.id), None)
        if depot_stop is None:
            depot_stop = Stop(id=depot.id, lng=depot.lng, lat=depot.lat, x=depot.lng, y=depot.lat, demand=0)

        time_windows = None
        if req.time_windows:
            time_windows = {
                tw.stop_id: (tw.earliest, tw.latest) for tw in req.time_windows
            }

        return Scenario(
            graph=graph,
            stops=scenario_stops,
            vehicles=vehicles,
            depot=depot_stop,
            seed=req.seed if req.seed is not None else 0,
            time_windows=time_windows,
        )

    def optimize(self, req: OptimizeRequest) -> OptimizeResponse:
        if isinstance(req, NamedScenarioRequest):
            try:
                scenario = self._scenarios.get(req.scenario_id, seed=req.seed)
            except KeyError as exc:
                raise ValueError(f"Unknown scenario_id '{req.scenario_id}'") from exc

            solution = ORToolsSolver(scenario, time_limit_ms=self.time_limit_ms).solve()

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
        else:
            scenario = self._build_custom_scenario(req)

            solution = ORToolsSolver(scenario, time_limit_ms=self.time_limit_ms).solve()

            if not solution.feasible:
                raise ValueError("No feasible routing solution for custom scenario")

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
                "Optimized custom scenario solver=%s cost=%.2f vehicles=%d",
                req.solver,
                solution.total_cost,
                solution.vehicles_used,
            )

            return OptimizeResponse(
                solver=req.solver,
                scenario_id="custom",
                total_cost=round(solution.total_cost, 2),
                runtime_ms=runtime_ms,
                vehicles_used=solution.vehicles_used,
                routes=routes,
            )
