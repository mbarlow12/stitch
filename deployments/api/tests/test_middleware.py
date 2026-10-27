from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from stitch.api.main import app
from stitch.api.middleware import ALLOWED_HEADERS, ALLOWED_METHODS
from stitch.api.settings import get_settings


@pytest.fixture
async def cors_client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test/api/v1",
    ) as ac:
        yield ac


class TestCorsMiddleware:
    @pytest.fixture
    def allowed_origin(self) -> str:
        settings = get_settings()
        return str(settings.frontend_origin_url).rstrip("/")

    @pytest.fixture
    def disallowed_origin(self) -> str:
        return "http://malicious-site.com"

    @pytest.mark.anyio
    async def test_preflight_request_returns_cors_headers(
        self, cors_client: AsyncClient, allowed_origin: str
    ):
        response = await cors_client.options(
            "/health",
            headers={
                "Origin": allowed_origin,
                "Access-Control-Request-Method": "POST",
            },
        )

        assert response.headers.get("Access-Control-Allow-Origin") == allowed_origin
        assert response.headers.get("Access-Control-Allow-Credentials") == "true"
        assert "Access-Control-Allow-Methods" in response.headers
        assert "Access-Control-Allow-Headers" in response.headers

    @pytest.mark.anyio
    async def test_simple_request_includes_cors_origin_header(
        self, cors_client: AsyncClient, allowed_origin: str
    ):
        response = await cors_client.get(
            "/health",
            headers={"Origin": allowed_origin},
        )

        assert response.status_code == 200
        assert response.headers.get("Access-Control-Allow-Origin") == allowed_origin

    @pytest.mark.anyio
    async def test_credentials_header_is_true(
        self, cors_client: AsyncClient, allowed_origin: str
    ):
        response = await cors_client.get(
            "/health",
            headers={"Origin": allowed_origin},
        )

        assert response.headers.get("Access-Control-Allow-Credentials") == "true"

    @pytest.mark.anyio
    async def test_disallowed_origin_gets_no_cors_headers(
        self, cors_client: AsyncClient, disallowed_origin: str
    ):
        response = await cors_client.get(
            "/health",
            headers={"Origin": disallowed_origin},
        )

        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" not in response.headers

    @pytest.mark.anyio
    async def test_allowed_methods_in_preflight_response(
        self, cors_client: AsyncClient, allowed_origin: str
    ):
        response = await cors_client.options(
            "/health",
            headers={
                "Origin": allowed_origin,
                "Access-Control-Request-Method": "POST",
            },
        )

        allowed_methods_header = response.headers.get(
            "Access-Control-Allow-Methods", ""
        )

        for method in ALLOWED_METHODS:
            assert method in allowed_methods_header, (
                f"Method {method} not in allowed methods"
            )

    @pytest.mark.anyio
    async def test_allowed_headers_in_preflight_response(
        self, cors_client: AsyncClient, allowed_origin: str
    ):
        response = await cors_client.options(
            "/health",
            headers={
                "Origin": allowed_origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization, Content-Type",
            },
        )

        allowed_headers_header = response.headers.get(
            "Access-Control-Allow-Headers", ""
        )

        for header in ALLOWED_HEADERS:
            assert header.lower() in allowed_headers_header.lower(), (
                f"Header {header} not in allowed headers"
            )
