"""Deterministic benchmark runner comparing solver implementations.

Runs each requested solver multiple times on a single fixed in-code scenario
(reproducible via a fixed seed) and reports repeated-run metrics. The best
known cost is the minimum across all solvers so results are compared fairly.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import networkx as nx

from app.algorithms.base import Solver
from app.algorithms.models import Scenario


@dataclass
class BenchmarkRun:
    """Metrics from a single solver repetition."""

    cost: float
    runtime_ms: float


@dataclass
class BenchmarkResult:
    """Aggregated metrics for one solver over its repeated runs."""

    solver_id: str
    cost: float
    gap_pct: float
    runtime_ms: float
    feasible: bool
    runs: List[BenchmarkRun] = field(default_factory=list)

    @property
    def cost_mean(self) -> float:
        return self.cost

    @property
    def cost_std(self) -> float:
        if not self.runs:
            return 0.0
        vals = [r.cost for r in self.runs]
        mean = sum(vals) / len(vals)
        return (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5


@dataclass
class BenchmarkSummary:
    """Best-known cost plus per-solver results."""

    scenario_seed: int
    best_known: float
    results: List[BenchmarkResult] = field(default_factory=list)


ScenarioFactory = Callable[[...], Scenario]


def _run_solver(
    solver_cls: type[Solver],
    scenario: Scenario,
    repeats: int,
    seed: int,
) -> BenchmarkResult:
    runs: List[BenchmarkRun] = []
    costs: List[float] = []
    best_cost = float("inf")
    feasible = True

    for _ in range(repeats):
        solver = solver_cls(scenario)
        start = time.perf_counter()
        solution = solver.solve()
        elapsed = (time.perf_counter() - start) * 1000.0
        if not solution.feasible:
            feasible = False
        cost = solution.total_cost
        costs.append(cost)
        if cost < best_cost:
            best_cost = cost
        runs.append(BenchmarkRun(cost=cost, runtime_ms=elapsed))

    mean = sum(costs) / len(costs)
    return BenchmarkResult(
        solver_id=solver_cls.solver_id,
        cost=mean,
        gap_pct=0.0,  # filled after best_known is known
        runtime_ms=sum(r.runtime_ms for r in runs) / len(runs),
        feasible=feasible,
        runs=runs,
    )


def run_benchmark(
    solver_classes: List[type[Solver]],
    scenario: Scenario,
    repeats: int = 3,
) -> BenchmarkSummary:
    """Run each solver ``repeats`` times and report per-solver aggregates."""
    results: List[BenchmarkResult] = []
    for solver_cls in solver_classes:
        results.append(_run_solver(solver_cls, scenario, repeats, scenario.seed))

    best_known = min((r.cost for r in results if r.feasible), default=float("inf"))
    for r in results:
        if best_known == 0.0:
            r.gap_pct = 0.0
        elif r.feasible:
            r.gap_pct = ((r.cost - best_known) / best_known) * 100.0
        else:
            r.gap_pct = float("inf")

    return BenchmarkSummary(scenario_seed=scenario.seed, best_known=best_known, results=results)
