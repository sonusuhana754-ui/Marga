"""Pydantic request/response schemas for graph endpoints."""

from typing import List, Optional

from pydantic import BaseModel, Field

from app.graph.schemas import GraphMetadata


class GraphLoadRequest(BaseModel):
    """Request body for loading a graph from OpenStreetMap."""

    place: str = Field(
        ...,
        min_length=1,
        description="OpenStreetMap place name (e.g. 'Manhattan, New York, USA')",
        examples=["Manhattan, New York, USA"],
    )
    force_reload: bool = Field(
        default=False,
        description="If true, discard any cached graph for this place and fetch fresh data.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "place": "Manhattan, New York, USA",
                "force_reload": False,
            }
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
