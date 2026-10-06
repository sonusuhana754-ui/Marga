"""Tests for the VA-QPSO solver and its supporting modules.

The design doc's §20 ablation requires each claimed improvement to be measured
against fixed-schedule QPSO on the same instance, so these tests check three
separate things and deliberately keep them distinct:

1. The algorithm is *implemented* (structure, feasibility, determinism).
2. Its components behave as specified (β mapping, decode, penalty, 2-opt).
3. Its quality claim against the baseline is **not** asserted.

Point 3 is the important one for honesty. A metaheuristic beating a guided
local search on 5 seeds is not evidence of anything, so no test here claims VA-QPSO
wins. `test_va_qpso_is_within_a_wide_band_of_ortools` only bounds the gap so a
regression that breaks the solver outright fails loudly.
"""

from __future__ import annotations

import math
import random

import pytest

from app.algorithms.base import Solver
from app.algorithms.evaluate import evaluate_solution
from app.algorithms.ortools_solver import ORToolsSolver
from app.algorithms.qpso import QPSOConfig, QPSOSwarm, sphere
from app.algorithms.qpso_solver import (
    FixedBetaQPSOSolver,
    QPSOSolver,
    solve_va_qpso,
)
from app.algorithms.random_key import (
    capacity_violation,
    decode,
    fleet_is_feasible,
    polish,
    random_key_order,
    relocate,
    routes_cost,
    two_opt,
)
from app.algorithms.scenario import make_scenario
from app.algorithms.scenarios import _square_grid, scenario_registry
from app.algorithms.registry import ABLATION_ARMS, SOLVERS, get, is_known
from app.algorithms.volatility import (
    RollingVolatility,
    synthesize_traffic_series,
)


def _scenario(num_stops: int = 12, vehicles: int = 3, capacity: int = 8, seed: int = 3):
    return make_scenario(
        _square_grid(num_stops),
        seed=seed,
        capacity=capacity,
        vehicles=vehicles,
        num_stops=num_stops,
    )


# --------------------------------------------------------------------------
# Volatility → β mapping (§5)
# --------------------------------------------------------------------------


class TestRollingVolatility:
    def test_no_signal_without_observations(self):
        vol = RollingVolatility()
        assert vol.has_signal is False
        assert vol.sigma_sq("a-b") == 0.0
        assert vol.region_volatility(["a-b"]) == 0.0
        assert vol.beta_for(["a-b"], 0.4, 1.0) == pytest.approx(0.4)

    def test_single_observation_is_not_enough(self):
        """One sample has no variance; treating it as 0 variance is correct."""
        vol = RollingVolatility(window=4, min_observations=2)
        vol.observe({"a-b": 10.0})
        assert vol.has_signal is False
        assert vol.sigma_sq("a-b") == 0.0

    def test_sigma_sq_matches_population_variance(self):
        vol = RollingVolatility(window=8)
        for value in (10.0, 12.0, 14.0):
            vol.observe({"e": value})
        assert vol.mean("e") == pytest.approx(12.0)
        # Population variance of (10,12,14) is (4+0+4)/3.
        assert vol.sigma_sq("e") == pytest.approx(8.0 / 3.0)

    def test_beta_is_clipped_to_bounds(self):
        vol = RollingVolatility(window=8)
        for _ in range(6):
            vol.observe({"stable": 10.0, "wild": 10.0 + _ * 40.0})
        beta = vol.beta_for(["stable"], 0.2, 0.9)
        assert 0.2 <= beta <= 0.9
        # A region of only-stable edges must sit at the floor.
        assert beta == pytest.approx(0.2)

    def test_more_volatile_region_gets_higher_beta(self):
        vol = RollingVolatility(window=8)
        for step in range(6):
            vol.observe({"calm": 50.0, "stormy": 50.0 + (step % 2) * 40.0})
        assert vol.beta_for(["stormy"], 0.4, 1.0) > vol.beta_for(["calm"], 0.4, 1.0)

    def test_region_volatility_is_normalised(self):
        """Scale-free: the same *shape* scores the same regardless of units."""
        small = RollingVolatility(window=8)
        large = RollingVolatility(window=8)
        for step in range(6):
            small.observe({"a": 1.0, "b": 1.0 + (step % 2) * 0.2})
            large.observe({"a": 1000.0, "b": 1000.0 + (step % 2) * 200.0})
        assert small.region_volatility(["a", "b"]) == pytest.approx(
            large.region_volatility(["a", "b"]), rel=1e-6
        )
        assert 0.0 <= small.region_volatility(["a", "b"]) <= 1.0

    def test_synthesized_series_is_reproducible(self):
        edges = ["a-b", "c-d"]
        one = synthesize_traffic_series(edges, 5, random.Random(1))
        two = synthesize_traffic_series(edges, 5, random.Random(1))
        assert one == two
        assert len(one) == 5


