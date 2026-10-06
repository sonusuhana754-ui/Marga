from __future__ import annotations

from app.algorithms import benchmark as bench_mod
from app.algorithms import scenarios
from app.algorithms.ortools_solver import ORToolsSolver


def test_named_cvrp_smoke():
    scen = scenarios.scenario_registry.get("grid_cvrp_6")
    res = bench_mod._run_solver(
        ORToolsSolver,
        scen,
        repeats=1,
        seed=scen.seed,
        solution_limit=1,
    )
    assert res.feasible is True
    assert res.runs[0].total_distance_m >= 0


def test_named_vrptw_smoke():
    scen = scenarios.scenario_registry.get("grid_vrptw_8")
    res = bench_mod._run_solver(
        ORToolsSolver,
        scen,
        repeats=1,
        seed=scen.seed,
        solution_limit=1,
    )
    assert res.feasible is True
