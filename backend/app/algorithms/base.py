"""Common solver interface for static fleet optimization.

A single static fleet contract: given a :class:`Scenario`, solve it and
return a :class:`Solution`. This is intentionally minimal and independent of
any HTTP/API wiring. Future metahurestic solvers (QPSO, VA-QPSO, ...) and the
OR-Tools baseline implement this same interface so they can be compared fairly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.algorithms.models import Scenario, Solution


class Solver(ABC):
    """Interface implemented by every fleet optimization solver."""

    #: Human/domain identifier, e.g. "ortools", "qpso".
    solver_id: str = "base"

    def __init__(self, scenario: Scenario) -> None:
        self.scenario = scenario

    @abstractmethod
    def solve(self) -> Solution:
        """Produce a :class:`Solution` for the scenario bound to this solver."""
        raise NotImplementedError
