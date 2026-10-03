from __future__ import annotations

from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator


# Solver
OptSolver = Literal["ortools"]


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


class OptimizeResponse(BaseModel):
    """Result returned after solving a named or custom scenario."""

    solver: str = Field(..., description="Solver used", examples=["ortools"])
    scenario_id: str = Field(..., description="Scenario identifier run")
    total_cost: float = Field(..., ge=0.0, description="Total solution cost")
    runtime_ms: float = Field(..., ge=0.0, description="Solver runtime in ms")
    vehicles_used: int = Field(..., ge=0, description="Number of vehicles used")
    routes: List[OptimizeRoute] = Field(
        default_factory=list, description="Route plans per vehicle"
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
        description="Solver to run (currently only 'ortools').",
        examples=["ortools"],
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
        description="Solver to run (currently only 'ortools').",
        examples=["ortools"],
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


OptimizeRequest = Annotated[
    Union[NamedScenarioRequest, CustomScenarioRequest],
    Field(discriminator="mode"),
]
