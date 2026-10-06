"""Pydantic request/response schemas for the route endpoint."""

from __future__ import annotations

from typing import List, Tuple

from pydantic import BaseModel, Field


class VehicleProfile(BaseModel):
    """Vehicle physical dimensions used for future constraint checking."""

    vehicle_class: str = Field(
        ...,
        description="Vehicle class identifier",
        examples=["car"],
    )
    weight_t: float = Field(
        default=0.0, ge=0.0, description="Vehicle weight in tonnes"
    )
    length_m: float = Field(
        default=0.0, ge=0.0, description="Vehicle length in metres"
    )
    height_m: float = Field(
        default=0.0, ge=0.0, description="Vehicle height in metres"
    )
    width_m: float = Field(
        default=0.0, ge=0.0, description="Vehicle width in metres"
    )


class RouteRequest(BaseModel):
    """Request body for computing a single-vehicle shortest path."""

    city: str = Field(
        ...,
        min_length=1,
        description="Place name used to look up the cached road graph",
        examples=["Koramangala, Bengaluru, India"],
    )
    origin: Tuple[float, float] = Field(
        ...,
        description="[longitude, latitude] of the start point",
        examples=[[77.6245, 12.9352]],
    )
    destination: Tuple[float, float] = Field(
        ...,
        description="[longitude, latitude] of the end point",
        examples=[[77.6110, 12.9320]],
    )
    vehicle_profile: VehicleProfile = Field(
        default_factory=lambda: VehicleProfile(vehicle_class="car"),
        description="Vehicle profile for future constraint checking",
    )
    traffic_aware: bool = Field(
        default=False,
        description="Placeholder; traffic-aware routing is not yet implemented",
    )


class SingleRoute(BaseModel):
    """A single computed route with geometry and cost metrics."""

    path: List[Tuple[float, float]] = Field(
        ...,
        description="Ordered [longitude, latitude] coordinates along the route",
    )
    distance_m: float = Field(
        ..., ge=0.0, description="Total route distance in metres"
    )
    eta_s: float = Field(
        ..., ge=0.0, description="Estimated travel time in seconds"
    )
    feasible_for_profile: bool = Field(
        default=True,
        description="Whether the route satisfies vehicle-profile constraints",
    )


class BlockedEdge(BaseModel):
    """A road segment blocked for the given vehicle profile (reserved for future use)."""

    edge_id: str = Field(..., description="Unique edge identifier")
    geometry: List[Tuple[float, float]] = Field(
        default_factory=list, description="Edge geometry as [lng, lat] pairs"
    )
    reason: str = Field(..., description="Why this edge is blocked")
    limit: float = Field(
        ..., description="The limit value that blocks this vehicle"
    )


class RouteResponse(BaseModel):
    """Response containing the computed shortest-path route."""

    unconstrained: SingleRoute = Field(
        ...,
        description="Shortest route by travel_time for an unrestricted vehicle",
    )
    best: SingleRoute = Field(
        ...,
        description="Lowest-cost legal route (same as unconstrained in baseline)",
    )
    blocked_edges: List[BlockedEdge] = Field(
        default_factory=list,
        description="Edges blocked for this vehicle profile (empty in baseline)",
    )
    method: str = Field(
        default="dijkstra",
        description="Routing algorithm used",
    )
