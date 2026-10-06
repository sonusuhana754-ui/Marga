from fastapi import APIRouter
from app.api.v1.endpoints import benchmark, graph, health, optimize, route, traffic

api_router = APIRouter()

# Register endpoint routers under /api/v1
api_router.include_router(
    health.router,
    tags=["Health"],
)
api_router.include_router(
    graph.router,
    tags=["Graph"],
)
api_router.include_router(
    traffic.router,
    tags=["Traffic"],
)
api_router.include_router(
    route.router,
    tags=["Route"],
)
api_router.include_router(
    optimize.router,
    tags=["Optimize"],
)
api_router.include_router(
    benchmark.router,
    tags=["Benchmark"],
)
