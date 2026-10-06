"""Random-key encoding, capacity splitting, and 2-opt for discrete VRP.

Implements §7 and §9 of the VA-QPSO-AR design. QPSO searches a continuous space;
a CVRP solution is a permutation plus an assignment to vehicles. The bridge is a
random-key encoding: every customer carries a continuous key, sorting the keys
gives a grand-tour ordering, and a split heuristic cuts that ordering into
capacity-feasible vehicle routes.

    Particle X = [x_1 … x_n],  x_i ∈ R
      → pair each customer with its key
      → sort by key                     = candidate visit sequence
      → insert the depot and split by vehicle constraints
      → repair infeasible segments
      → evaluate

Splitting is deterministic given an ordering, so the only stochastic part of the
pipeline is the continuous search upstream. Two split strategies are tried and
the cheaper kept, which is a cheap quality win over first-fit alone.

The fitness used here is the same distance-plus-time objective the OR-Tools
baseline is scored with (``evaluate_solution``), so benchmark gaps between the
two solvers are computed on one scale.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from app.algorithms.models import DEPOT_INDEX

Route = List[int]

#: Cost of one unit of travel time when expressed as distance, matching
#: ``_DEFAULT_SPEED_MS`` in ``app.algorithms.evaluate``.
DEFAULT_SPEED_MPS = (50.0 * 1000.0) / 3600.0


def combined_cost_matrix(
    time_matrix: Sequence[Sequence[float]],
    dist_matrix: Sequence[Sequence[float]],
    speed_mps: float = DEFAULT_SPEED_MPS,
) -> List[List[float]]:
    """Precompute ``dist + time * speed`` once so fitness is a single lookup.

    This is the same arithmetic ``evaluate_solution`` applies to the finished
    solution, precomputed so the swarm can score a candidate in O(1) per leg.
    """
    n = len(time_matrix)
    return [
        [
            dist_matrix[i][j] + time_matrix[i][j] * speed_mps
            for j in range(n)
        ]
        for i in range(n)
    ]


def random_key_order(keys: Sequence[float], num_customers: int) -> Route:
    """Sort customers 1..num_customers by key ascending.

    Ties break on position so the decode is total and reproducible.
    """
    pairs = [(keys[i - 1], i) for i in range(1, num_customers + 1)]
    pairs.sort(key=lambda kv: (kv[0], kv[1]))
    return [pos for _key, pos in pairs]


def leg_cost(route: Sequence[int], cost: Sequence[Sequence[float]]) -> float:
    """Sum the leg costs of a depot-first/depot-last route."""
    return sum(cost[a][b] for a, b in zip(route[:-1], route[1:]))


def routes_cost(routes: Sequence[Sequence[int]], cost: Sequence[Sequence[float]]) -> float:
    return sum(leg_cost(r, cost) for r in routes)


def _first_fit_split(
    order: Sequence[int],
    demands: Sequence[int],
    capacities: Sequence[int],
) -> List[Route]:
    """Sequential first-fit: walk the order, open a new route when full.

    Route count is bounded by the fleet size. A customer that fits nowhere is
    still served — dropping it would make the decode lie about coverage — so it
    overflows the last vehicle's capacity and the caller detects it through
    :func:`capacity_violation`.
    """
    max_routes = max(1, len(capacities))
    routes: List[Route] = []
    current: Route = [DEPOT_INDEX]
    load = 0
    for customer in order:
        d = demands[customer]
        if current == [DEPOT_INDEX]:
            current.append(customer)
            load = d
            continue
        vehicle = min(len(routes), len(capacities) - 1)
        if load + d <= capacities[vehicle]:
            current.append(customer)
            load += d
        elif len(routes) + 1 < max_routes:
            routes.append(current + [DEPOT_INDEX])
            current = [DEPOT_INDEX, customer]
            load = d
        else:
            # Fleet exhausted; carry the overflow so the violation is visible.
            current.append(customer)
            load += d
    if len(current) > 1:
        routes.append(current + [DEPOT_INDEX])
    return routes


def _best_fit_split(
    order: Sequence[int],
    demands: Sequence[int],
    capacities: Sequence[int],
    cost: Sequence[Sequence[float]],
) -> List[Route]:
    """Cheapest feasible insertion: place each customer in the route that costs least.

    Falls back to the cheapest overflow vehicle once the fleet is full. This
    keeps routes geographically compact in a way first-fit does not.
    """
    max_routes = max(1, len(capacities))
    routes: List[Route] = []
    loads: List[int] = []
    for customer in order:
        d = demands[customer]
        best_idx: Optional[int] = None
        best_delta = float("inf")
        for i, route in enumerate(routes):
            cap = capacities[min(i, len(capacities) - 1)]
            if loads[i] + d > cap:
                continue
            delta = _insertion_delta(route, customer, cost)
            if delta < best_delta:
                best_delta = delta
                best_idx = i
        if best_idx is not None:
            pos = _best_insertion_pos(routes[best_idx], customer, cost)
            routes[best_idx].insert(pos, customer)
            loads[best_idx] += d
        elif len(routes) < max_routes:
            routes.append([DEPOT_INDEX, customer, DEPOT_INDEX])
            loads.append(d)
        else:
            # No vehicle has room. Force the cheapest insertion anyway so the
            # decode still covers every customer, and let the penalty surface it.
            deltas = [_insertion_delta(r, customer, cost) for r in routes]
            forced = min(range(len(routes)), key=lambda i: deltas[i])
            routes[forced].insert(_best_insertion_pos(routes[forced], customer, cost), customer)
            loads[forced] += d
    return routes


def _insertion_delta(route: Sequence[int], customer: int, cost: Sequence[Sequence[float]]) -> float:
    """Cost of inserting `customer` at its best position in `route`."""
    best = float("inf")
    for pos in range(1, len(route)):
        a, b = route[pos - 1], route[pos]
        delta = cost[a][customer] + cost[customer][b] - cost[a][b]
        if delta < best:
            best = delta
    return best


def _best_insertion_pos(route: Sequence[int], customer: int, cost: Sequence[Sequence[float]]) -> int:
    """Index at which inserting `customer` adds least cost."""
    best_pos = 1
    best = float("inf")
    for pos in range(1, len(route)):
        a, b = route[pos - 1], route[pos]
        delta = cost[a][customer] + cost[customer][b] - cost[a][b]
        if delta < best:
            best = delta
            best_pos = pos
    return best_pos


def decode(
    keys: Sequence[float],
    demands: Sequence[int],
    capacities: Sequence[int],
    cost: Sequence[Sequence[float]],
) -> List[Route]:
    """Decode a continuous particle into the cheapest feasible route set.

    Tries first-fit and best-fit and keeps the cheaper, so a candidate is never
    worse than plain sequential splitting.
    """
    num_customers = len(demands) - 1
    if num_customers <= 0:
        return []
    order = random_key_order(keys, num_customers)
    first = _first_fit_split(order, demands, capacities)
    best = _best_fit_split(order, demands, capacities, cost)
    if first and routes_cost(first, cost) <= routes_cost(best, cost):
        return first
    return best


def two_opt(route: Sequence[int], cost: Sequence[Sequence[float]]) -> Route:
    """Bounded intra-route 2-opt, §9 step 24.

    Reverses the segment between two indices when it strictly reduces leg cost.
    Depot-first/depot-last is preserved because only interior indices are touched.
    """
    r: List[int] = list(route)
    n = len(r)
    if n < 4:
        return r
    improved = True
    while improved:
        improved = False
        for i in range(1, n - 2):
            for j in range(i + 1, n - 1):
                a, b = r[i - 1], r[i]
                c, d = r[j], r[j + 1]
                delta = cost[a][c] + cost[b][d] - cost[a][b] - cost[c][d]
                if delta < -1e-9:
                    r[i : j + 1] = reversed(r[i : j + 1])
                    improved = True
    return r


def _removal_gain(route: Sequence[int], i: int, cost: Sequence[Sequence[float]]) -> float:
    """Leg cost saved by lifting `route[i]` out, reconnecting its neighbours."""
    a, node, b = route[i - 1], route[i], route[i + 1]
    return cost[a][b] - cost[a][node] - cost[node][b]


def _insertion_cost(
    route: Sequence[int], j: int, node: int, cost: Sequence[Sequence[float]]
) -> float:
    """Leg cost added by putting `node` between `route[j-1]` and `route[j]`."""
    a, b = route[j - 1], route[j]
    return cost[a][node] + cost[node][b] - cost[a][b]


def relocate(
    routes: Sequence[Sequence[int]],
    demands: Sequence[int],
    capacities: Sequence[int],
    cost: Sequence[Sequence[float]],
    max_passes: int = 8,
) -> List[Route]:
    """Inter-route customer relocation, honouring vehicle capacity.

    2-opt only reorders *within* a route, so a route set produced by greedy
    splitting stays trapped in whatever assignment the split chose — which is
    where the measured quality gap against OR-Tools came from. This moves one
    customer at a time between any two positions in any two routes, provided the
    receiving vehicle has spare capacity.

    Best-improvement over all (route, position, route, position) moves per pass,
    bounded by `max_passes` so the polish stays cheap enough to run inside the
    solve budget. Depot-first/depot-last is preserved because only interior
    indices are ever candidates.
    """
    work: List[Route] = [list(r) for r in routes]
    fleet_size = max(1, len(capacities))
    loads = [sum(demands[p] for p in r if p != DEPOT_INDEX) for r in work]

    for _ in range(max_passes):
        best_delta = -1e-9
        best_move: Optional[Tuple[int, int, int, int]] = None

        for ri, route in enumerate(work):
            if len(route) <= 2:
                continue
            for i in range(1, len(route) - 1):
                node = route[i]
                demand = demands[node]
                gain = _removal_gain(route, i, cost)
                for ti, target in enumerate(work):
                    if ti >= fleet_size:
                        continue
                    if ti != ri and loads[ti] + demand > capacities[ti]:
                        continue
                    for j in range(1, len(target)):
                        # Skip no-ops: the slot the node already occupies.
                        if ti == ri and j in (i, i + 1):
                            continue
                        delta = _insertion_cost(target, j, node, cost) - gain
                        if delta < best_delta:
                            best_delta = delta
                            best_move = (ri, i, ti, j)

        if best_move is None:
            break

        ri, i, ti, j = best_move
        node = work[ri][i]
        work[ri].pop(i)
        loads[ri] -= demands[node]
        # Insertion index refers to the pre-removal route; shift if the target
        # is the same route and the slot sat after the removed element.
        if ti == ri and j > i:
            j -= 1
        work[ti].insert(j, node)
        loads[ti] += demands[node]

    return work


def polish(
    routes: Sequence[Sequence[int]],
    cost: Sequence[Sequence[float]],
    demands: Optional[Sequence[int]] = None,
    capacities: Optional[Sequence[int]] = None,
) -> List[Route]:
    """Apply 2-opt to every route, then relocate customers across routes.

    Cost is separable across vehicles, so 2-opt per route is safe. Relocation
    needs `demands`/`capacities`; without them it is skipped and the result is
    exactly the 2-opt-only polish.
    """
    improved = [two_opt(r, cost) for r in routes]
    if demands is not None and capacities:
        improved = relocate(improved, demands, capacities, cost)
        improved = [two_opt(r, cost) for r in improved]
    return improved


def time_window_penalty(
    routes: Sequence[Sequence[int]],
    time_matrix: Sequence[Sequence[float]],
    time_windows: Optional[Dict[int, Tuple[float, float]]],
    max_penalty: float = 1e9,
) -> float:
    """Total earliness/lateness penalty over all routes, 0.0 when untimed.

    Depot legs are checked too: a vehicle must still return within its window.
    """
    if not time_windows:
        return 0.0
    total = 0.0
    for route in routes:
        clock = 0.0
        for i, pos in enumerate(route):
            if i > 0:
                clock += time_matrix[route[i - 1]][pos]
            window = time_windows.get(pos)
            if window is None:
                continue
            earliest, latest = window
            if clock < earliest:
                total += earliest - clock
            elif clock > latest:
                total += clock - latest
            if total > max_penalty:
                return max_penalty
    return total


def capacity_violation(
    routes: Sequence[Sequence[int]],
    demands: Sequence[int],
    capacities: Sequence[int],
) -> float:
    """Total infeasibility across the fleet, 0.0 when the split is feasible.

    Two distinct failures are summed:

    * **Per-vehicle overload** — a route carries more than its capacity.
    * **Fleet overflow** — more routes were opened than there are vehicles, or
      total demand exceeds total fleet capacity.

    Fleet overflow is the one that silently produces a plausible-looking answer:
    the split can open as many routes as it likes and the route list still looks
    like a solution. Counting it here is what stops the swarm from preferring
    candidates that quietly borrow a vehicle that does not exist.
    """
    total = 0.0
    fleet_size = max(1, len(capacities))

    for i, route in enumerate(routes):
        if i >= fleet_size:
            # Opened beyond the fleet: charge the whole load as overflow.
            total += sum(demands[p] for p in route if p != DEPOT_INDEX)
            continue
        load = sum(demands[p] for p in route if p != DEPOT_INDEX)
        if load > capacities[i]:
            total += load - capacities[i]

    total_demand = sum(demands)
    total_capacity = sum(capacities)
    if total_demand > total_capacity:
        total += total_demand - total_capacity

    return total


def fleet_is_feasible(
    demands: Sequence[int],
    capacities: Sequence[int],
) -> bool:
    """True when the instance can be served at all, ignoring routing.

    A cheap precondition check: if total demand exceeds total fleet capacity no
    solver can produce a valid answer, and reporting that up front is more useful
    than returning a large penalty score for every candidate.
    """
    return sum(demands) <= sum(capacities)
