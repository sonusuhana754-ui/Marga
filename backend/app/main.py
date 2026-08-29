import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.api.v1.router import api_router

# Initialize structured logging
setup_logging()
logger = get_logger("marga.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager for startup and shutdown events.
    Replaces deprecated @app.on_event("startup") and @app.on_event("shutdown").
    """
    # ------------------ STARTUP ------------------
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT} | Debug: {settings.DEBUG}")
    logger.info(f"Allowed CORS Origins: {settings.BACKEND_CORS_ORIGINS}")
    logger.info(f"API v1 mounted at: {settings.API_V1_STR}")

    yield

    # ----------------- SHUTDOWN ------------------
    logger.info(f"Shutting down {settings.PROJECT_NAME}... Cleaning up resources.")


def create_application() -> FastAPI:
    """
    Application factory for creating and configuring the FastAPI instance.
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=settings.DESCRIPTION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.DEBUG else None,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # ------------------ CORS Middleware ------------------
    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Process-Time", "X-Request-ID"],
        )

    # ------------------ Process Time & Context Middleware ------------------
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = f"{process_time:.4f}s"
        return response

    # ------------------ Mount Routers ------------------
    # Mount Version 1 API
    app.include_router(api_router, prefix=settings.API_V1_STR)

    # ------------------ Root Endpoint ------------------
    @app.get("/", tags=["Root"], summary="Root Health & Info")
    async def root():
        return JSONResponse(
            content={
                "message": f"Welcome to {settings.PROJECT_NAME}",
                "version": settings.VERSION,
                "status": "online",
                "docs": "/docs" if settings.DEBUG else "Disabled in production",
                "api_v1": settings.API_V1_STR,
                "health": f"{settings.API_V1_STR}/health",
            }
        )

    return app


app = create_application()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
