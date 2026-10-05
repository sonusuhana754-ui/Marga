"""Deterministic benchmark runner comparing solver implementations.

Runs each requested solver multiple times on a single fixed in-code scenario
(reproducible via a fixed seed) and reports repeated-run metrics. The best
known cost is the minimum across all solvers so results are compared fairly.
"""

from __future__ import annotations

import math
import statistics
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

import networkx as nx

from app.algorithms.base import Solver
from app.algorithms.models import DEPOT_INDEX, Scenario


@dataclass
class BenchmarkRun:
    """Metrics from a single solver repetition."""

    cost: float
    runtime_ms: float
    total_distance_m: float = 0.0
    total_time_s: float = 0.0
    vehicles_used: int = 0
    wall_ms: float = 0.0


@dataclass
class BenchmarkResult:
    """Aggregated metrics for one solver over its repeated runs."""

    solver_id: str
    cost: float
    gap_pct: float
    runtime_ms: float
    feasible: bool
    runs: List[BenchmarkRun] = field(default_factory=list)
    total_distance_m: float = 0.0
    total_time_s: float = 0.0
    vehicles_used_mean: float = 0.0
    vehicles_used_min: int = 0
    vehicles_used_max: int = 0
    vehicles_used_stdev_sample: float = 0.0
    total_distance_m_mean: float = 0.0
    total_distance_m_min: float = 0.0
    total_distance_m_max: float = 0.0
    total_distance_m_stdev_sample: float = 0.0
    total_time_s_mean: float = 0.0
    total_time_s_min: float = 0.0
    total_time_s_max: float = 0.0
    total_time_s_stdev_sample: float = 0.0
    runtime_ms_mean: float = 0.0
    runtime_ms_min: float = 0.0
    runtime_ms_max: float = 0.0
    runtime_ms_stdev_sample: float = 0.0
    wall_ms_mean: float = 0.0
    wall_ms_min: float = 0.0
    wall_ms_max: float = 0.0
    wall_ms_stdev_sample: float = 0.0
    violations: List[str] = field(default_factory=list)

    @property
    def cost_mean(self) -> float:
        return self.cost

    @property
    def cost_std(self) -> float:
        if not self.runs:
            return 0.0
        vals = [r.cost for r in self.runs]
        return statistics.pstdev(vals)


@dataclass
class BenchmarkSummary:
    """Best-known cost plus per-solver results."""

    scenario_seed: int
    best_known: float
    results: List[BenchmarkResult] = field(default_factory=list)


def _validate_solution(scenario: Scenario, solution) -> Tuple[bool, List[str]]:
    violations: List[str] = []
    if not getattr(solution, "feasible", False):
        violations.append("solution.feasible is False")
        return False, violations

    stops = scenario.stops
    num_stops = scenario.num_stops

    seen = set()
    for route in solution.routes:
        seq = getattr(route, "stop_sequence", [])
        if len(seq) < 2:
            violations.append(f"route {route.vehicle_id} has invalid stop_sequence")
            continue
        if seq[0] != DEPOT_INDEX or seq[-1] != DEPOT_INDEX:
            violations.append(f"route {route.vehicle_id} must start/end at depot {DEPOT_INDEX}")
        for i, s in enumerate(seq[1:-1], start=1):
            if s == DEPOT_INDEX:
                violations.append(f"route {route.vehicle_id} contains depot in interior at pos {i}")
        for s in seq:
            if s < 0 or s >= num_stops:
                violations.append(f"stop id {s} out of range")
            seen.add(s)

    all_stops = set(range(num_stops)) if num_stops >= 0 else set()
    for sid in all_stops:
        if sid not in seen:
            violations.append(f"missing stop {sid}")
    for sid in seen:
        if sid in all_stops:
            count = sum(1 for r in solution.routes for s in getattr(r, "stop_sequence", []) if s == sid)
            if count != 1 and sid != DEPOT_INDEX:
                violations.append(f"duplicate stop {sid}")
            elif sid == DEPOT_INDEX:
                depot_count = sum(
                    1
                    for r in solution.routes
                    for s in getattr(r, "stop_sequence", [])
                    if s == sid
                )
                if depot_count < len(solution.routes) * 2:
                    pass

    for route in solution.routes:
        seq = getattr(route, "stop_sequence", [])
        load_recomputed = sum(stops[i].demand for i in seq if i != DEPOT_INDEX)
        if abs(getattr(route, "load", -1) - load_recomputed) > 1e-9:
            violations.append(f"route {route.vehicle_id} load mismatch")
        if hasattr(scenario, "vehicles") and route.vehicle_id < len(scenario.vehicles):
            cap = scenario.vehicles[route.vehicle_id].capacity
            if getattr(route, "load", 0) > cap + 1e-9:
                violations.append(f"route {route.vehicle_id} capacity exceeded")

    if getattr(solution, "total_distance_m", 0.0) < 0:
        violations.append("total_distance_m < 0")
    if getattr(solution, "total_time_s", 0.0) < 0:
        violations.append("total_time_s < 0")

    return len(violations) == 0, violations


ScenarioFactory = Callable[..., Scenario]


