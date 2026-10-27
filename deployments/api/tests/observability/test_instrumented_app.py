from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from opentelemetry.sdk.trace import TracerProvider

from stitch.api.main import create_app
from stitch.api.settings import get_settings


@pytest.fixture
async def instrumented_client() -> AsyncIterator[AsyncClient]:
    app = create_app(get_settings(), tracer_provider=TracerProvider())
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test/api/v1",
    ) as ac:
        yield ac


@pytest.fixture
def allowed_origin() -> str:
    return str(get_settings().frontend_origin_url).rstrip("/")


@pytest.mark.anyio
async def test_instrumented_partial_match_does_not_crash(
    instrumented_client: AsyncClient,
):
    response = await instrumented_client.options("/auth/me")

    assert response.status_code == 405


@pytest.mark.anyio
async def test_instrumented_preflight_returns_cors_headers(
    instrumented_client: AsyncClient, allowed_origin: str
):
    response = await instrumented_client.options(
        "/auth/me",
        headers={
            "Origin": allowed_origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("Access-Control-Allow-Origin") == allowed_origin
