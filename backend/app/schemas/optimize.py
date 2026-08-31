"""Pydantic request/response schemas for the optimize endpoint.

This first API integration exposes named in-code scenarios only. We accept a
``scenario_id``, a solver id (currently ``"ortools"``), and an optional seed.
No arbitrary stops, vehicles, capacity, vehicle profile, city, or graph-key
inputs are accepted yet — those belong to a later custom-scenario milestone.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

#: Solver ids supported at this milestone.
OptSolver = Literal["ortools"]


class OptimizeRequest(BaseModel):
    """Request body for running a solver over a named in-code scenario."""

    scenario_id: str = Field(
        ...,
        min_length=1,
        description="Identifier of a deterministic in-code scenario",
        examples=["grid_cvrp_8"],
    )
    solver: OptSolver = Field(
        ...,
        description="Solver to run (only 'ortools' is supported)",
        examples=["ortools"],
    )
    seed: Optional[int] = Field(
        default=None,
        ge=0,
        description="Optional PRNG seed; defaults to the scenario's own seed",
    )


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
    """Result returned after solving a named scenario."""

    solver: str = Field(..., description="Solver used", examples=["ortools"])
    scenario_id: str = Field(..., description="Scenario identifier run")
    total_cost: float = Field(..., ge=0.0, description="Total solution cost")
    runtime_ms: float = Field(..., ge=0.0, description="Solver runtime in ms")
    vehicles_used: int = Field(..., ge=0, description="Number of vehicles used")
    routes: List[OptimizeRoute] = Field(
        default_factory=list, description="Route plans per vehicle"
    )
