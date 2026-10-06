"""Pydantic request/response schemas for graph endpoints."""

from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from app.graph.schemas import GraphMetadata


class GraphLoadRequest(BaseModel):
    """Request body for loading a graph from OpenStreetMap.

    Give either a *place* name or a geographic *center* ``[lng, lat]`` (plus a
    radius) — the latter is how the map loads any point on Earth without
    needing its administrative name. Exactly one of the two is required.
    """

    place: Optional[str] = Field(
        None,
        min_length=1,
        description="OpenStreetMap place name (e.g. 'Manhattan, New York, USA').",
        examples=["Manhattan, New York, USA"],
    )
    center: Optional[List[float]] = Field(
        None,
        min_length=2,
        max_length=2,
        description="Alternative to `place`: load the drivable network within "
        "`dist_m` of this [lng, lat] point (WGS84).",
        examples=[[77.5946, 12.9716]],
    )
    dist_m: int = Field(
        default=1200,
        ge=300,
        le=3000,
        description="Radius in metres used with `center`. Bounded to keep a "
        "single request from downloading a whole city.",
    )
    force_reload: bool = Field(
        default=False,
        description="If true, discard any cached graph for this key and fetch fresh data.",
    )

    @model_validator(mode="after")
    def _require_exactly_one_target(self) -> "GraphLoadRequest":
        if self.place is None and self.center is None:
            raise ValueError("either 'place' or 'center' must be provided")
        if self.center is not None:
            lng, lat = float(self.center[0]), float(self.center[1])
            if not -180.0 <= lng <= 180.0:
                raise ValueError("center lng must be between -180 and 180")
            if not -90.0 <= lat <= 90.0:
                raise ValueError("center lat must be between -90 and 90")
        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "place": "Manhattan, New York, USA",
                "force_reload": False,
            },
            "examples": [
                {"place": "Manhattan, New York, USA", "force_reload": False},
                {"center": [77.5946, 12.9716], "dist_m": 1200},
            ],
        }
    }


class GraphLoadResponse(BaseModel):
    """Response returned after initiating a graph load."""

    message: str = Field(..., description="Human-readable status message", examples=["Graph loaded successfully"])
    graph_key: str = Field(..., description="Deterministic cache key for the loaded graph", examples=["manhattan_new_york_usa_abc123def456"])
    metadata: GraphMetadata = Field(..., description="Computed metadata and statistics for the loaded graph")


class GraphMetadataListResponse(BaseModel):
    """Response containing metadata for all cached graphs."""

    graphs: List[GraphMetadata] = Field(default_factory=list, description="List of cached graph metadata records")
    count: int = Field(..., ge=0, description="Number of cached graphs", examples=[3])
