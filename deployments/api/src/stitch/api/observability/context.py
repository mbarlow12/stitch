from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TypedDict

__all__ = [
    "DbStats",
    "db_stats_var",
    "named_query",
    "new_db_stats",
    "query_name_var",
]


class DbStats(TypedDict):
    count: int
    time_ms: float


db_stats_var: ContextVar[DbStats | None] = ContextVar("stitch_db_stats", default=None)

query_name_var: ContextVar[str | None] = ContextVar("stitch_query_name", default=None)


def new_db_stats() -> DbStats:
    return {"count": 0, "time_ms": 0.0}


@contextmanager
def named_query(name: str) -> Iterator[None]:
    token = query_name_var.set(name)
    try:
        yield
    finally:
        query_name_var.reset(token)