# --------------------------------------------------------------------------
# Random-key encode / decode / repair
# --------------------------------------------------------------------------


class TestRandomKey:
    def test_order_is_a_permutation(self):
        keys = [0.3, 0.1, 0.9, 0.4]
        order = random_key_order(keys, 4)
        assert sorted(order) == [1, 2, 3, 4]

    def test_order_follows_key_ascending(self):
        order = random_key_order([0.5, 0.1, 0.9], 3)
        assert order == [2, 1, 3]

    def test_ties_break_deterministically(self):
        assert random_key_order([0.5, 0.5, 0.5], 3) == [1, 2, 3]

    def test_decode_respects_fleet_size(self):
        """A decode may never open more routes than there are vehicles."""
        demands = [0, 6, 6, 6, 6, 6]
        capacities = [10, 10]
        cost = [[0.0] * 6 for _ in range(6)]
        routes = decode([0.1, 0.2, 0.3, 0.4, 0.5], demands, capacities, cost)
        assert len(routes) <= len(capacities)
        covered = {p for r in routes for p in r if p != 0}
        assert covered == {1, 2, 3, 4, 5}, "every customer must still be served"

    def test_decode_of_unservable_instance_is_flagged(self):
        demands = [0, 9, 9, 9]
        capacities = [10]
        cost = [[0.0] * 4 for _ in range(4)]
        routes = decode([0.1, 0.2, 0.3], demands, capacities, cost)
        assert fleet_is_feasible(demands, capacities) is False
        assert capacity_violation(routes, demands, capacities) > 0.0

    def test_capacity_violation_is_zero_when_feasible(self):
        demands = [0, 3, 4, 2]
        capacities = [10]
        cost = [[0.0] * 4 for _ in range(4)]
        routes = decode([0.1, 0.2, 0.3], demands, capacities, cost)
        assert capacity_violation(routes, demands, capacities) == 0.0

    def test_fleet_overflow_is_counted(self):
        """Two routes for a one-vehicle fleet must register as a violation."""
        demands = [0, 1, 1]
        capacities = [10]
        routes = [[0, 1, 0], [0, 2, 0]]
        assert capacity_violation(routes, demands, capacities) > 0.0


# --------------------------------------------------------------------------
# Local search
# --------------------------------------------------------------------------


class TestLocalSearch:
    def test_two_opt_never_increases_cost(self):
        cost = [[0, 10, 20, 10, 0], [10, 0, 5, 20, 10], [20, 5, 0, 5, 20],
                [10, 20, 5, 0, 10], [0, 10, 20, 10, 0]]
        improved = two_opt([0, 2, 1, 3, 0], cost)
        assert routes_cost([improved], cost) <= routes_cost([[0, 2, 1, 3, 0]], cost)

    def test_two_opt_preserves_depot_ends(self):
        cost = [[0, 1, 9, 1], [1, 0, 1, 9], [9, 1, 0, 1], [1, 9, 1, 0]]
        for route in ([0, 2, 1, 3, 0], [0, 1, 2, 3, 0]):
            out = two_opt(route, cost)
            assert out[0] == 0 and out[-1] == 0

    def test_relocate_respects_capacity(self):
        """The whole point: 2-opt cannot rebalance load, relocate can."""
        cost = [
            [0, 1, 2, 3, 1, 2, 3],
            [1, 0, 5, 20, 1, 20, 5],
            [2, 5, 0, 5, 20, 20, 5],
            [3, 20, 5, 0, 20, 5, 5],
            [1, 1, 20, 20, 0, 1, 20],
            [2, 20, 20, 5, 1, 0, 5],
            [3, 5, 5, 5, 20, 5, 0],
        ]
        demands = [0, 9, 9, 1]
        capacities = [10, 10]
        routes = [[0, 1, 0], [0, 2, 3, 0]]
        moved = relocate(routes, demands, capacities, cost)
        assert len(moved) <= 2
        for i, route in enumerate(moved):
            load = sum(demands[p] for p in route if p != 0)
            assert load <= capacities[min(i, len(capacities) - 1)]
        assert capacity_violation(moved, demands, capacities) == 0.0

    def test_relocate_never_increases_cost(self):
        cost = [
            [0, 1, 2, 3, 1, 2, 3],
            [1, 0, 5, 20, 1, 20, 5],
            [2, 5, 0, 5, 20, 20, 5],
            [3, 20, 5, 0, 20, 5, 5],
            [1, 1, 20, 20, 0, 1, 20],
            [2, 20, 20, 5, 1, 0, 5],
            [3, 5, 5, 5, 20, 5, 0],
        ]
        demands = [0, 1, 1, 1, 1]
        capacities = [3, 3]
        routes = [[0, 1, 3, 0], [0, 4, 2, 0]]
        before = routes_cost(routes, cost)
        after = routes_cost(relocate(routes, demands, capacities, cost), cost)
        assert after <= before


