import json
import logging
import os
import sys
from collections.abc import Mapping
from typing import Literal

LogFormat = Literal["json", "plain"]

_RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()) | {
    "message",
    "asctime",
    "taskName",
}

_PLAIN_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        event = getattr(record, "event", None)
        if isinstance(event, dict):
            for key, value in event.items():
                if key not in payload:
                    payload[key] = value

        for key, value in record.__dict__.items():
            if key not in _RESERVED and key != "event" and key not in payload:
                payload[key] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


class ResourceAttributesFilter(logging.Filter):
    def __init__(self, attributes: Mapping[str, str]) -> None:
        super().__init__()
        self._attributes = dict(attributes)

    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in self._attributes.items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True


def resource_attributes_from_env() -> dict[str, str]:
    attributes: dict[str, str] = {}
    service_name = os.getenv("OTEL_SERVICE_NAME")
    if service_name:
        attributes["service.name"] = service_name
    for pair in os.getenv("OTEL_RESOURCE_ATTRIBUTES", "").split(","):
        key, sep, value = pair.partition("=")
        key, value = key.strip(), value.strip()
        if sep and key:
            attributes[key] = value
    return attributes


def configure_logging(
    *,
    level: str | None = None,
    log_format: LogFormat = "json",
    resource_attributes: Mapping[str, str] | None = None,
) -> None:
    level_name = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    resolved = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(_PLAIN_FORMAT))
    if resource_attributes:
        handler.addFilter(ResourceAttributesFilter(resource_attributes))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(resolved)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
