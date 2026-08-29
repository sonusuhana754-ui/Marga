import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.api.deps import get_current_settings, get_async_db
from app.schemas.health import HealthResponse

router = APIRouter()
logger = get_logger("marga.health")

# Track module initialization / server reference time
_SERVER_START_TIME = time.time()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health & Readiness Check",
    description="Returns the current operational status, environment, version, database connection state, and server uptime.",
)
async def check_health(
    response: Response,
    db: AsyncSession = Depends(get_async_db),
    settings: Settings = Depends(get_current_settings),
) -> HealthResponse:
    """
    Health check endpoint used by Kubernetes, load balancers, and monitoring tools.
    Tests Postgres connection to ensure the API and database are fully operational.
    """
    uptime = time.time() - _SERVER_START_TIME
    database_connected = False
    
    try:
        # Perform low-overhead query to check connection readiness
        await db.execute(text("SELECT 1"))
        database_connected = True
    except Exception as e:
        logger.error(f"Database health check connection failed: {str(e)}")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="healthy" if database_connected else "degraded",
        project_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
        uptime_seconds=round(uptime, 2),
        database_connected=database_connected,
    )