def _run_solver(
    solver_cls: type[Solver],
    scenario: Scenario,
    repeats: int,
    seed: int,
    solution_limit: Optional[int] = None,
) -> BenchmarkResult:
    if solution_limit is not None and solution_limit < 1:
        raise ValueError("solution_limit must be >= 1")

    runs: List[BenchmarkRun] = []
    costs: List[float] = []
    best_cost = float("inf")
    feasible_all = True

    solver_ctor_kwargs = {}
    if solution_limit is not None:
        solver_ctor_kwargs["solution_limit"] = int(solution_limit)

    for _ in range(repeats):
        if solver_ctor_kwargs:
            solver = solver_cls(scenario, **solver_ctor_kwargs)
        else:
            solver = solver_cls(scenario)
        wall_start = time.perf_counter()
        solution = solver.solve()
        elapsed_harness = (time.perf_counter() - wall_start) * 1000.0

        is_feas, viols = _validate_solution(scenario, solution)
        if not getattr(solution, "feasible", False) or not is_feas:
            feasible_all = False

        cost = solution.total_cost

        costs.append(cost)
        if cost < best_cost:
            best_cost = cost

        runtime_internal = getattr(solution, "_runtime_ms", elapsed_harness)
        runs.append(
            BenchmarkRun(
                cost=cost,
                runtime_ms=runtime_internal,
                total_distance_m=getattr(solution, "total_distance_m", 0.0),
                total_time_s=getattr(solution, "total_time_s", 0.0),
                vehicles_used=getattr(solution, "vehicles_used", 0),
                wall_ms=elapsed_harness,
            )
        )

    mean_cost = sum(costs) / len(costs) if costs else float("inf")

    result = BenchmarkResult(
        solver_id=solver_cls.solver_id,
        cost=mean_cost,
        gap_pct=0.0,
        runtime_ms=sum(r.runtime_ms for r in runs) / len(runs) if runs else 0.0,
        feasible=feasible_all,
        runs=runs,
        violations=[],
    )

    if runs:
        result.total_distance_m = runs[0].total_distance_m
        result.total_time_s = runs[0].total_time_s
        result.vehicles_used_min = min(r.vehicles_used for r in runs)
        result.vehicles_used_max = max(r.vehicles_used for r in runs)
        result.vehicles_used_mean = sum(r.vehicles_used for r in runs) / len(runs)
        result.vehicles_used_stdev_sample = (
            statistics.stdev(r.vehicles_used for r in runs) if len(runs) > 1 else 0.0
        )
        result.total_distance_m_min = min(r.total_distance_m for r in runs)
        result.total_distance_m_max = max(r.total_distance_m for r in runs)
        result.total_distance_m_mean = sum(r.total_distance_m for r in runs) / len(runs)
        result.total_distance_m_stdev_sample = (
            statistics.stdev(r.total_distance_m for r in runs) if len(runs) > 1 else 0.0
        )
        result.total_time_s_min = min(r.total_time_s for r in runs)
        result.total_time_s_max = max(r.total_time_s for r in runs)
        result.total_time_s_mean = sum(r.total_time_s for r in runs) / len(runs)
        result.total_time_s_stdev_sample = (
            statistics.stdev(r.total_time_s for r in runs) if len(runs) > 1 else 0.0
        )
        result.runtime_ms_min = min(r.runtime_ms for r in runs)
        result.runtime_ms_max = max(r.runtime_ms for r in runs)
        result.runtime_ms_mean = sum(r.runtime_ms for r in runs) / len(runs)
        result.runtime_ms_stdev_sample = (
            statistics.stdev(r.runtime_ms for r in runs) if len(runs) > 1 else 0.0
        )
        result.wall_ms_min = min(r.wall_ms for r in runs)
        result.wall_ms_max = max(r.wall_ms for r in runs)
        result.wall_ms_mean = sum(r.wall_ms for r in runs) / len(runs)
        result.wall_ms_stdev_sample = (
            statistics.stdev(r.wall_ms for r in runs) if len(runs) > 1 else 0.0
        )

    all_violations = []
    for idx, r in enumerate(runs):
        scen = scenario
        solver = solver_cls(scen)
        if solution_limit is not None:
            solver = solver_cls(scen, solution_limit=int(solution_limit))
        else:
            solver = solver_cls(scen)
        wall_start = time.perf_counter()
        sol = solver.solve()
        _ = (time.perf_counter() - wall_start) * 1000.0
        _, viols = _validate_solution(scen, sol)
        all_violations.extend(viols)
    if all_violations:
        result.violations = list(dict.fromkeys(all_violations))

    return result


def run_benchmark(
    solver_classes: List[type[Solver]],
    scenario: Scenario,
    repeats: int = 3,
    solution_limit: Optional[int] = None,
) -> BenchmarkSummary:
    """Run each solver ``repeats`` times and report per-solver aggregates."""
    if solution_limit is not None and solution_limit < 1:
        raise ValueError("solution_limit must be >= 1")

    results: List[BenchmarkResult] = []
    for solver_cls in solver_classes:
        results.append(
            _run_solver(
                solver_cls,
                scenario,
                repeats,
                scenario.seed,
                solution_limit=solution_limit,
            )
        )

    best_known = min((r.cost for r in results if r.feasible), default=float("inf"))
    for r in results:
        if best_known == 0.0:
            r.gap_pct = 0.0
        elif r.feasible:
            r.gap_pct = ((r.cost - best_known) / best_known) * 100.0
        else:
            r.gap_pct = float("inf")

    return BenchmarkSummary(scenario_seed=scenario.seed, best_known=best_known, results=results)
