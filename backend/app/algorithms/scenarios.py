"""Named deterministic in-code scenario registry.

Exposes a small set of fixed, reproducible CVRP/VRPTW scenarios so the API can
reference them by ``scenario_id`` without accepting arbitrary stop/vehicle
configurations or requiring a cached road graph. All graphs are built in-code,
so no map data is downloaded.
"""

from __future__ import annotations

from typing import Dict, Optional

import networkx as nx

from app.algorithms.models import Scenario
from app.algorithms.scenario import make_scenario


def build_grid_graph(num_nodes: int = 9, side: int = 3) -> nx.MultiDiGraph:
    """Return a small deterministic connected directed grid road graph.

    Nodes are laid out on a `side`-column grid spaced 100 m apart. Every node is
    connected to its right and downward neighbours, and each connection is
    bidirectional, so the graph is strongly connected with no isolated nodes.

    `side` defaults to 3, which keeps the original 9-node layout. Larger values
    are used to build instances big enough that solver quality actually differs;
    a 3x3 grid with 7 stops is solvable exactly by almost any method, so it
    cannot tell a swarm apart from a local search.
    """
    if num_nodes < 1:
        raise ValueError("num_nodes must be >= 1")
    if side < 1:
        raise ValueError("side must be >= 1")
    G = nx.MultiDiGraph()
    for idx in range(num_nodes):
        x = (idx % side) * 0.001
        y = (idx // side) * 0.001
        G.add_node(idx, x=x, y=y)

    # Connect each node to the right and down; skip indices past num_nodes.
    edges = []
    for idx in range(num_nodes):
        col = idx % side
        if col + 1 < side:
            right = idx + 1
            if right < num_nodes:
                edges.append((idx, right, 100.0))
        down = idx + side
        if down < num_nodes:
            edges.append((idx, down, 100.0))

    for u, v, length in edges:
        tt = length / (50.0 * 1000.0 / 3600.0)
        G.add_edge(u, v, length=length, travel_time=tt)
        G.add_edge(v, u, length=length, travel_time=tt)
    return G


def _square_grid(num_stops: int, side: int | None = None) -> nx.MultiDiGraph:
    """Grid with enough nodes for `num_stops` customers plus a depot."""
    import math

    side = side or max(3, math.ceil(math.sqrt(num_stops + 1)))
    return build_grid_graph(num_nodes=side * side, side=side)


#: The underlying grid graph shared by all named scenarios.
_GRID_GRAPH = build_grid_graph(num_nodes=9)


def _make_cvrp(
    seed: int,
    capacity: int = 10,
    vehicles: int = 3,
    num_stops: int = 7,
) -> Scenario:
    return make_scenario(
        _GRID_GRAPH,
        seed=seed,
        capacity=capacity,
        vehicles=vehicles,
        num_stops=num_stops,
    )


def _make_vrptw(seed: int) -> Scenario:
    """Return the grid scenario with generous time windows on every stop."""
    scenario = _make_cvrp(seed)
    scenario.time_windows = {
        i: (0.0, 500.0) for i in range(0, scenario.num_stops)
    }
    return scenario


def _make_square_cvrp(seed: int, num_stops: int, vehicles: int, capacity: int, side: int | None = None):
    return make_scenario(
        _square_grid(num_stops, side=side),
        seed=seed,
        capacity=capacity,
        vehicles=vehicles,
        num_stops=num_stops,
    )


def _make_square_vrptw(seed: int, num_stops: int, vehicles: int, capacity: int):
    scenario = _make_square_cvrp(seed, num_stops, vehicles, capacity)
    horizon = 100_000.0
    scenario.time_windows = {i: (0.0, horizon) for i in range(scenario.num_stops)}
    return scenario


_DEFS: Dict[str, dict] = {
    # Small instances. Kept because the original test suite pins them, and
    # because they exercise the VRPTW path. Note they are *too easy to
    # discriminate*: at 7 stops every solver finds the optimum, so all three rows
    # tie. Use the larger instances below to compare solver quality.
    "grid_cvrp_8": {
        "factory": _make_cvrp,
        "seed": 7,
        "kwargs": {"vehicles": 3, "capacity": 10, "num_stops": 7},
        "description": "8-node grid, 3 vehicles, capacity 10, 7 stops (too small to rank solvers)",
    },
    "grid_cvrp_6": {
        "factory": _make_cvrp,
        "seed": 5,
        "kwargs": {"vehicles": 2, "capacity": 10, "num_stops": 5},
        "description": "6-node grid, 2 vehicles, capacity 10, 5 stops (too small to rank solvers)",
    },
    "grid_vrptw_8": {
        "factory": _make_vrptw,
        "seed": 11,
        "kwargs": {},
        "description": "8-node grid CVRP with time windows (VRPTW)",
    },
    # Larger instances, sized so solver quality actually diverges.
    "grid_cvrp_25": {
        "factory": _make_square_cvrp,
        "seed": 3,
        "kwargs": {"num_stops": 24, "vehicles": 4, "capacity": 9},
        "description": "25-node grid, 4 vehicles, capacity 9, 24 stops",
    },
    "grid_cvrp_49": {
        "factory": _make_square_cvrp,
        "seed": 4,
        "kwargs": {"num_stops": 48, "vehicles": 6, "capacity": 10},
        "description": "49-node grid, 6 vehicles, capacity 10, 48 stops",
    },
    "grid_vrptw_25": {
        "factory": _make_square_vrptw,
        "seed": 6,
        "kwargs": {"num_stops": 24, "vehicles": 4, "capacity": 9},
        "description": "25-node grid with time windows, 4 vehicles, 24 stops",
    },
}


class ScenarioRegistry:
    """Resolve named :class:`Scenario` instances by id."""

    def __init__(self, defs: Optional[Dict[str, dict]] = None) -> None:
        self._defs = defs or _DEFS

    def available_ids(self):
        return list(self._defs.keys())

    def has(self, scenario_id: str) -> bool:
        return scenario_id in self._defs

    def get(self, scenario_id: str, seed: Optional[int] = None) -> Scenario:
        """Return the named scenario, optionally overriding its default seed."""
        if scenario_id not in self._defs:
            raise KeyError(f"Unknown scenario_id '{scenario_id}'")
        definition = self._defs[scenario_id]
        factory = definition["factory"]
        effective_seed = definition["seed"] if seed is None else seed
        return factory(seed=effective_seed, **definition["kwargs"])


#: Module-level singleton registry.
scenario_registry = ScenarioRegistry()


def describe(scenario_id: str) -> dict:
    if scenario_id not in _DEFS:
        raise KeyError(f"Unknown scenario_id '{scenario_id}'")
    definition = _DEFS[scenario_id]
    return {
        "id": scenario_id,
        "description": definition.get("description", ""),
        "seed": definition.get("seed"),
    }
