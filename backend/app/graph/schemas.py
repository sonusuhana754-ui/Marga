"""Pydantic schemas for graph metadata and statistics."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

DEFAULT_SPEED_KMH: float = 50.0
"""Default assumed driving speed in km/h for travel-time calculation."""


class GraphMetadata(BaseModel):
    """
    Serializable snapshot of a cached graph's key properties and statistics.
    """

    graph_key: str = Field(..., description="Deterministic cache key for the graph", examples=["san_francisco_abc123def456"])
    place: str = Field(..., description="Original place name used for loading", examples=["San Francisco, California, USA"])
    nodes: int = Field(..., ge=0, description="Number of intersection/segment-end nodes", examples=[5432])
    edges: int = Field(..., ge=0, description="Number of directed road segments", examples=[12345])
    total_length_km: float = Field(..., ge=0.0, description="Sum of all edge lengths in kilometres", examples=[845.32])
    avg_travel_time_s: float = Field(..., ge=0.0, description="Mean travel_time across all edges in seconds", examples=[42.1])
    default_speed_kmh: float = Field(
        default=DEFAULT_SPEED_KMH,
        ge=0.0,
        description="Assumed driving speed (km/h) used for travel-time calculation",
        examples=[50.0],
    )
    is_strongly_connected: Optional[bool] = Field(
        None,
        description="Whether the largest strongly-connected component covers all nodes",
    )
    scc_node_count: Optional[int] = Field(
        None,
        ge=0,
        description="Node count of the largest strongly-connected component",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "graph_key": "san_francisco_abc123def456",
                "place": "San Francisco, California, USA",
                "nodes": 5432,
                "edges": 12345,
                "total_length_km": 845.32,
                "avg_travel_time_s": 42.1,
                "default_speed_kmh": 50.0,
                "is_strongly_connected": False,
                "scc_node_count": 5100,
            }
        }
    }
