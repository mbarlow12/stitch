from stitch.observability.middleware import RequestContextMiddleware

from .context import db_stats_var, new_db_stats


class RequestTimingMiddleware(RequestContextMiddleware):
    def on_request_start(self, request) -> tuple:
        stats = new_db_stats()
        token = db_stats_var.set(stats)
        return stats, token

    def request_log_fields(self, state: tuple) -> dict:
        stats, _token = state
        return {
            "db_query_count": stats["count"],
            "db_time_ms": round(stats["time_ms"], 2),
        }

    def on_request_finish(self, state: tuple) -> None:
        _stats, token = state
        db_stats_var.reset(token)