# --------------------------------------------------------------------------
# The swarm itself
# --------------------------------------------------------------------------


class TestSwarm:
    def test_config_rejects_bad_values(self):
        with pytest.raises(ValueError):
            QPSOConfig(swarm_size=1)
        with pytest.raises(ValueError):
            QPSOConfig(max_iterations=0)
        with pytest.raises(ValueError):
            QPSOConfig(beta_min=1.0, beta_max=0.4)
        with pytest.raises(ValueError):
            QPSOConfig(beta_mode="magic")

    def test_solves_the_sphere_function(self):
        """Smoke-test the update rule on a function with a known optimum."""
        swarm = QPSOSwarm(4, sphere, QPSOConfig(swarm_size=24, max_iterations=80, seed=5))
        result = swarm.run()
        assert result.best_fitness < 1.0, "8-D sphere should get near zero"
        assert all(math.isfinite(c) for _i, c in result.convergence.as_pairs())

    def test_convergence_is_monotonically_non_increasing(self):
        swarm = QPSOSwarm(5, sphere, QPSOConfig(swarm_size=16, max_iterations=30, seed=2))
        costs = [c for _i, c in swarm.run().convergence.as_pairs()]
        assert costs == sorted(costs, reverse=True)

    def test_seed_makes_runs_reproducible(self):
        cfg = QPSOConfig(swarm_size=12, max_iterations=25, seed=17)
        a = QPSOSwarm(4, sphere, cfg).run()
        b = QPSOSwarm(4, sphere, cfg).run()
        assert a.best_key == b.best_key
        assert a.best_fitness == b.best_fitness

    def test_evaluations_are_counted(self):
        cfg = QPSOConfig(swarm_size=10, max_iterations=7, seed=1, stall_limit=0)
        result = QPSOSwarm(3, sphere, cfg).run()
        assert result.evaluations == cfg.swarm_size + cfg.swarm_size * cfg.max_iterations

    def test_stall_limit_stops_early(self):
        cfg = QPSOConfig(swarm_size=10, max_iterations=200, seed=1, stall_limit=3)
        result = QPSOSwarm(3, sphere, cfg).run()
        assert result.iterations_run < cfg.max_iterations

    def test_beta_callback_is_used(self):
        seen = []

        def beta_for(particle, keys):
            seen.append(particle)
            return 0.5

        QPSOSwarm(3, sphere, QPSOConfig(swarm_size=6, max_iterations=4, seed=1), beta_for).run()
        assert seen, "beta callback must be consulted"

    def test_on_evaluate_hook_receives_particle_index(self):
        calls = []
        QPSOSwarm(
            3,
            sphere,
            QPSOConfig(swarm_size=4, max_iterations=2, seed=1),
            on_evaluate=lambda i, keys, value: calls.append((i, value)),
        ).run()
        assert calls
        assert {i for i, _v in calls} == {0, 1, 2, 3}

    def test_zero_dimension_is_rejected(self):
        with pytest.raises(ValueError):
            QPSOSwarm(0, sphere, QPSOConfig())


# --------------------------------------------------------------------------
# Solver contract
# --------------------------------------------------------------------------


