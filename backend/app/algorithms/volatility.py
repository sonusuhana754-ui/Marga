"""Rolling traffic volatility and the adaptive-β mapping.

Implements §5 of the VA-QPSO-AR design: β is driven by *measured* instability of
edge weights over a rolling observation window, not by the iteration index.

    μ_e    = (1/N) Σ_k w_e(k)
    σ²_e   = (1/N) Σ_k [w_e(k) − μ_e]²
    Vol(Z) = normalized average of σ²_e over e ∈ Z
    β(Z)   = clip(βmin + (βmax − βmin)·Vol(Z), βmin, βmax)

High volatility → higher β → broader exploration. Low volatility → lower β →
stronger exploitation. β is bounded by construction, never scheduled to grow
without control.

A note on honesty, because this is the project's claimed contribution: with no
traffic feed attached the window is empty, every σ² is 0, and β sits at βmin.
That is a genuine degradation toward exploitation, not a hidden default, and
callers can detect it via :attr:`RollingVolatility.has_signal`. The design doc is
explicit that "the traffic-volatility → β mapping is a hypothesis until
sensitivity and ablation experiments validate it", so nothing here treats βmin
or βmax as a proven constant — both are constructor arguments.
"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from typing import Deque, Dict, Iterable, List, Mapping, Optional, Sequence, Set


class RollingVolatility:
    """Rolling-window variance tracker over named edge weights.

    Feed observations with :meth:`observe`; query per-edge instability with
    :meth:`sigma_sq` and region-level β with :meth:`beta_for`.

    Normalisation note: σ² has units of (weight)², which vary by edge and by
    speed convention, so a raw average is not comparable across instances. Vol is
    therefore normalised by the maximum σ² currently observed, giving a
    scale-free value in [0, 1]. An edge that is stable relative to its peers
    scores 0 regardless of its absolute variance.
    """

    def __init__(self, window: int = 8, min_observations: int = 2) -> None:
        if window < 2:
            raise ValueError("window must be >= 2")
        if min_observations < 2:
            raise ValueError("min_observations must be >= 2")
        self._window = window
        self._min_observations = min_observations
        self._series: Dict[str, Deque[float]] = defaultdict(
            lambda: deque(maxlen=self._window)
        )
        self._observations = 0

    # -- observation ----------------------------------------------------------

    def observe(self, weights: Mapping[str, float]) -> None:
        """Record one traffic observation for every edge in `weights`."""
        if not weights:
            return
        for edge, value in weights.items():
            value = float(value)
            if not math.isfinite(value):
                continue
            self._series[edge].append(value)
        self._observations += 1

    def observe_graph_travel_times(self, graph) -> None:
        """Convenience: observe every edge's current ``travel_time`` attribute."""
        for u, v, data in graph.edges(data=True):
            tt = data.get("travel_time")
            if tt is not None:
                self.observe({f"{u}->{v}": float(tt)})

    @property
    def has_signal(self) -> bool:
        """True once any edge has enough history to have a meaningful σ²."""
        return any(
            len(v) >= self._min_observations for v in self._series.values()
        )

    @property
    def observations(self) -> int:
        return self._observations

    @property
    def tracked_edges(self) -> int:
        return sum(1 for v in self._series.values() if len(v) >= self._min_observations)

    # -- statistics -----------------------------------------------------------

    def mean(self, edge: str) -> Optional[float]:
        series = self._series.get(edge)
        if not series or len(series) < self._min_observations:
            return None
        return sum(series) / len(series)

    def sigma_sq(self, edge: str) -> float:
        """Population variance of `edge` over the window; 0.0 if under-sampled."""
        series = self._series.get(edge)
        if not series or len(series) < self._min_observations:
            return 0.0
        mu = sum(series) / len(series)
        return sum((v - mu) ** 2 for v in series) / len(series)

    def region_volatility(self, edges: Iterable[str]) -> float:
        """Normalised average σ² over `edges`, in [0, 1].

        Returns 0.0 for an empty or under-sampled region, and when no variance
        exists anywhere in the tracker (nothing to be unstable relative to).
        """
        sigmas = [self.sigma_sq(e) for e in edges]
        sigmas = [s for s in sigmas if s > 0.0]
        if not sigmas:
            return 0.0
        peak = max(sigmas)
        if peak <= 0.0:
            return 0.0
        return min(1.0, (sum(sigmas) / len(sigmas)) / peak)

    # -- β mapping ------------------------------------------------------------

    def beta_for(
        self,
        edges: Iterable[str],
        beta_min: float,
        beta_max: float,
    ) -> float:
        """β for a region: clip(βmin + (βmax − βmin)·Vol(Z), βmin, βmax)."""
        if beta_min > beta_max:
            raise ValueError("beta_min must be <= beta_max")
        vol = self.region_volatility(edges)
        raw = beta_min + (beta_max - beta_min) * vol
        return min(beta_max, max(beta_min, raw))

    def beta_summary(self, edges: Iterable[str]) -> Dict[str, float]:
        """Diagnostics for tests and the benchmark report."""
        edge_list = list(edges)
        return {
            "volatility": self.region_volatility(edge_list),
            "edges": float(len(edge_list)),
            "observations": float(self._observations),
        }


def edges_of_stop_sequence(
    stop_sequence: Sequence[int],
    edge_lookup: Mapping[tuple, str],
) -> List[str]:
    """Map a route's consecutive stop pairs onto named edge ids.

    `edge_lookup` maps ``(u, v)`` position pairs to an edge name. Pairs with no
    entry are skipped rather than guessed, so a region never inflates its
    volatility from untracked edges.
    """
    out: List[str] = []
    for a, b in zip(stop_sequence[:-1], stop_sequence[1:]):
        name = edge_lookup.get((a, b))
        if name is not None:
            out.append(name)
    return out


def normalized_positions(stop_sequence: Sequence[int], origin: tuple) -> List[tuple]:
    """Translate a route into normalised coordinate pairs for volatility lookup.

    `origin` is the scenario's ``(lng, lat)`` reference so that callers can map
    positions back onto whatever coordinate space their edge ids use.
    """
    out: List[tuple] = []
    for pos in stop_sequence:
        out.append((origin[0] + pos * 1e-6, origin[1] + pos * 1e-6))
    return out


def synthesize_traffic_series(
    edge_ids: Sequence[str],
    observations: int,
    rng,
    base: float = 60.0,
    jitter: float = 0.25,
) -> List[Dict[str, float]]:
    """Deterministic synthetic traffic observations for reproducible tests.

    This is test and benchmark scaffolding, not a traffic model: it produces
    stable-but-noisy weights so the adaptive-β path can be exercised
    deterministically. Callers must label any result derived from it as
    synthetic. Produces one dict per observation, keyed by edge id.
    """
    frames: List[Dict[str, float]] = []
    phase = {edge: rng.uniform(0.0, 2 * math.pi) for edge in edge_ids}
    for step in range(observations):
        frame: Dict[str, float] = {}
        for edge in edge_ids:
            wave = 1.0 + jitter * math.sin(2 * math.pi * step / 6.0 + phase[edge])
            noise = 1.0 + rng.uniform(-jitter / 3.0, jitter / 3.0)
            frame[edge] = base * wave * noise
        frames.append(frame)
    return frames


def unique_edges_from_routes(routes: Iterable[Sequence[int]]) -> Set[str]:
    """Collect ``"u-v"`` edge names implied by a set of routes."""
    out: Set[str] = set()
    for route in routes:
        for a, b in zip(route[:-1], route[1:]):
            out.add(f"{a}-{b}")
    return out
