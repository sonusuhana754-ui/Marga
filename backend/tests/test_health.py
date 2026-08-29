from fastapi.testclient import TestClient
from app.core.config import settings


def test_root_endpoint(client: TestClient):
    """Test root endpoint returns welcome payload and status."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["version"] == settings.VERSION
    assert "api_v1" in data


def test_health_check_v1(client: TestClient):
    """Test /api/v1/health returns healthy status and metadata."""
    response = client.get(f"{settings.API_V1_STR}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["project_name"] == settings.PROJECT_NAME
    assert data["version"] == settings.VERSION
    assert data["environment"] == settings.ENVIRONMENT
    assert "timestamp" in data
    assert "uptime_seconds" in data
    assert data["uptime_seconds"] >= 0


def test_cors_headers(client: TestClient):
    """Test CORS preflight and response headers."""
    response = client.options(
        f"{settings.API_V1_STR}/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_process_time_header(client: TestClient):
    """Test custom X-Process-Time header is injected by middleware."""
    response = client.get(f"{settings.API_V1_STR}/health")
    assert "x-process-time" in response.headers