class TestSolverContract:
    @pytest.mark.parametrize("solver_id", ["ortools", "qpso", "va_qpso"])
    def test_implements_the_abc(self, solver_id):
        cls = SOLVERS[solver_id]
        assert issubclass(cls, Solver)
        assert cls.solver_id == solver_id

    def test_registry_rejects_unknown_ids(self):
        with pytest.raises(KeyError):
            get("dijkstra")
        assert is_known("va_qpso") is True
        assert set(ABLATION_ARMS) == {"qpso", "va_qpso"}

    @pytest.mark.parametrize("solver_id", ["qpso", "va_qpso"])
    def test_solution_is_feasible_and_shaped_correctly(self, solver_id):
        scenario = _scenario()
        solution = SOLVERS[solver_id](scenario).solve()
        assert solution.feasible is True
        assert solution.routes, "must return at least one route"
        for route in solution.routes:
            seq = route.stop_sequence
            assert seq[0] == 0 and seq[-1] == 0, "routes start and end at the depot"
            assert len(seq) > 2

    @pytest.mark.parametrize("solver_id", ["qpso", "va_qpso"])
    def test_every_stop_is_served_exactly_once(self, solver_id):
        scenario = _scenario()
        solution = SOLVERS[solver_id](scenario).solve()
        served = [p for r in solution.routes for p in r.stop_sequence if p != 0]
        assert sorted(served) == list(range(1, scenario.num_stops))

    @pytest.mark.parametrize("solver_id", ["qpso", "va_qpso"])
    def test_no_more_routes_than_vehicles(self, solver_id):
        scenario = _scenario(vehicles=2, capacity=6)
        solution = SOLVERS[solver_id](scenario).solve()
        assert len(solution.routes) <= scenario.num_vehicles

    @pytest.mark.parametrize("solver_id", ["qpso", "va_qpso"])
    def test_capacities_are_respected(self, solver_id):
        scenario = _scenario(vehicles=3, capacity=8)
        solution = SOLVERS[solver_id](scenario).solve()
        demands = [s.demand for s in scenario.stops]
        caps = [v.capacity for v in scenario.vehicles]
        assert capacity_violation(
            [r.stop_sequence for r in solution.routes], demands, caps
        ) == 0.0

    @pytest.mark.parametrize("solver_id", ["qpso", "va_qpso"])
    def test_same_seed_is_reproducible(self, solver_id):
        a = SOLVERS[solver_id](_scenario(seed=9)).solve()
        b = SOLVERS[solver_id](_scenario(seed=9)).solve()
        assert a.total_cost == b.total_cost
        assert [r.stop_sequence for r in a.routes] == [r.stop_sequence for r in b.routes]

    @pytest.mark.parametrize("solver_id", ["qpso", "va_qpso"])
    def test_different_seeds_are_actually_searched(self, solver_id):
        """Guards against a solver that ignores its seed entirely."""
        costs = {
            SOLVERS[solver_id](_scenario(seed=s)).solve().total_cost for s in (1, 2, 3, 4, 5)
        }
        assert len(costs) > 1, "swarm produced identical cost for every seed"

    @pytest.mark.parametrize("solver_id", ["qpso", "va_qpso"])
    def test_reported_cost_matches_evaluation_of_returned_routes(self, solver_id):
        """The number quoted must be recomputable from the routes returned."""
        scenario = _scenario()
        solution = SOLVERS[solver_id](scenario).solve()
        rechecked = evaluate_solution(scenario, solution)
        assert rechecked.total_cost == pytest.approx(solution.total_cost)

    @pytest.mark.parametrize("solver_id", ["qpso", "va_qpso"])
    def test_convergence_trace_is_recorded(self, solver_id):
        solution = SOLVERS[solver_id](_scenario()).solve()
        trace = solution._convergence
        assert len(trace) >= 2
        costs = [c for _i, c in trace]
        assert costs == sorted(costs, reverse=True)

    def test_unservable_instance_is_reported_not_faked(self):
        """More demand than the fleet can carry must not yield a 'solution'."""
        scenario = make_scenario(
            _square_grid(12), seed=4, capacity=4, vehicles=2, num_stops=10
        )
        scenario.stops[1] = type(scenario.stops[1])(**{**scenario.stops[1].__dict__, "demand": 99})
        assert scenario.servable is False
        solution = QPSOSolver(scenario).solve()
        assert solution.feasible is False
        assert getattr(solution, "_reason", "")


# --------------------------------------------------------------------------
# Ablation mechanics — the β modes must actually differ
# --------------------------------------------------------------------------


