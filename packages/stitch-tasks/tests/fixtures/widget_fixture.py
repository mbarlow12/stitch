"""Module docstring that must not reach the rendered markdown."""

from __future__ import annotations

import functools
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, AsyncIterator, Generator, Sequence
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from typing import Literal, NoReturn, Protocol, Self, overload

__all__ = [
    "MAX_WIDGETS",
    "Box",
    "Coord",
    "Registry",
    "Renderable",
    "Widget",
    "build",
    "cached_area",
    "describe",
    "fetch",
    "first",
    "opened",
    "paginate",
    "scaled",
    "spaced",
    "stream",
]

# A module-level comment that must not survive rendering.

type Coord = tuple[float, float]

MAX_WIDGETS: int = 64

_INTERNAL_LIMIT = 8


def first[T](
        items: Sequence[T],
        /,
        *,
        default: T | None = None,
) -> T | None:
    """Return the first item, or the default when empty."""
    return items[0] if items else default


class Box[T]:
    """Generic single-value container."""

    def __init__(self, value: T) -> None:
        self._value = value

    @property
    def value(self) -> T:
        """The wrapped value."""
        return self._value

    def replace(self, value: T, /) -> Self:
        return type(self)(value)

    def _reset(self) -> None: ...


@overload
def describe(target: int) -> str: ...


@overload
def describe(target: str) -> str: ...


def describe(target: int | str) -> str:
    """Describe an int or a str."""
    return str(target)


@functools.lru_cache(maxsize=128)
def cached_area(width: int, height: int) -> int:
    return width * height


@functools.singledispatch
def scaled(value: object, factor: float = 1.0) -> object:
    raise NotImplementedError


@scaled.register
def _(value: int, factor: float = 1.0) -> int:
    return int(value * factor)


@contextmanager
def opened(path: str) -> Generator[str]:
    """Yield an open handle."""
    yield path


@asynccontextmanager
async def stream(url: str) -> AsyncGenerator[bytes]:
    yield b""


async def fetch(url: str, *, retries: int = 3) -> bytes:
    """Fetch bytes over the network."""
    return b""


async def paginate(url: str, page_size: int = 50) -> AsyncIterator[bytes]:
    yield b""


def build(
  name: str,
  *args: int,
  strict: bool = False,
  **options: str,
) -> Widget:
    """Build a widget.

    The nested helpers below must not surface as top-level symbols.
    """

    def _normalize(raw: str) -> str:
        return raw.strip()

    class _Scratch: ...

    return Widget(_normalize(name))


def spaced( first : int ,second : str = 'two' , *, third : float=3.0 ) -> tuple[int, str, float]:
    return (first, second, third)


def never() -> NoReturn:
    raise RuntimeError


class Renderable(Protocol):
    """Protocol for things that render themselves."""

    def render(self, *, indent: int = 0) -> str: ...

    @property
    def visible(self) -> bool: ...


class Registry(ABC):
    """Abstract registry base."""

    registry_name: str

    @abstractmethod
    def lookup(self, key: str) -> Coord | None:
        """Look a coordinate up by key."""

    @staticmethod
    def normalize(key: str) -> str:
        return key.lower()

    @classmethod
    def create( cls , **kwargs : object ) -> Self :
        return cls(**kwargs)

    @property
    @abstractmethod
    def size(self) -> int: ...


@dataclass(frozen=True, slots=True)
class Widget:
    """A widget with a name and coordinates."""

    name: str
    coords: Coord = (0.0, 0.0)
    mode: Literal["draw", "hide"] = "draw"

    def render(self, *, indent: int = 0) -> str:
        return " " * indent + self.name

    def _private(self) -> None: ...


def _helper() -> None: ...


class _Hidden: ...
