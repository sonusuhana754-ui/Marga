from __future__ import annotations

from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator

from app.algorithms.registry import ABLATION_ARMS, DEFAULT_SOLVER
from app.schemas.common import ConvergencePoint

__all__ = [
    "ConvergencePoint",
    "CustomScenarioRequest",
    "CustomStop",
    "CustomTimeWindow",
    "CustomVehicle",
    "GraphRef",
    "GraphScenarioRequest",
    "NamedScenarioRequest",
    "OptSolver",
    "OptimizeRequest",
    "OptimizeResponse",
    "OptimizeRoute",
    "ScenarioPoint",
    "TrafficSnapshot",
]


# Solver
#:
#: The three arms registered in `app.algorithms.registry`. ``ortools`` is the
#: classical baseline, ``qpso`` is fixed-schedule QPSO, and ``va_qpso`` is the
#: volatility-adaptive variant this project contributes. All three are accepted
#: because the design doc's ablation is invalid without the fixed-beta anchor.
OptSolver = Literal["ortools", "qpso", "va_qpso"]


class OptimizeRoute(BaseModel):
    """A single vehicle's route plan produced by the solver."""

    vehicle_id: int = Field(..., ge=0, description="Vehicle index")
    stop_sequence: List[int] = Field(
        ...,
        description="Ordered stop indices; starts and ends at the depot (0)",
    )
    load: int = Field(..., ge=0, description="Total load carried by the vehicle")
    distance_m: float = Field(..., ge=0.0, description="Route distance in metres")
    time_s: float = Field(..., ge=0.0, description="Route travel time in seconds")
    geometry: List[List[float]] = Field(
        default_factory=list,
        description=(
            "Road-following polyline as [lng, lat] vertices, present when the "
            "scenario was built from a real OSM graph (mode='graph'). Empty "
            "for in-code scenarios, which have no road geometry to draw — the "
            "client must not invent one."
        ),
    )


class ScenarioPoint(BaseModel):
    """A depot or delivery stop as the backend actually resolved it."""

    id: int = Field(..., ge=0, description="Stop index (0 is the depot)")
    lng: float = Field(..., description="Longitude in degrees (WGS84)")
    lat: float = Field(..., description="Latitude in degrees (WGS84)")
    demand: int = Field(..., ge=0, description="Demand at this stop (units)")
    is_depot: bool = Field(default=False, description="True for the depot")


class GraphRef(BaseModel):
    """Reference to the OSM graph a scenario was built on."""

    graph_key: str = Field(..., description="Cache key of the loaded graph")
    place: str = Field(..., description="Place label or point description")
    center: Optional[List[float]] = Field(
        None, description="Centre of the loaded area as [lng, lat]"
    )
    bounds: Optional[List[float]] = Field(
        None,
        description="Loaded area as [min_lng, min_lat, max_lng, max_lat], for framing the map",
    )
    nodes: int = Field(..., ge=0, description="Nodes in the loaded graph")
    edges: int = Field(..., ge=0, description="Directed edges in the loaded graph")
    total_length_km: float = Field(
        ..., ge=0.0, description="Total road length in the loaded graph (km)"
    )


class TrafficSnapshot(BaseModel):
    """Live traffic readings consumed by the adaptive-β path for this run."""

    source: str = Field(..., description="Feed identifier, e.g. 'tomtom'")
    observed_at: str = Field(
        ..., description="UTC ISO-8601 timestamp of the probe batch"
    )
    probes: int = Field(..., ge=0, description="Successful probe readings")
    failed: int = Field(..., ge=0, description="Probes that returned no data")
    mean_current_kmh: float = Field(
        ..., ge=0.0, description="Mean observed speed across probes (km/h)"
    )
    mean_free_flow_kmh: float = Field(
        ..., ge=0.0, description="Mean free-flow speed across probes (km/h)"
    )
    readings: List[dict] = Field(
        default_factory=list,
        description="Per-probe readings: leg, coordinates, speeds, delay ratio",
    )