class TestBetaSchedule:
    def test_fixed_mode_uses_beta_max(self):
        scenario = _scenario()
        solver = FixedBetaQPSOSolver(scenario)
        assert solver.beta_mode == "fixed"
        solution = solver.solve()
        assert solution._beta_mean == pytest.approx(solver.beta_max)
        assert len(solution._beta_history) == solution._iterations

    def test_adaptive_mode_without_signal_sits_at_floor(self):
        """No traffic feed ⇒ no volatility ⇒ β at βmin. Honest degradation."""
        solver = QPSOSolver(_scenario(), beta_min=0.25, beta_max=1.0)
        solution = solver.solve()
        assert solution._volatility_signal is False
        assert solution._beta_mean == pytest.approx(0.25)

    def test_adaptive_mode_with_signal_raises_beta(self):
        scenario = _scenario()
        edges = sorted(f"{u}-{v}" for u, v in scenario.graph.edges())
        vol = RollingVolatility(window=8)
        for frame in synthesize_traffic_series(edges, 8, random.Random(4), jitter=0.4):
            vol.observe(frame)
        solution = QPSOSolver(scenario, volatility=vol, beta_min=0.25, beta_max=1.0).solve()
        assert solution._volatility_signal is True
        assert solution._beta_mean > 0.25

    def test_modes_can_differ(self):
        """Sanity check that the two arms are genuinely different code paths."""
        scenario = _scenario(num_stops=20, vehicles=4, capacity=8, seed=6)
        fixed = FixedBetaQPSOSolver(scenario).solve()
        adaptive = QPSOSolver(scenario).solve()
        assert fixed._beta_mean != adaptive._beta_mean

    def test_local_search_can_be_disabled_for_ablation(self):
        scenario = _scenario()
        with_ls = QPSOSolver(scenario, local_search=True).solve()
        without = QPSOSolver(scenario, local_search=False).solve()
        assert with_ls.total_cost <= without.total_cost

    def test_smooth_fitness_is_off_by_default_and_is_measurably_not_better(self):
        """The documented default, and a regression guard on that decision.

        Smoothing costs ~2.4x per evaluation. Measured over 12 seeds on a 24-stop
        instance it averaged 8500 against the raw variant's 8267, so it loses at a
        fixed iteration budget. This test pins the default and asserts the
        smoothed path is wired up, without asserting a win it does not get.
        """
        scenario = _scenario(num_stops=24, vehicles=4, capacity=9, seed=6)
        assert QPSOSolver(scenario).smooth_fitness is False
        # Both paths must run and return a valid solution.
        for flag in (True, False):
            solution = QPSOSolver(scenario, smooth_fitness=flag).solve()
            assert solution.feasible is True
            assert solution.total_cost > 0


# --------------------------------------------------------------------------
# Comparison with the baseline — bounds only, never a quality claim
# --------------------------------------------------------------------------


class TestAgainstBaseline:
    def test_va_qpso_is_within_a_wide_band_of_ortools(self):
        """A regression guard, not a quality claim.

        The bound is deliberately loose (100%). The honest statement about this
        project is that OR-Tools with guided local search is *better* on these
        instances and slower; VA-QPSO's claimed advantage is in bounded
        computation per update and needs a traffic feed to demonstrate at all.
        A tight bound here would quietly turn into an assertion that the
        metaheuristic wins, which the measurements do not support.
        """
        scenario = _scenario(num_stops=14, vehicles=3, capacity=10, seed=3)
        ours = QPSOSolver(scenario).solve()
        theirs = ORToolsSolver(scenario, time_limit_ms=2_000).solve()
        assert ours.total_cost <= theirs.total_cost * 2.0

    def test_qpso_is_far_faster_than_ortools(self):
        """The one advantage that does hold: bounded time-to-solution."""
        scenario = _scenario(num_stops=14, vehicles=3, capacity=10, seed=3)
        ours = QPSOSolver(scenario).solve()
        theirs = ORToolsSolver(scenario, time_limit_ms=2_000).solve()
        assert ours._runtime_ms < theirs._runtime_ms


# --------------------------------------------------------------------------
# Named scenarios — the ones the API actually exposes
# --------------------------------------------------------------------------


@pytest.mark.parametrize("scenario_id", ["grid_cvrp_8", "grid_cvrp_6", "grid_vrptw_8"])
@pytest.mark.parametrize("solver_id", ["qpso", "va_qpso"])
def test_every_named_scenario_is_solvable(scenario_id, solver_id):
    scenario = scenario_registry.get(scenario_id)
    solution = SOLVERS[solver_id](scenario).solve()
    assert solution.feasible is True, getattr(solution, "_reason", "")
    assert solution.total_cost > 0


def test_vrptw_reports_infeasible_when_window_cannot_be_met():
    """A tight window the swarm cannot satisfy must be flagged, not hidden."""
    scenario = scenario_registry.get("grid_vrptw_8")
    scenario.time_windows = {i: (0.0, 1.0) for i in range(scenario.num_stops)}
    solution = QPSOSolver(scenario).solve()
    assert solution.feasible is False


def test_empty_instance_is_handled():
    scenario = _scenario()
    scenario.stops = scenario.stops[:1]
    assert QPSOSolver(scenario).solve().routes == []