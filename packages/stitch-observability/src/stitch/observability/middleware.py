from contextvars import ContextVar
from time import perf_counter
from typing import TYPE_CHECKING
from uuid import uuid4

import logging

from opentelemetry import trace

try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.routing import Match
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "stitch.observability.middleware requires Starlette; "
        "install it via the extra: stitch-observability[asgi]"
    ) from exc

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

_request_logger = logging.getLogger("stitch.observability.request")

REQUEST_ID_HEADER = "X-Request-ID"
SCENARIO_HEADER = "X-Stitch-Perf-Scenario"
_SCENARIO_MAX_CHARS = 80

request_id_var: ContextVar[str | None] = ContextVar("stitch_request_id", default=None)
route_var: ContextVar[str | None] = ContextVar("stitch_route", default=None)
scenario_var: ContextVar[str | None] = ContextVar("stitch_scenario", default=None)


def _route_template(request: "Request") -> str:
    for route in request.app.routes:
        match, _ = route.matches(request.scope)
        if match == Match.FULL:
            return getattr(route, "path", request.url.path)
    return request.url.path


class RequestContextMiddleware(BaseHTTPMiddleware):
    def on_request_start(self, request: "Request") -> object:
        return None

    def request_log_fields(self, state: object) -> dict:
        return {}

    def on_request_finish(self, state: object) -> None: ...

    async def dispatch(self, request: "Request", call_next) -> "Response":
        request_id = uuid4().hex
        route = _route_template(request)
        scenario = request.headers.get(SCENARIO_HEADER)
        if scenario:
            scenario = scenario[:_SCENARIO_MAX_CHARS]

        id_token = request_id_var.set(request_id)
        route_token = route_var.set(route)
        scenario_token = scenario_var.set(scenario)
        try:
            state = self.on_request_start(request)

            span = trace.get_current_span()
            span.set_attribute("stitch.request_id", request_id)
            if scenario:
                span.set_attribute("stitch.scenario", scenario)

            start = perf_counter()
            status_code = 500
            try:
                response = await call_next(request)
                status_code = response.status_code
                response.headers[REQUEST_ID_HEADER] = request_id
                return response
            finally:
                try:
                    event = {
                        "request_id": request_id,
                        "method": request.method,
                        "route": route,
                        "status_code": status_code,
                        "duration_ms": round((perf_counter() - start) * 1000.0, 2),
                        "scenario": scenario,
                    }
                    event.update(self.request_log_fields(state))
                    _request_logger.info("request", extra={"event": event})
                finally:
                    self.on_request_finish(state)
        finally:
            request_id_var.reset(id_token)
            route_var.reset(route_token)
            scenario_var.reset(scenario_token)
