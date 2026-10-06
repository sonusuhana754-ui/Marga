"""OptimizeService – render a named or custom scenario and run a solver over it.

Bridges the solver library (``ScenarioRegistry`` + the solver ``registry``) to
the optimize request/response schemas. No optimization logic lives here; this layer
resolves the scenario, dispatches to the requested solver, and maps the result.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import networkx as nx

from app.algorithms import registry as solver_registry
from app.algorithms.models import Scenario, Stop, Vehicle
from app.algorithms.scenario import make_scenario
from app.algorithms.scenarios import ScenarioRegistry, scenario_registry
from app.algorithms.volatility import RollingVolatility
from app.core.logging import get_logger
from app.feeds.tomtom import TomTomFlow, TrafficObservation
from app.graph.cache import _normalize_key
from app.graph.router import compute_shortest_path, nearest_node
from app.schemas.common import ConvergencePoint
from app.schemas.optimize import (
    CustomScenarioRequest,
    GraphRef,
    GraphScenarioRequest,
    NamedScenarioRequest,
    OptimizeRequest,
    OptimizeResponse,
    OptimizeRoute,
    ScenarioPoint,
    TrafficSnapshot,
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


def _diagnostics(solution: Any, solver_id: str) -> Dict[str, Any]:
    """Collect whatever a solver chose to expose, dropping anything absent.

    Solvers attach extra fields with a leading underscore rather than widening
    the shared `Solution` dataclass, so this filters on presence instead of
    hard-coding a list per solver.
    """
    out: Dict[str, Any] = {}
    for attr, key in (
        ("_iterations", "iterations"),
        ("_evaluations", "evaluations"),
        ("_beta_mean", "mean_beta"),
        # Measured β, one value per iteration, plus the solver's β bounds. The
        # frontend charts these directly rather than drawing a synthetic series.
        ("_beta_history", "beta_history"),
        ("_beta_range", "beta_range"),
        ("_volatility_signal", "volatility_signal"),
        ("_beta_mode", "beta_mode"),
        ("_reason", "infeasible_reason"),
    ):
        value = getattr(solution, attr, None)
        if value is not None:
            out[key] = value
    return out


def _convergence(solution: Any) -> List[ConvergencePoint]:
    trace = getattr(solution, "_convergence", None) or []
    return [
        ConvergencePoint(iteration=int(i), best_cost=round(float(c), 2))
        for i, c in trace
    ]


class OptimizeService:
    """Run a named, custom, or graph-derived scenario through a solver."""

    def __init__(
        self,
        scenarios: Optional[ScenarioRegistry] = None,
        time_limit_ms: int = 10_000,
        volatility: Optional[RollingVolatility] = None,
        feed: Optional[TomTomFlow] = None,
        graph_service: Optional[Any] = None,
    ) -> None:
        self._scenarios = scenarios or scenario_registry
        self.time_limit_ms = time_limit_ms
        #: Shared rolling traffic window handed to the adaptive-β solvers. Empty
        #: by default, which pins β at its exploitation floor rather than
        #: pretending a traffic signal exists. Populate it from a real feed to
        #: exercise the adaptive path; see `app.algorithms.volatility`.
        self.volatility = volatility
        #: Live traffic feed. ``None`` or an unconfigured key means every run
        #: reports ``traffic: null`` — never a simulated one.
        self._feed = feed
        self._graph_service = graph_service
        #: One rolling window per graph so observations from one city never
        #: leak into another's β. Created lazily; ``volatility`` (when given)
        #: stays the window for in-code scenarios, so callers that inject one
        #: keep seeing their own object.
        self._windows: Dict[str, RollingVolatility] = {}

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

        scenario_stops = []
        for _gnode, (lng, lat, pid, demand) in enumerate(all_points):
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

    # -- graph-backed scenarios ------------------------------------------------

    def _window_for(self, key: Optional[str]) -> Optional[RollingVolatility]:
        """Rolling volatility window for *key* (``None`` → the injected one).

        Windows are per graph so that observations recorded while routing in
        one city cannot silently raise β in another.
        """
        if key is None:
            return self.volatility
        return self._windows.setdefault(key, RollingVolatility())

    def _resolve_graph(self, req: GraphScenarioRequest):
        """Return ``(graph, graph_key, GraphRef)`` for a graph-mode request.

        Uses the cache when ``graph_key`` is given, otherwise downloads the
        network around ``center`` on demand. Raises ``ValueError`` with a
        message the endpoint turns into a 4xx.
        """
        from app.services.graph_service import GraphService

        if self._graph_service is None:
            self._graph_service = GraphService()

        if req.graph_key:
            graph = self._graph_service.get_graph(req.graph_key)
            metadata = self._graph_service.get_metadata(req.graph_key)
            if graph is None or metadata is None:
                raise ValueError(
                    f"No cached graph '{req.graph_key}'. "
                    "Load it first with POST /api/v1/graphs/load."
                )
            key = req.graph_key
        else:
            response = self._graph_service.load(center=req.center, dist_m=req.dist_m)
            key = response.graph_key
            metadata = response.metadata
            graph = self._graph_service.get_graph(key)
            if graph is None:
                raise ValueError("Graph vanished from cache immediately after load")

        # Routing on a graph with unreachable pairs fails deep inside the
        # solver, so restrict to the largest strongly-connected component up
        # front: every stop can then reach every other stop.
        if not nx.is_strongly_connected(graph):
            component = max(nx.strongly_connected_components(graph), key=len)
            graph = graph.subgraph(component).copy()
            logger.info(
                "Graph %s not strongly connected; using largest component "
                "(%d nodes)",
                key,
                graph.number_of_nodes(),
            )
        if graph.number_of_nodes() <= req.stops:
            raise ValueError(
                f"Graph '{key}' has {graph.number_of_nodes()} routable nodes, "
                f"fewer than the {req.stops} stops requested. Load a larger "
                "area or ask for fewer stops."
            )

        total_length_km = sum(
            d.get("length", 0.0) for _, _, d in graph.edges(data=True)
        ) / 1000.0
        ref = GraphRef(
            graph_key=key,
            place=metadata.place,
            center=metadata.center,
            bounds=metadata.bounds,
            nodes=graph.number_of_nodes(),
            edges=graph.number_of_edges(),
            total_length_km=round(total_length_km, 2),
        )
        return graph, key, ref

    @staticmethod
    def _node_index(scenario: Scenario) -> Dict[int, Any]:
        """Stop index → graph node id (stops are drawn from graph nodes)."""
        graph = scenario.graph
        return {
            i: nearest_node(graph, stop.lng, stop.lat)
            for i, stop in enumerate(scenario.stops)
        }

    @staticmethod
    def _leg(
        scenario: Scenario,
        node_index: Dict[int, Any],
        memo: Dict[Tuple[int, int], Any],
        a: int,
        b: int,
    ):
        """Road path between stop indices *a* and *b*, memoised per request."""
        key = (a, b)
        if key not in memo:
            memo[key] = compute_shortest_path(
                scenario.graph, node_index[a], node_index[b], weight="travel_time"
            )
        return memo[key]

    @staticmethod
    def _greedy_candidate_legs(
        scenario: Scenario, limit: int
    ) -> List[Tuple[int, int]]:
        """Capacity-respecting nearest-neighbour routes, as ``(a, b)`` pairs.

        Used only to choose *which* legs to probe for live traffic before the
        real solve: a cheap construction produces the same depot-to-cluster
        legs the solvers will mostly pick, so the β callback sees legs that
        actually appear in routes.
        """
        stops = scenario.stops
        remaining = set(range(1, len(stops)))
        legs: List[Tuple[int, int]] = []
        for vehicle in scenario.vehicles:
            load = 0
            current = 0
            while remaining:
                candidates = [
                    i for i in remaining if load + stops[i].demand <= vehicle.capacity
                ]
                if not candidates:
                    break
                nxt = min(
                    candidates,
                    key=lambda i: _haversine_m(
                        stops[current].lng, stops[current].lat,
                        stops[i].lng, stops[i].lat,
                    ),
                )
                legs.append((current, nxt))
                load += stops[nxt].demand
                current = nxt
                remaining.discard(nxt)
            if current != 0:
                legs.append((current, 0))
            if len(legs) >= limit:
                break
        if not remaining:
            legs.append((0, 0))  # depot only; keeps the batch non-empty
        return legs[:limit]

    def _observe_traffic(
        self,
        scenario: Scenario,
        window: Optional[RollingVolatility],
        node_index: Dict[int, Any],
        memo: Dict[Tuple[int, int], Any],
    ) -> Optional[TrafficSnapshot]:
        """Probe live traffic for candidate legs and record it for the solver.

        Returns ``None`` when no feed is configured or nothing could be read;
        in that case the window is left exactly as it was, so β falls back to
        its floor and the response reports ``traffic: null``.
        """
        feed = self._feed
        if feed is None or not feed.configured or window is None:
            return None

        probes: Dict[str, Tuple[float, float]] = {}
        baseline_s: Dict[str, float] = {}
        for a, b in self._greedy_candidate_legs(scenario, feed.max_legs):
            try:
                _path, _dist, eta, coords = self._leg(scenario, node_index, memo, a, b)
            except Exception:  # noqa: BLE001 - a bad leg must not kill the run
                continue
            if not coords or eta <= 0:
                continue
            leg_id = f"{a}-{b}"
            midpoint = coords[len(coords) // 2]
            probes[leg_id] = (float(midpoint[0]), float(midpoint[1]))
            baseline_s[leg_id] = float(eta)

        observation = feed.observe_legs(probes, baseline_s)
        if observation is None:
            logger.info(
                "Traffic feed returned no readings (probes=%d)", len(probes)
            )
            return None

        # One batch = one observation per leg for this run. β moves only when
        # a later batch of the *same* leg measures a different travel time.
        window.observe(observation.legs)
        return self._traffic_snapshot(observation)

    @staticmethod
    def _traffic_snapshot(observation: TrafficObservation) -> TrafficSnapshot:
        return TrafficSnapshot(
            source=observation.source,
            observed_at=observation.observed_at,
            probes=observation.probes,
            failed=observation.failed,
            mean_current_kmh=round(observation.mean_current_kmh, 2),
            mean_free_flow_kmh=round(observation.mean_free_flow_kmh, 2),
            readings=observation.readings,
        )

    @staticmethod
    def _points(scenario: Scenario) -> List[ScenarioPoint]:
        depot_id = scenario.depot.id
        return [
            ScenarioPoint(
                id=stop.id,
                lng=stop.lng,
                lat=stop.lat,
                demand=stop.demand,
                is_depot=stop.id == depot_id,
            )
            for stop in scenario.stops
        ]

    @staticmethod
    def _route_geometry(
        scenario: Scenario,
        node_index: Dict[int, Any],
        memo: Dict[Tuple[int, int], Any],
        stop_sequence: Sequence[int],
    ) -> List[List[float]]:
        """Chain the road paths between consecutive stops into one polyline."""
        line: List[List[float]] = []
        for a, b in zip(stop_sequence[:-1], stop_sequence[1:]):
            try:
                _path, _dist, _eta, coords = OptimizeService._leg(
                    scenario, node_index, memo, int(a), int(b)
                )
            except Exception:  # noqa: BLE001 - keep whatever geometry we have
                continue
            for lng, lat in coords:
                point = [round(float(lng), 6), round(float(lat), 6)]
                if not line or line[-1] != point:
                    line.append(point)
        return line

    def _run_solver(self, solver_id: str, scenario: Scenario, window: Optional[RollingVolatility] = None):
        """Instantiate the requested solver with its own constructor kwargs.

        OR-Tools takes a wall-clock limit; the QPSO variants take a swarm budget
        and optionally the rolling volatility window. Passing anything a solver
        does not accept would be a TypeError at call time, so the kwargs are
        chosen per id rather than spread unconditionally.
        """
        cls = solver_registry.get(solver_id)
        if not solver_registry.is_known(solver_id):
            raise ValueError(
                f"Unknown solver '{solver_id}'. "
                f"Available: {', '.join(solver_registry.available())}"
            )

        if solver_id == "ortools":
            return cls(scenario, time_limit_ms=self.time_limit_ms).solve()

        kwargs: Dict[str, Any] = {}
        effective = window if window is not None else self.volatility
        if effective is not None:
            kwargs["volatility"] = effective
        return cls(scenario, **kwargs).solve()

    def optimize(self, req: OptimizeRequest) -> OptimizeResponse:
        graph_ref: Optional[GraphRef] = None
        window: Optional[RollingVolatility]
        node_index: Dict[int, Any] = {}
        memo: Dict[Tuple[int, int], Any] = {}
        traffic: Optional[TrafficSnapshot] = None

        if isinstance(req, GraphScenarioRequest):
            graph, graph_key, graph_ref = self._resolve_graph(req)
            scenario = make_scenario(
                graph,
                seed=req.seed,
                capacity=req.capacity,
                vehicles=req.vehicles,
                num_stops=req.stops,
            )
            scenario_id = f"graph:{graph_key}"
            window = self._window_for(graph_key)
            node_index = self._node_index(scenario)
            if req.traffic:
                traffic = self._observe_traffic(scenario, window, node_index, memo)
        elif isinstance(req, NamedScenarioRequest):
            try:
                scenario = self._scenarios.get(req.scenario_id, seed=req.seed)
            except KeyError as exc:
                raise ValueError(f"Unknown scenario_id '{req.scenario_id}'") from exc
            scenario_id = req.scenario_id
            window = self.volatility
        else:
            scenario = self._build_custom_scenario(req)
            scenario_id = "custom"
            window = self.volatility

        solution = self._run_solver(req.solver, scenario, window)

        if not solution.feasible:
            reason = getattr(solution, "_reason", "no feasible solution found")
            raise ValueError(
                f"No feasible routing solution for scenario '{scenario_id}' "
                f"with solver '{req.solver}': {reason}"
            )

        routes = [
            OptimizeRoute(
                vehicle_id=r.vehicle_id,
                stop_sequence=r.stop_sequence,
                load=r.load,
                distance_m=round(r.distance_m, 2),
                time_s=round(r.time_s, 2),
                geometry=(
                    self._route_geometry(scenario, node_index, memo, r.stop_sequence)
                    if graph_ref is not None
                    else []
                ),
            )
            for r in solution.routes
        ]

        logger.info(
            "Optimized scenario_id=%s solver=%s cost=%.2f vehicles=%d runtime_ms=%.1f",
            scenario_id,
            req.solver,
            solution.total_cost,
            solution.vehicles_used,
            getattr(solution, "_runtime_ms", 0.0),
        )

        diagnostics = _diagnostics(solution, req.solver)
        if traffic is not None:
            diagnostics["traffic_legs_probed"] = traffic.probes

        return OptimizeResponse(
            solver=req.solver,
            scenario_id=scenario_id,
            total_cost=round(solution.total_cost, 2),
            runtime_ms=round(getattr(solution, "_runtime_ms", 0.0), 2),
            vehicles_used=solution.vehicles_used,
            routes=routes,
            feasible=solution.feasible,
            total_distance_m=round(solution.total_distance_m, 2),
            total_time_s=round(solution.total_time_s, 2),
            fleet_utilisation=round(scenario.utilisation, 4),
            convergence=_convergence(solution),
            solver_diagnostics=diagnostics,
            points=self._points(scenario),
            graph=graph_ref,
            traffic=traffic,
        )