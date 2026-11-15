import logging
from typing import TYPE_CHECKING, Literal, get_args

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from fastapi import FastAPI
    from opentelemetry.sdk.trace import ReadableSpan
    from sqlalchemy.engine import Engine

    from .settings import OTelSettings

_span_logger = logging.getLogger("stitch.observability.trace")

_MAX_ATTR_CHARS = 2000
_MAX_ATTR_ITEMS = 100

ExporterMode = Literal["console", "otlp", "none"]
_VALID_EXPORTERS = get_args(ExporterMode)


def _truncate_str(value: str) -> str:
    if len(value) > _MAX_ATTR_CHARS:
        return value[:_MAX_ATTR_CHARS] + "…"
    return value


def _truncate_value(value: object) -> object:
    if isinstance(value, str):
        return _truncate_str(value)
    if isinstance(value, (list, tuple)):
        capped: list = [
            _truncate_str(item) if isinstance(item, str) else item
            for item in value[:_MAX_ATTR_ITEMS]
        ]
        if len(value) > _MAX_ATTR_ITEMS:
            capped.append(f"…(+{len(value) - _MAX_ATTR_ITEMS} more)")
        return capped
    return value


def _truncate_attributes(attributes: dict) -> dict:
    return {key: _truncate_value(value) for key, value in attributes.items()}


class LoggingSpanExporter(SpanExporter):
    def __init__(self) -> None:
        self._resource_cache: dict[int, dict] = {}

    def _resource_attributes(self, resource: "Resource | None") -> dict:
        if resource is None:
            return {}
        cached = self._resource_cache.get(id(resource))
        if cached is None:
            cached = _truncate_attributes(dict(resource.attributes))
            self._resource_cache[id(resource)] = cached
        return cached

    def export(self, spans: "Sequence[ReadableSpan]") -> SpanExportResult:
        for span in spans:
            ctx = span.get_span_context()
            parent = span.parent
            duration_ms = (
                round((span.end_time - span.start_time) / 1e6, 2)
                if span.end_time is not None and span.start_time is not None
                else None
            )
            _span_logger.info(
                "span",
                extra={
                    "event": {
                        "span_name": span.name,
                        "trace_id": format(ctx.trace_id, "032x"),
                        "span_id": format(ctx.span_id, "016x"),
                        "parent_span_id": format(parent.span_id, "016x")
                        if parent is not None
                        else None,
                        "kind": span.kind.name,
                        "duration_ms": duration_ms,
                        "status": span.status.status_code.name,
                        "attributes": _truncate_attributes(dict(span.attributes or {})),
                        "resource": self._resource_attributes(span.resource),
                    }
                },
            )
        return SpanExportResult.SUCCESS

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True


def configure_tracing(
    *,
    service_name: str,
    enabled: bool = True,
    exporter: ExporterMode = "console",
    otlp_endpoint: str | None = None,
    sample_ratio: float = 1.0,
    version: str | None = None,
    environment: str | None = None,
    extra_resource_attributes: "Mapping[str, str] | None" = None,
) -> TracerProvider | None:
    if exporter not in _VALID_EXPORTERS:
        raise ValueError(
            f"exporter must be one of {_VALID_EXPORTERS}, got {exporter!r}"
        )
    if not 0.0 <= sample_ratio <= 1.0:
        raise ValueError(f"sample_ratio must be in [0.0, 1.0], got {sample_ratio!r}")
    if not enabled or exporter == "none":
        return None

    attributes: dict[str, str] = {"service.name": service_name}
    if version:
        attributes["service.version"] = version
    if environment:
        attributes["deployment.environment"] = environment
    if extra_resource_attributes:
        attributes.update(extra_resource_attributes)
    resource = Resource.create(attributes)
    sampler = ParentBased(root=TraceIdRatioBased(sample_ratio))
    provider = TracerProvider(resource=resource, sampler=sampler)

    if exporter == "otlp":
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
        )
    else:
        provider.add_span_processor(SimpleSpanProcessor(LoggingSpanExporter()))

    trace.set_tracer_provider(provider)
    return provider


def shutdown_tracing(provider: TracerProvider | None) -> None:
    if provider is not None:
        provider.shutdown()


def instrument_fastapi(app: "FastAPI") -> None:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)


def instrument_httpx() -> None:
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    HTTPXClientInstrumentor().instrument()


def instrument_httpx2() -> None:
    from opentelemetry.instrumentation.httpx import HTTPX2ClientInstrumentor

    HTTPX2ClientInstrumentor().instrument()


def instrument_sqlalchemy(engine: "Engine") -> None:
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    SQLAlchemyInstrumentor().instrument(engine=engine)


def setup_fastapi_tracing(
    app: "FastAPI",
    *,
    service_name: str,
    settings: "OTelSettings",
    instrument_outbound_httpx: bool = True,
    version: str | None = None,
    environment: str | None = None,
    extra_resource_attributes: "Mapping[str, str] | None" = None,
) -> "TracerProvider | None":
    provider = configure_tracing(
        service_name=service_name,
        enabled=settings.otel_enabled,
        exporter=settings.otel_traces_exporter,
        otlp_endpoint=settings.otel_exporter_otlp_endpoint,
        sample_ratio=settings.otel_sample_ratio,
        version=version,
        environment=environment,
        extra_resource_attributes=extra_resource_attributes,
    )
    if provider is not None:
        instrument_fastapi(app)
        if instrument_outbound_httpx:
            instrument_httpx()
    return provider


def setup_sqlalchemy_tracing(engine: "Engine", *, settings: "OTelSettings") -> bool:
    if not settings.otel_enabled or settings.otel_traces_exporter == "none":
        return False
    instrument_sqlalchemy(engine)
    return True
