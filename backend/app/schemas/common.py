"""Schema fragments shared by more than one endpoint.

Kept separate so `/benchmark` does not have to import from `/optimize` just to
reuse a two-field model, which would invert the dependency between two
independent endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ConvergencePoint(BaseModel):
    """One point on a solver's best-found-so-far convergence curve.

    `best_cost` is the running optimum at `iteration`, so the sequence must be
    non-increasing. OR-Tools reports no such curve and leaves the trace empty
    rather than having one synthesised for it.
    """

    iteration: int = Field(..., ge=0, description="Iteration index")
    best_cost: float = Field(..., description="Best objective value found by then")