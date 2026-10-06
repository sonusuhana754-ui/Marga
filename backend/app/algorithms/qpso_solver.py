"""VA-QPSO-AR: traffic-volatility-adaptive QPSO for static CVRP/VRPTW.

Solves the same single static fleet contract as :mod:`app.algorithms.ortools_solver`
— both are :class:`~app.algorithms.base.Solver` implementations over the same
:class:`~app.algorithms.models.Scenario` — so they can be benchmarked against each
other on one scale.

Three variants share one implementation, which is what makes the §20 ablation
possible without three code paths drifting apart:

    solver_id="qpso"      fixed-schedule β   — the established anchor
    solver_id="va_qpso"   volatility-adaptive β — this project's contribution

``local_search=False`` disables the 2-opt polish on top of either, so an
improvement can be attributed to the search rather than to the polish.

Pipeline per the design doc:

    random keys → decode (sort → split by capacity) → repair/penalise →
    evaluate → pbest/gbest → adaptive-β update → 2-opt → evaluate_solution

Reported costs come from :func:`app.algorithms.evaluate.evaluate_solution`, the
same graph-backed evaluator the OR-Tools baseline uses, so a benchmark gap is a
like-for-like comparison rather than two different cost definitions.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Sequence

from app.algorithms.base import Solver
from app.algorithms.evaluate import edge_cost_matrice, evaluate_solution
from app.algorithms.models import DEPOT_INDEX, RoutePlan, Scenario, Solution
from app.algorithms.qpso import QPSOConfig, QPSOSwarm
from app.algorithms.random_key import (
    DEFAULT_SPEED_MPS,
    Route,
    capacity_violation,
    combined_cost_matrix,
    decode,
    fleet_is_feasible,
    polish,
    routes_cost,
    time_window_penalty,
)
from app.algorithms.volatility import RollingVolatility, unique_edges_from_routes


class QPSOSolver(Solver):
    """Quantum-inspired swarm solver for capacitated fleet routing.

    Parameters
    ----------
    scenario:
        Static fleet instance.
    swarm_size, max_iterations:
        Search budget. Larger is better and slower; there is no proven setting.
    beta_mode:
        ``"adaptive"`` derives β per particle from measured traffic volatility of
        the region its route covers. ``"fixed"`` pins β to ``beta_max`` and
        reproduces plain QPSO.
    beta_min, beta_max:
        Bounded β range. ``clip`` keeps β inside it by construction.
    local_search:
        Apply 2-opt and inter-route relocation to the winner. Turn off to isolate
        the swarm's own search quality.
    smooth_fitness:
        Locally improve each candidate *during* evaluation, so the swarm searches
        a smoothed landscape instead of the raw decode cost. Defaults to **off**
        because it was measured not to pay off here: across 12 seeds on a 24-stop
        instance the smoothed variant averaged 8500 against the raw variant's
        8267, losing on 7 of 12. It costs ~2.4x per evaluation, and at a fixed
        iteration budget that spend buys diversity loss rather than better optima.
        Kept as a switch because smoothing is the right lever if the budget is
        raised or restarts are added, which is exactly the kind of thing the
        ablation should revisit rather than a decision to hard-code.
    volatility:
        Rolling observation window. When omitted, or when it holds fewer than two
        observations per edge, every σ² is 0 and β sits at ``beta_min``. That is
        the honest behaviour: without a traffic feed there is no volatility
        signal, and adaptive β degrades to its exploitation bound rather than
        silently reverting to the anchor schedule.
    penalty_weight:
        Multiplier on constraint violation in the swarm's internal fitness.
    """

    solver_id = "va_qpso"

    def __init__(
        self,
        scenario: Scenario,
        swarm_size: int = 24,
        max_iterations: int = 60,
        beta_mode: str = "adaptive",
        beta_min: float = 0.4,
        beta_max: float = 1.0,
        local_search: bool = True,
        smooth_fitness: bool = False,
        volatility: Optional[RollingVolatility] = None,
        penalty_weight: float = 1e6,
        seed: Optional[int] = None,
        stall_limit: int = 20,
    ) -> None:
        super().__init__(scenario)
        self.swarm_size = swarm_size
        self.max_iterations = max_iterations
        self.beta_mode = beta_mode
        self.beta_min = beta_min
        self.beta_max = beta_max
        self.local_search = local_search
        self.smooth_fitness = smooth_fitness
        self.volatility = volatility or RollingVolatility()
        self.penalty_weight = penalty_weight
        self.seed = scenario.seed if seed is None else seed
        self.stall_limit = stall_limit

    # -- problem setup --------------------------------------------------------

    def _demands(self) -> List[int]:
        """Demand indexed by stop position.

        Position-indexed deliberately: `random_key` and `evaluate_solution` both
        index `Scenario.stops` by position, while the OR-Tools demand callback
        indexes by `Stop.id`. Numbering depot 0 and stops 1..n keeps the two
        consistent, which is the same invariant `optimize_service` relies on.
        """
        demands = [0] * self.scenario.num_stops
        for stop in self.scenario.stops:
            if 0 <= stop.id < len(demands):
                demands[stop.id] = stop.demand
        return demands

    def _capacities(self) -> List[int]:
        return [v.capacity for v in self.scenario.vehicles] or [0]

    # -- fitness --------------------------------------------------------------

    def _build_fitness(self, cost: List[List[float]], time_matrix: List[List[float]]):
        """Return ``(fitness, on_evaluate)`` sharing a decode cache.

        `on_evaluate` records each particle's decoded routes so the β callback can
        read the region without decoding a second time.
        """
        demands = self._demands()
        capacities = self._capacities()
        time_windows = self.scenario.time_windows
        penalty_weight = self.penalty_weight

        decoded: Dict[int, List[Route]] = {}
        pending: List[List[Route]] = []

        def fitness(keys: Sequence[float]) -> float:
            routes = decode(keys, demands, capacities, cost)
            if self.smooth_fitness:
                routes = polish(routes, cost, demands, capacities)
            value = routes_cost(routes, cost)
            violation = capacity_violation(routes, demands, capacities)
            violation += time_window_penalty(routes, time_matrix, time_windows)
            pending.append(routes)
            return value + penalty_weight * violation

        def on_evaluate(particle: int, keys: List[float], _value: float) -> None:
            if pending:
                decoded[particle] = pending.pop()

        return fitness, on_evaluate, decoded

    # -- adaptive β -----------------------------------------------------------

    def _beta_callback(self, decoded: Dict[int, List[Route]]):
        """β for a particle from the volatility of the region its route covers.

        Edges are the consecutive stop pairs of that particle's current route,
        named ``"u-v"`` so they line up with
        :func:`app.algorithms.volatility.observe`.
        """
        if self.beta_mode == "fixed":
            return lambda particle, keys: self.beta_max

        def beta_for(particle: int, keys: Sequence[float]) -> float:
            routes = decoded.get(particle)
            if not routes:
                return self.beta_min
            edges = sorted(unique_edges_from_routes(routes))
            if not edges or not self.volatility.has_signal:
                return self.beta_min
            return self.volatility.beta_for(edges, self.beta_min, self.beta_max)

        return beta_for

    # -- solve ----------------------------------------------------------------

    def solve(self) -> Solution:
        scenario = self.scenario
        num_customers = scenario.num_stops - 1
        if num_customers <= 0:
            return Solution(feasible=True)

        demands = self._demands()
        capacities = self._capacities()

        # An instance whose total demand exceeds total fleet capacity cannot be
        # served by any solver. Say so instead of returning the least-bad
        # penalty-scored route set, which would read as a real answer.
        if not fleet_is_feasible(demands, capacities):
            solution = Solution(feasible=False, total_cost=float("inf"))
            solution._reason = "total demand exceeds total fleet capacity"  # type: ignore[attr-defined]
            return solution

        start = time.perf_counter()

        time_matrix, dist_matrix = edge_cost_matrice(scenario)
        cost = combined_cost_matrix(time_matrix, dist_matrix, DEFAULT_SPEED_MPS)

        fitness, on_evaluate, decoded = self._build_fitness(cost, time_matrix)

        config = QPSOConfig(
            swarm_size=self.swarm_size,
            max_iterations=self.max_iterations,
            beta_min=self.beta_min,
            beta_max=self.beta_max,
            beta_mode=self.beta_mode,
            seed=self.seed,
            stall_limit=self.stall_limit,
        )

        swarm = QPSOSwarm(
            dimension=num_customers,
            fitness=fitness,
            config=config,
            beta_for=self._beta_callback(decoded),
            on_evaluate=on_evaluate,
        )
        result = swarm.run()

        routes = decode(result.best_key, demands, capacities, cost)
        if self.local_search:
            routes = polish(routes, cost, demands, capacities)
        # Drop routes the split left empty so vehicles_used matches reality.
        routes = [r for r in routes if len(r) > 2]

        solution = Solution(feasible=True)
        for i, route in enumerate(routes):
            solution.routes.append(
                RoutePlan(
                    vehicle_id=i,
                    stop_sequence=list(route),
                    load=0,
                )
            )

        solution = evaluate_solution(scenario, solution)

        # A candidate can still violate capacity or a time window even when the
        # instance itself is servable — the split is greedy, not exact. Report
        # that rather than shipping a route set the fleet cannot legally run.
        sequences = [r.stop_sequence for r in solution.routes]
        if len(sequences) > len(capacities):
            solution.feasible = False
            solution._reason = "solution needs more vehicles than the fleet has"  # type: ignore[attr-defined]
        elif capacity_violation(sequences, demands, capacities) > 0.0:
            solution.feasible = False
            solution._reason = "route exceeds vehicle capacity"  # type: ignore[attr-defined]

        if scenario.time_windows:
            tw = time_window_penalty(sequences, time_matrix, scenario.time_windows)
            if tw > 1e-6:
                solution.feasible = False
                solution._reason = "time window violated"  # type: ignore[attr-defined]

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        solution._runtime_ms = elapsed_ms  # type: ignore[attr-defined]
        solution._convergence = result.convergence.as_pairs()  # type: ignore[attr-defined]
        solution._iterations = result.iterations_run  # type: ignore[attr-defined]
        solution._evaluations = result.evaluations  # type: ignore[attr-defined]
        solution._beta_mean = (  # type: ignore[attr-defined]
            sum(result.beta_history) / len(result.beta_history)
            if result.beta_history
            else 0.0
        )
        solution._beta_history = list(result.beta_history)  # type: ignore[attr-defined]
        solution._beta_range = [  # type: ignore[attr-defined]
            float(self.beta_min),
            float(self.beta_max),
        ]
        solution._beta_mode = self.beta_mode  # type: ignore[attr-defined]
        solution._volatility_signal = self.volatility.has_signal  # type: ignore[attr-defined]
        return solution


class FixedBetaQPSOSolver(QPSOSolver):
    """Fixed-schedule QPSO — the §20 ablation baseline for adaptive β."""

    solver_id = "qpso"

    def __init__(self, scenario: Scenario, **kwargs) -> None:
        kwargs.setdefault("beta_mode", "fixed")
        super().__init__(scenario, **kwargs)
        self.beta_mode = "fixed"


#: Registry consumed by the benchmark endpoint and the optimize service.
QPSO_VARIANTS: Dict[str, type[QPSOSolver]] = {
    "qpso": FixedBetaQPSOSolver,
    "va_qpso": QPSOSolver,
}


def solve_qpso(scenario: Scenario, **kwargs) -> Solution:
    return FixedBetaQPSOSolver(scenario, **kwargs).solve()


def solve_va_qpso(scenario: Scenario, **kwargs) -> Solution:
    return QPSOSolver(scenario, **kwargs).solve()
