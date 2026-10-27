import pytest
from opentelemetry.sdk.trace import TracerProvider
from sqlalchemy.exc import OperationalError

from stitch.api.main import create_app, db_unavailable_handler
from stitch.api.settings import get_settings


def test_create_app_registers_db_unavailable_handler() -> None:
    app = create_app(get_settings(), tracer_provider=None)
    assert app.exception_handlers.get(OperationalError) is db_unavailable_handler


def test_create_app_attaches_tracer_provider_to_state() -> None:
    provider = TracerProvider()
    app = create_app(get_settings(), tracer_provider=provider)
    assert app.state.tracer_provider is provider


@pytest.mark.anyio
async def test_db_unavailable_handler_returns_503() -> None:
    response = await db_unavailable_handler(
        None, OperationalError("SELECT 1", None, Exception("boom"))
    )
    assert response.status_code == 503
