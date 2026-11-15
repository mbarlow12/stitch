
import re

from sqlalchemy import event
from sqlalchemy.engine import Engine

from stitch.observability.middleware import (
    request_id_var,
    route_var,
    scenario_var,
)

from .context import db_stats_var, query_name_var
from .sinks import emit_query_event

try:
    from time import perf_counter
except ImportError:
    from time import monotonic as perf_counter

_START_KEY = "_stitch_query_start"
_WHITESPACE = re.compile(r"\s+")


def _normalize_statement(statement: str, max_chars: int) -> str:
    collapsed = _WHITESPACE.sub(" ", statement).strip()
    if len(collapsed) > max_chars:
        return collapsed[:max_chars] + "…"
    return collapsed


def register_query_timing(
    sync_engine: Engine,
    *,
    slow_query_ms: float,
    log_all_queries: bool = False,
    statement_max_chars: int = 2000,
) -> None:

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault(_START_KEY, []).append(perf_counter())

    @event.listens_for(sync_engine, "handle_error")
    def _on_error(exc_context):
        conn = exc_context.connection
        if conn is None:
            return
        start_stack = conn.info.get(_START_KEY)
        if start_stack:
            start_stack.pop()

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):
        start_stack = conn.info.get(_START_KEY)
        if not start_stack:
            return
        elapsed_ms = (perf_counter() - start_stack.pop()) * 1000.0

        stats = db_stats_var.get()
        if stats is not None:
            stats["count"] += 1
            stats["time_ms"] += elapsed_ms

        if not (log_all_queries or elapsed_ms >= slow_query_ms):
            return

        try:
            rowcount = cursor.rowcount
        except Exception:
            rowcount = None

        event = {
            "duration_ms": round(elapsed_ms, 2),
            "rowcount": rowcount if rowcount is not None and rowcount >= 0 else None,
            "executemany": executemany,
            "statement": _normalize_statement(statement, statement_max_chars),
            "request_id": request_id_var.get(),
            "route": route_var.get(),
            "scenario": scenario_var.get(),
        }
        if (query_name := query_name_var.get()) is not None:
            event["query_name"] = query_name
        emit_query_event(event)
