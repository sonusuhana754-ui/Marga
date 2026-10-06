from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ConvergencePoint

#: Kept as a Literal so a typo is a 422 rather than a silently empty report.
BenchSolver = Literal["ortools", "qpso", "va_qpso"]


class BenchmarkRequest(BaseModel):
    """Which solvers to compare, on which in-code scenario, how many times."""

    solvers: List[BenchSolver] = Field(
        default_factory=lambda: ["ortools", "qpso", "va_qpso"],
        min_length=1,
        description=(
            "Solver ids to compare. Defaults to all registered solvers, which is "
            "the set the design doc's ablation needs."
        ),
    )
    scenario_id: str = Field(
        ...,
        min_length=1,
        description="Identifier of a deterministic in-code scenario.",
        examples=["grid_cvrp_8"],
    )
    repeats: int = Field(
        ...,
        ge=1,
        le=10,
        description="Independent runs per solver. The reported cost is the best run.",
    )
    seed: Optional[int] = Field(
        default=None,
        ge=0,
        description="PRNG seed; defaults to the scenario's own seed.",
    )
    baseline_time_limit_ms: Optional[int] = Field(
        default=2_000,
        ge=0,
        le=60_000,
        description=(
            "Wall-clock budget forwarded to solvers that accept one (currently "
            "the OR-Tools baseline). It is a real input to the comparison, not a "
            "cosmetic knob: the baseline's quality depends on how long it is "
            "allowed to search, so the reported gap is only meaningful alongside "
            "this value. Left unset, a default of 2000 ms applies."
        ),
    )


class BenchmarkRunOut(BaseModel):
    """One solver repetition."""

    cost: float = Field(..., description="Total cost of this run")
    runtime_ms: float = Field(..., ge=0.0, description="Solver-reported runtime")
    vehicles_used: int = Field(..., ge=0, description="Vehicles used")


class BenchmarkSolverResult(BaseModel):
    """Aggregates for one solver across its repetitions."""

    solver_id: str
    cost: float = Field(..., description="Mean cost across repetitions")
    best_cost: float = Field(
        ...,
        description=(
            "Best single-run cost. Reported separately from the mean because with "
            "a stochastic solver the two can differ materially, and quoting only "
            "the mean hides the best result while quoting only the best hides the "
            "spread."
        ),
    )
    convergence: List[ConvergencePoint] = Field(
        default_factory=list,
        description=(
            "Best-found cost per iteration from the best run. Empty for solvers "
            "that report no per-iteration trace (OR-Tools), which is stated rather "
            "than filled in with a synthetic curve."
        ),
    )
    gap_pct: float = Field(
        ...,
        description=(
            "Cost gap versus the best feasible solver on this scenario, as a "
            "percentage. Negative means this solver was the best."
        ),
    )
    feasible: bool
    runtime_ms_mean: float = Field(..., ge=0.0)
    runtime_ms_min: float = Field(..., ge=0.0)
    runtime_ms_max: float = Field(..., ge=0.0)
    vehicles_used_min: int = Field(..., ge=0)
    vehicles_used_max: int = Field(..., ge=0)
    total_distance_m: float = Field(..., ge=0.0)
    total_time_s: float = Field(..., ge=0.0)
    runs: List[BenchmarkRunOut] = Field(default_factory=list)
    violations: List[str] = Field(
        default_factory=list,
        description="Constraint violations observed across the runs.",
    )


class BenchmarkResponse(BaseModel):
    """A real, locally measured benchmark. No values here are hard-coded."""

    scenario_id: str
    scenario_seed: int
    repeats: int
    best_known: float = Field(
        ...,
        description="Lowest feasible cost achieved by any requested solver.",
    )
    fleet_utilisation: float = Field(..., ge=0.0)
    results: List[BenchmarkSolverResult] = Field(default_factory=list)

    @model_validator(mode="after")
    def _at_least_one_result(self) -> "BenchmarkResponse":
        if not self.results:
            raise ValueError("benchmark produced no solver results")
        return self