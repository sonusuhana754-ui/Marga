"""Response schemas for the live traffic feed."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.optimize import TrafficSnapshot


class TrafficSnapshotResponse(BaseModel):
    """Live traffic readings for a loaded graph, or the reason there are none."""

    configured: bool = Field(
        ...,
        description="False when no API key is configured — no feed, no readings.",
    )
    graph_key: str = Field(..., description="Graph the readings were taken from")
    snapshot: Optional[TrafficSnapshot] = Field(
        default=None,
        description="The readings, when the feed answered. Null is never "
        "replaced with simulated data.",
    )
    detail: Optional[str] = Field(
        default=None,
        description="Human-readable reason when `snapshot` is null.",
    )
