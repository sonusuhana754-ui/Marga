from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """
    Schema for health check status response.
    """
    status: str = Field(..., description="Application operational status", examples=["healthy"])
    project_name: str = Field(..., description="Project name", examples=["MARGA Backend API"])
    version: str = Field(..., description="API Version", examples=["1.0.0"])
    environment: str = Field(..., description="Deployment environment", examples=["development"])
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Current UTC timestamp")
    uptime_seconds: Optional[float] = Field(None, description="Server uptime in seconds", examples=[124.5])

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "project_name": "MARGA Backend API",
                "version": "1.0.0",
                "environment": "development",
                "timestamp": "2026-08-29T13:00:00Z",
                "uptime_seconds": 124.5,
            }
        }
    }
