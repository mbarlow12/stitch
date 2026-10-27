from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import APIRouter, FastAPI
from stitch.observability import (
    configure_logging,
    resource_attributes_from_env,
    setup_fastapi_tracing,
    shutdown_tracing,
)

from stitch.llm.auth import validate_auth_config_at_startup
from stitch.llm.client import validate_downstream_auth_config_at_startup
from stitch.llm.middleware import register_middlewares
from stitch.llm.routers.health import router as health_router
from stitch.llm.routers.oil_gas_fields import router as oil_gas_fields_router
from stitch.llm.settings import get_settings

base_router = APIRouter(prefix="/api/v1")
base_router.include_router(health_router)
base_router.include_router(oil_gas_fields_router)

_tracer_provider = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.started_at = datetime.now(UTC)
    app.state.auth_config_validated = False
    app.state.downstream_auth_config_validated = False
    validate_auth_config_at_startup()
    app.state.auth_config_validated = True
    validate_downstream_auth_config_at_startup()
    app.state.downstream_auth_config_validated = True
    yield
    shutdown_tracing(_tracer_provider)


settings = get_settings()

configure_logging(
    level=settings.log_level,
    resource_attributes=resource_attributes_from_env(),
)

app = FastAPI(lifespan=lifespan)

register_middlewares(application=app, settings=settings)

_tracer_provider = setup_fastapi_tracing(
    app,
    service_name="stitch-llm",
    settings=settings,
)

app.include_router(base_router)
