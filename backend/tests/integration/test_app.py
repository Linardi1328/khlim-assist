import httpx
import pytest
from app.config.settings import Settings
from app.main import create_app


@pytest.mark.asyncio
async def test_fastapi_application_startup_and_health_endpoint() -> None:
    app = create_app(Settings(app_env="test"))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app_name": "KHLIM Assist",
        "app_env": "test",
        "version": "0.1.0",
    }