class OptimizeResponse(BaseModel):
    """Result returned after solving a named or custom scenario."""

    solver: str = Field(..., description="Solver used", examples=["va_qpso"])
    scenario_id: str = Field(..., description="Scenario identifier run")
    total_cost: float = Field(..., ge=0.0, description="Total solution cost")
    runtime_ms: float = Field(..., ge=0.0, description="Solver runtime in ms")
    vehicles_used: int = Field(..., ge=0, description="Number of vehicles used")
    routes: List[OptimizeRoute] = Field(
        default_factory=list, description="Route plans per vehicle"
    )
    feasible: bool = Field(
        ...,
        description=(
            "False when the solver could not produce a solution the fleet may "
            "legally run (over-capacity, over-fleet, or time-window violation)."
        ),
    )
    total_distance_m: float = Field(
        default=0.0, ge=0.0, description="Summed route distance in metres"
    )
    total_time_s: float = Field(
        default=0.0, ge=0.0, description="Summed route travel time in seconds"
    )
    fleet_utilisation: float = Field(
        default=0.0,
        ge=0.0,
        description="Total demand / total fleet capacity for this scenario.",
    )
    convergence: List[ConvergencePoint] = Field(
        default_factory=list,
        description=(
            "Best-found cost per iteration. Populated for the QPSO variants, "
            "where it is measured; empty for solvers that report no trace."
        ),
    )
    solver_diagnostics: dict = Field(
        default_factory=dict,
        description="Solver-specific diagnostics (iterations, evaluations, mean beta).",
    )
    points: List[ScenarioPoint] = Field(
        default_factory=list,
        description=(
            "Depot and stops as resolved by the backend. Populated for every "
            "mode; when present the client must draw these instead of its own "
            "hard-coded pins."
        ),
    )
    graph: Optional[GraphRef] = Field(
        default=None,
        description="The OSM graph this scenario ran on (mode='graph' only).",
    )
    traffic: Optional[TrafficSnapshot] = Field(
        default=None,
        description=(
            "Live traffic readings taken before this solve, if a feed is "
            "configured. Null means no feed was consulted — never a "
            "simulated one."
        ),
    )


# Named scenario
class NamedScenarioRequest(BaseModel):
    mode: Literal["named"] = Field(
        ...,
        description="Request mode: use an in-code named scenario.",
    )
    scenario_id: str = Field(
        ...,
        min_length=1,
        description="Identifier of a deterministic in-code scenario.",
        examples=["grid_cvrp_8"],
    )
    solver: OptSolver = Field(
        ...,
        description=(
            "Solver to run. 'ortools' is the classical baseline, 'qpso' is "
            "fixed-schedule QPSO, 'va_qpso' is the volatility-adaptive QPSO this "
            "project contributes."
        ),
        examples=[DEFAULT_SOLVER],
    )
    seed: Optional[int] = Field(
        default=None,
        ge=0,
        description="Optional PRNG seed; defaults to the scenario's seed.",
    )


# Custom scenario
class CustomStop(BaseModel):
    id: int = Field(..., ge=0, description="Stop/depot identifier.")
    lng: float = Field(
        ...,
        description="Longitude in degrees (WGS84). Must be between -180 and 180.",
    )
    lat: float = Field(
        ...,
        description="Latitude in degrees (WGS84). Must be between -90 and 90.",
    )
    demand: int = Field(..., ge=0, description="Demand for this stop (units).")


class CustomVehicle(BaseModel):
    id: int = Field(..., ge=0, description="Vehicle identifier.")
    capacity: int = Field(
        ...,
        gt=0,
        description="Vehicle capacity (units). Positive. Per-vehicle only.",
    )


class CustomTimeWindow(BaseModel):
    stop_id: int = Field(..., ge=0, description="Stop/depot ID this window applies to.")
    earliest: float = Field(
        ..., ge=0.0, description="Earliest service/start time in the same time units as travel time."
    )
    latest: float = Field(
        ..., ge=0.0, description="Latest service/end time in the same time units as travel time."
    )

    @model_validator(mode="after")
    def _earliest_le_latest(self) -> "CustomTimeWindow":
        if self.latest < self.earliest:
            raise ValueError("latest must be >= earliest")
        return self


