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


def build_grid_graph(num_nodes: int = 9) -> nx.MultiDiGraph:
    """Return a small deterministic connected directed grid road graph.

    Nodes are laid out on a 3-column grid spaced 100 m apart. Every node is
    connected to its right and downward neighbours, and each connection is
    bidirectional, so the graph is strongly connected with no isolated nodes.
    """
    G = nx.MultiDiGraph()
    side = 3
    for idx in range(num_nodes):
        x = (idx % side) * 0.001
        y = (idx // side) * 0.001
        G.add_node(idx, x=x, y=y)

    # Connect each node to the right and down; skip indices past num_nodes.
    edges = []
    for idx in range(num_nodes):
        col = idx % side
        row = idx // side
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


_DEFS: Dict[str, dict] = {
    "grid_cvrp_8": {
        "factory": _make_cvrp,
        "seed": 7,
        "kwargs": {"vehicles": 3, "capacity": 10, "num_stops": 7},
        "description": "8-node grid, 3 vehicles, capacity 10, 7 stops",
    },
    "grid_cvrp_6": {
        "factory": _make_cvrp,
        "seed": 5,
        "kwargs": {"vehicles": 2, "capacity": 10, "num_stops": 5},
        "description": "6-node grid, 2 vehicles, capacity 10, 5 stops",
    },
    "grid_vrptw_8": {
        "factory": _make_vrptw,
        "seed": 11,
        "kwargs": {},
        "description": "8-node grid CVRP with time windows (VRPTW)",
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
