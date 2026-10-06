"""Quantum-inspired particle swarm with a volatility-adaptive β.

Implements §6 and §9 steps 10–22 of the VA-QPSO-AR design.

The QPSO update, per particle ``i`` and dimension ``j``::

    φ_ij   = θ_ij · p_ij + (1 − θ_ij) · pg_j
    mbest_j = (1/S) Σ_i p_ij
    L_ij   = 2 · β · |mbest_j − x_ij|
    x_ij  ← φ_ij ± 0.5 · L_ij · ln(1 / r_ij)
    θ_ij, r_ij ~ Uniform(0, 1)

``θ`` mixes a particle's own memory toward the swarm's, ``mbest`` is the mean
best position (the distribution's centre), and the logarithmic term is the
inverse-CDF sampling step that gives QPSO its quantum-inspired character.

The β schedule is the extension this project proposes. Standard QPSO fixes β or
schedules it against the iteration count; here β is recomputed per particle from
the measured traffic volatility of the region that particle's route covers::

    β_i = clip(βmin + (βmax − βmin) · Vol(region_i), βmin, βmax)

Set ``beta_mode="fixed"`` to reproduce the plain anchor algorithm, which is what
the ablation in §20 requires: any claimed gain from adaptive β has to be measured
against a fixed-β swarm on the same instance and seed, or the improvement may
have come from local search or encoding instead.

Position encoding is the random-key scheme in :mod:`app.algorithms.random_key`;
this module stays purely continuous and takes a ``fitness`` callable so it can be
tested against a toy function before it is trusted on a road network.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple


@dataclass
class ConvergenceTrace:
    """Best-fitness-per-iteration, for honest convergence plots."""

    points: List[Tuple[int, float]] = field(default_factory=list)

    def record(self, iteration: int, best: float) -> None:
        self.points.append((iteration, best))

    def as_pairs(self) -> List[Tuple[int, float]]:
        return list(self.points)

    def best(self) -> float:
        return min((c for _i, c in self.points), default=float("inf"))


@dataclass
class QPSOConfig:
    """Swarm parameters. Defaults are starting points, not tuned constants.

    The design doc is explicit that β bounds and swarm size "must be validated
    experimentally"; treat these as the configuration a study varies, not as
    established values.
    """

    swarm_size: int = 24
    max_iterations: int = 60
    beta_min: float = 0.4
    beta_max: float = 1.0
    #: "fixed" = anchor algorithm, "adaptive" = this project's contribution.
    beta_mode: str = "adaptive"
    #: Independent uniform draws for the θ and r terms.
    seed: int = 0
    #: Stop early once the swarm has not improved for this many iterations.
    stall_limit: int = 20
    #: Keys are drawn in [0, 1); decoding sorts on them.
    key_low: float = 0.0
    key_high: float = 1.0

    def __post_init__(self) -> None:
        if self.swarm_size < 2:
            raise ValueError("swarm_size must be >= 2")
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be >= 1")
        if self.beta_min > self.beta_max:
            raise ValueError("beta_min must be <= beta_max")
        if self.beta_mode not in ("fixed", "adaptive"):
            raise ValueError("beta_mode must be 'fixed' or 'adaptive'")


@dataclass
class QPSOResult:
    """Outcome of a swarm run."""

    best_key: List[float]
    best_fitness: float
    best_particle: int
    convergence: ConvergenceTrace
    #: Mean β actually used per iteration — evidence the schedule is live.
    beta_history: List[float]
    iterations_run: int
    evaluations: int


class QPSOSwarm:
    """Continuous QPSO over `dimension` variables, minimising `fitness`.

    `beta_for` supplies the per-particle β. Pass a callable returning a constant
    to reproduce fixed-schedule QPSO; the solver wires in the volatility map.
    """

    def __init__(
        self,
        dimension: int,
        fitness: Callable[[Sequence[float]], float],
        config: QPSOConfig,
        beta_for: Optional[Callable[[int, Sequence[float]], float]] = None,
        on_evaluate: Optional[Callable[[int, Sequence[float], float], None]] = None,
    ) -> None:
        if dimension < 1:
            raise ValueError("dimension must be >= 1")
        self.dimension = dimension
        self._fitness = fitness
        self.config = config
        self._rng = random.Random(config.seed)
        self._beta_for = beta_for or (lambda particle, keys: config.beta_max)
        #: Called as ``(particle_index, keys, fitness)`` right after each
        #: evaluation, so a caller can cache the decoded artefact and then read
        #: it back when computing that particle's β. Avoids decoding twice.
        self._on_evaluate = on_evaluate

    def _evaluate(self, particle: int, keys: Sequence[float]) -> float:
        value = self._fitness(keys)
        if self._on_evaluate is not None:
            self._on_evaluate(particle, list(keys), value)
        return value

    # -- initialisation -------------------------------------------------------

    def _random_particle(self) -> List[float]:
        lo, hi = self.config.key_low, self.config.key_high
        return [self._rng.uniform(lo, hi) for _ in range(self.dimension)]

    # -- the QPSO update ------------------------------------------------------

    def _sample_new_position(
        self,
        position: Sequence[float],
        personal_best: Sequence[float],
        global_best: Sequence[float],
        mbest: Sequence[float],
        beta: float,
    ) -> List[float]:
        """One QPSO position update, §6."""
        theta = [self._rng.random() for _ in range(self.dimension)]
        r = [self._rng.random() for _ in range(self.dimension)]
        new: List[float] = []
        for j in range(self.dimension):
            phi = theta[j] * personal_best[j] + (1.0 - theta[j]) * global_best[j]
            length = 2.0 * beta * abs(mbest[j] - position[j])
            # ln(1/r) with r in (0,1]; clamp so r == 0 cannot produce -inf.
            rj = r[j] if r[j] > 1e-12 else 1e-12
            sign = 1.0 if self._rng.random() < 0.5 else -1.0
            new.append(phi + sign * 0.5 * length * math.log(1.0 / rj))
        return new

    # -- the loop -------------------------------------------------------------

    def run(self) -> QPSOResult:
        cfg = self.config
        d = self.dimension

        positions = [self._random_particle() for _ in range(cfg.swarm_size)]
        fitnesses = [self._evaluate(i, positions[i]) for i in range(cfg.swarm_size)]
        evaluations = cfg.swarm_size

        pbest_positions = [list(p) for p in positions]
        pbest_fitnesses = list(fitnesses)

        best_i = min(range(cfg.swarm_size), key=lambda i: pbest_fitnesses[i])
        gbest = list(pbest_positions[best_i])
        gbest_fitness = pbest_fitnesses[best_i]

        trace = ConvergenceTrace()
        trace.record(0, gbest_fitness)
        beta_history: List[float] = []
        stalled = 0
        iteration = 0

        for iteration in range(1, cfg.max_iterations + 1):
            mbest = [
                sum(pbest_positions[i][j] for i in range(cfg.swarm_size))
                / cfg.swarm_size
                for j in range(d)
            ]

            beta_sum = 0.0
            for i in range(cfg.swarm_size):
                beta = float(self._beta_for(i, positions[i]))
                beta_sum += beta
                new_position = self._sample_new_position(
                    positions[i], pbest_positions[i], gbest, mbest, beta
                )
                value = self._evaluate(i, new_position)
                evaluations += 1
                positions[i] = new_position
                if value < pbest_fitnesses[i]:
                    pbest_fitnesses[i] = value
                    pbest_positions[i] = list(new_position)

            beta_history.append(beta_sum / cfg.swarm_size)

            current_best = min(pbest_fitnesses)
            if current_best < gbest_fitness - 1e-12:
                gbest_fitness = current_best
                best_i = pbest_fitnesses.index(current_best)
                gbest = list(pbest_positions[best_i])
                stalled = 0
            else:
                stalled += 1
            trace.record(iteration, gbest_fitness)

            if cfg.stall_limit and stalled >= cfg.stall_limit:
                break

        return QPSOResult(
            best_key=list(gbest),
            best_fitness=gbest_fitness,
            best_particle=best_i,
            convergence=trace,
            beta_history=beta_history,
            iterations_run=iteration,
            evaluations=evaluations,
        )


def sphere(x: Sequence[float]) -> float:
    """Standard test function, Σx_i². Used to sanity-check the update rule."""
    return sum(v * v for v in x)