class CustomScenarioRequest(BaseModel):
    mode: Literal["custom"] = Field(
        ...,
        description="Request mode: build a custom static scenario in memory.",
    )
    solver: OptSolver = Field(
        ...,
        description=(
            "Solver to run. 'ortools' is the classical baseline, 'qpso' is "
            "fixed-schedule QPSO, 'va_qpso' is the volatility-adaptive QPSO this "
            "project contributes."
        ),
        examples=[DEFAULT_SOLVER],
    )
    seed: Optional[int] = Field(
        default=None,
        ge=0,
        description="Optional PRNG seed used when generating any internal randomness.",
    )
    depot: CustomStop = Field(
        ...,
        description="Depot point. Coordinates are lat/lng (WGS84).",
    )
    stops: List[CustomStop] = Field(
        default_factory=list,
        description="List of delivery stops (lat/lng WGS84).",
    )
    vehicles: List[CustomVehicle] = Field(
        ..., min_length=1, description="List of vehicles (per-vehicle capacity only)."
    )
    time_windows: Optional[List[CustomTimeWindow]] = Field(
        default=None,
        description="Optional time windows per stop/depot (CVRP if None).",
    )

    @model_validator(mode="after")
    def _validate_geographic_and_consistency(self) -> "CustomScenarioRequest":
        def _valid_pt(p: CustomStop) -> None:
            if p.lat < -90.0 or p.lat > 90.0:
                raise ValueError("lat must be between -90 and 90")
            if p.lng < -180.0 or p.lng > 180.0:
                raise ValueError("lng must be between -180 and 180")

        _valid_pt(self.depot)
        for s in self.stops:
            _valid_pt(s)

        all_stop_ids = set([self.depot.id])
        for s in self.stops:
            all_stop_ids.add(s.id)

        vehicle_ids = set()
        for v in self.vehicles:
            if v.id in vehicle_ids:
                raise ValueError(f"duplicate vehicle id {v.id}")
            vehicle_ids.add(v.id)

        combined_ids = set([self.depot.id])
        for s in self.stops:
            if s.id in combined_ids:
                raise ValueError(f"duplicate stop/depot id {s.id}")
            combined_ids.add(s.id)

        if self.depot.demand != 0:
            raise ValueError("depot demand must be 0")

        total_demand = sum(s.demand for s in self.stops)
        total_capacity = sum(v.capacity for v in self.vehicles)
        if total_demand > total_capacity:
            raise ValueError("total capacity must be >= total demand")

        if self.time_windows:
            tw_stop_ids = set()
            for tw in self.time_windows:
                if tw.stop_id not in all_stop_ids:
                    raise ValueError(f"time window references unknown stop_id {tw.stop_id}")
                if tw.stop_id in tw_stop_ids:
                    raise ValueError(f"duplicate time window for stop_id {tw.stop_id}")
                tw_stop_ids.add(tw.stop_id)

        return self


# Graph-backed scenario: build a fleet instance from a real OSM road network
class GraphScenarioRequest(BaseModel):
    mode: Literal["graph"] = Field(
        ...,
        description="Request mode: generate a scenario from a real OSM graph.",
    )
    solver: OptSolver = Field(
        ...,
        description="Solver to run (see NamedScenarioRequest.solver).",
        examples=[DEFAULT_SOLVER],
    )
    seed: int = Field(
        default=0,
        ge=0,
        description="PRNG seed for stop generation; same seed + graph = same scenario.",
    )
    graph_key: Optional[str] = Field(
        default=None,
        description="Key of an already-loaded graph (from POST /graphs/load).",
    )
    center: Optional[List[float]] = Field(
        default=None,
        min_length=2,
        max_length=2,
        description="Alternative to graph_key: [lng, lat]. The graph within "
        "`dist_m` is downloaded on demand (slow on a cold cache).",
        examples=[[77.5946, 12.9716]],
    )
    dist_m: int = Field(
        default=1200,
        ge=300,
        le=3000,
        description="Radius in metres used with `center`.",
    )
    stops: int = Field(
        default=18,
        ge=4,
        le=80,
        description="Number of delivery stops drawn from real road junctions.",
    )
    vehicles: int = Field(default=3, ge=1, le=20, description="Number of vehicles.")
    capacity: int = Field(default=20, ge=1, description="Capacity of each vehicle.")
    traffic: bool = Field(
        default=True,
        description=(
            "Probe live traffic for this scenario's legs before solving so the "
            "adaptive-β window receives real observations. Has no effect when "
            "no feed is configured."
        ),
    )

    @model_validator(mode="after")
    def _require_graph_target(self) -> "GraphScenarioRequest":
        if self.graph_key is None and self.center is None:
            raise ValueError("either 'graph_key' or 'center' must be provided")
        if self.center is not None:
            lng, lat = float(self.center[0]), float(self.center[1])
            if not -180.0 <= lng <= 180.0:
                raise ValueError("center lng must be between -180 and 180")
            if not -90.0 <= lat <= 90.0:
                raise ValueError("center lat must be between -90 and 90")
        return self


OptimizeRequest = Annotated[
    Union[NamedScenarioRequest, CustomScenarioRequest, GraphScenarioRequest],
    Field(discriminator="mode"),
]
