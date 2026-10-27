
import logging

_query_logger = logging.getLogger("stitch.api.observability.query")


def emit_query_event(event: dict) -> None:
    _query_logger.info("db_query", extra={"event": event})
