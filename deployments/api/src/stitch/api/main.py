from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from opentelemetry.sdk.trace import TracerProvider
from sqlalchemy.exc import OperationalError
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE
from stitch.observability import (
    configure_logging,
    configure_tracing,
    instrument_fastapi,
    instrument_httpx,
    resource_attributes_from_env,
    shutdown_tracing,
)
from .middleware import register_middlewares
from .db.config import dispose_engine
from .auth import validate_auth_config_at_startup
from .settings import Settings, get_settings

from .routers.auth import router as auth_router
from .routers.health import router as health_router
from .routers.oil_gas_fields import router as ogfield_resource_router
from .routers.oil_gas_field_sources import router as ogfield_source_router

base_router = APIRouter(prefix="/api/v1")
base_router.include_router(auth_router)
base_router.include_router(health_router)
base_router.include_router(ogfield_resource_router)
base_router.include_router(ogfield_source_router)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.started_at = datetime.now(UTC)
    app.state.auth_config_validated = False
    validate_auth_config_at_startup()
    app.state.auth_config_validated = True
    yield
    await dispose_engine()
    shutdown_tracing(getattr(app.state, "tracer_provider", None))


async def db_unavailable_handler(_request: Request, _exc: OperationalError):
    return JSONResponse(
        status_code=HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Database unavailable."},
    )


def create_app(
    settings: Settings, *, tracer_provider: TracerProvider | None
) -> FastAPI:
    application = FastAPI(lifespan=lifespan)
    application.state.tracer_provider = tracer_provider
    register_middlewares(application=application, settings=settings)
    if tracer_provider is not None:
        instrument_fastapi(application)
    application.include_router(base_router)
    application.add_exception_handler(OperationalError, db_unavailable_handler)
    return application


settings = get_settings()

configure_logging(
    level=settings.log_level,
    log_format=settings.log_format,
    resource_attributes=resource_attributes_from_env(),
)

_tracer_provider = configure_tracing(
    service_name="stitch-api",
    enabled=settings.otel_enabled,
    exporter=settings.otel_traces_exporter,
    otlp_endpoint=settings.otel_exporter_otlp_endpoint,
    sample_ratio=settings.otel_sample_ratio,
    version=settings.app_version,
    environment=settings.environment_name,
)
app = create_app(settings, tracer_provider=_tracer_provider)

if _tracer_provider is not None:
    instrument_httpx()
