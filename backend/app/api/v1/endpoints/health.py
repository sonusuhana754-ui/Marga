import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status
from app.core.config import Settings
from app.api.deps import get_current_settings
from app.schemas.health import HealthResponse

router = APIRouter()

# Track module initialization / server reference time
_SERVER_START_TIME = time.time()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health & Readiness Check",
    description="Returns the current operational status, environment, version, and server uptime.",
)
async def check_health(
    settings: Settings = Depends(get_current_settings),
) -> HealthResponse:
    """
    Health check endpoint used by Kubernetes, load balancers, and monitoring tools.
    """
    uptime = time.time() - _SERVER_START_TIME

    return HealthResponse(
        status="healthy",
        project_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
        uptime_seconds=round(uptime, 2),
    )
