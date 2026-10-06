"""Solver registry — the single place that maps a solver id to a class.

Every entry point (the optimize endpoint, the benchmark endpoint, tests) resolves
solvers through here, so adding a variant means editing one dict rather than
threading `if solver == ...` through the service layer.

The three registered solvers are the three arms the design doc's §20 ablation
needs, which is why they are registered together:

    ``ortools``   exact-ish local-search baseline (OR-Tools GLS)
    ``qpso``      fixed-schedule QPSO — the established anchor
    ``va_qpso``   volatility-adaptive QPSO — this project's contribution

Registering only ``va_qpso`` would have made the ablation impossible to run,
which is the failure mode this module exists to prevent.
"""

from __future__ import annotations

from typing import Callable, Dict, List

from app.algorithms.base import Solver
from app.algorithms.models import Scenario, Solution
from app.algorithms.ortools_solver import ORToolsSolver
from app.algorithms.qpso_solver import FixedBetaQPSOSolver, QPSOSolver

#: Solver id -> class. Insertion order is the ablation report order.
SOLVERS: Dict[str, type[Solver]] = {
    "ortools": ORToolsSolver,
    "qpso": FixedBetaQPSOSolver,
    "va_qpso": QPSOSolver,
}

#: The id the API advertises as the project's primary algorithm.
DEFAULT_SOLVER = "va_qpso"

#: Ids that are metaheuristics subject to the §20 ablation, i.e. everything
#: that is not the classical baseline.
ABLATION_ARMS = ("qpso", "va_qpso")


def available() -> List[str]:
    """Solver ids the API accepts, in registration order."""
    return list(SOLVERS)


def get(solver_id: str) -> type[Solver]:
    """Resolve a solver id to its class.

    Raises ``KeyError`` on an unknown id so callers surface a 422 rather than
    silently falling back to a different algorithm than the one requested.
    """
    if solver_id not in SOLVERS:
        raise KeyError(f"Unknown solver '{solver_id}'. Available: {', '.join(SOLVERS)}")
    return SOLVERS[solver_id]


def is_known(solver_id: str) -> bool:
    return solver_id in SOLVERS


def solve(solver_id: str, scenario: Scenario, **kwargs) -> Solution:
    """Instantiate and run a registered solver."""
    return get(solver_id)(scenario, **kwargs).solve()


def describe() -> Dict[str, Dict[str, object]]:
    """Solver metadata for the API's ``/optimize/solvers`` listing."""
    out: Dict[str, Dict[str, object]] = {}
    for solver_id, cls in SOLVERS.items():
        out[solver_id] = {
            "id": solver_id,
            "module": cls.__module__,
            "doc": (cls.__doc__ or "").strip().splitlines()[0] if cls.__doc__ else "",
            "is_metaheuristic": solver_id in ABLATION_ARMS,
            "deterministic": solver_id in ("ortools", "qpso", "va_qpso"),
        }
    return out