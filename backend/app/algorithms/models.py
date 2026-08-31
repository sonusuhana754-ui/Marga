"""Typed data models for static fleet (CVRP/VRPTW) optimization scenarios.

These are solver-layer dataclasses kept intentionally decoupled from the
FastAPI request/response schemas. A single static fleet contract is exposed
here; single-vehicle routing lives separately in ``app.services.route_service``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import networkx as nx

#: Stop sequence always starts and ends at the depot.
DEPOT_INDEX = 0


@dataclass(frozen=True)
class Stop:
    """A single delivery stop (or the depot at index 0)."""

    id: int
    lng: float
    lat: float
    #: Node coordinates on the road graph (longitude, latitude).
    x: float = 0.0
    y: float = 0.0
    demand: int = 0


@dataclass(frozen=True)
class Vehicle:
    """A single vehicle with a uniform capacity (generic units)."""

    id: int
    capacity: int


@dataclass
class Scenario:
    """A static fleet instance: graph + stops + vehicles + optional time windows.

    ``time_windows`` maps a stop ``id`` to an ``(earliest, latest)`` pair in the
    same time units as the leg cost matrix. ``None`` means CVRP (capacity only).
    """

    graph: nx.MultiDiGraph
    stops: List[Stop]
    vehicles: List[Vehicle]
    depot: Stop
    seed: int = 0
    time_windows: Optional[Dict[int, Tuple[float, float]]] = None

    @property
    def time_windowed(self) -> bool:
        return self.time_windows is not None

    @property
    def num_stops(self) -> int:
        return len(self.stops)

    @property
    def num_vehicles(self) -> int:
        return len(self.vehicles)


@dataclass
class RoutePlan:
    """Orders served by a single vehicle (depot first and last).

    ``distance_m``/``time_s``/``load`` are filled in during graph-backed
    evaluation, hence this class is intentionally mutable.
    """

    vehicle_id: int
    #: Ordered stop indices into ``Scenario.stops``; starts/ends at 0 (depot).
    stop_sequence: List[int]
    load: int = 0
    distance_m: float = 0.0
    time_s: float = 0.0


@dataclass
class Solution:
    """A complete routing solution across all vehicles."""

    routes: List[RoutePlan] = field(default_factory=list)
    total_cost: float = 0.0
    total_distance_m: float = 0.0
    total_time_s: float = 0.0
    feasible: bool = True

    @property
    def vehicles_used(self) -> int:
        return len([r for r in self.routes if len(r.stop_sequence) > 2])

    @property
    def is_empty(self) -> bool:
        return not self.routes
