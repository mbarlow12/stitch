
from __future__ import annotations

from collections.abc import Collection
from typing import Final

from stitch.ogsi.model.types import OGSISrcKey

PUBLIC_SOURCES: Final[frozenset[OGSISrcKey]] = frozenset(
    {"gem", "rmi", "llm", "alb", "bc", "nor"}
)
RESTRICTED_SOURCES: Final[frozenset[OGSISrcKey]] = frozenset({"wm", "ccr"})

PROFILES: Final[dict[int, frozenset[OGSISrcKey]]] = {
    0: PUBLIC_SOURCES,
    1: PUBLIC_SOURCES | {"ccr"},
    2: PUBLIC_SOURCES | {"wm"},
    3: PUBLIC_SOURCES | {"wm", "ccr"},
}

PERMISSION_MASKS: Final[tuple[int, ...]] = tuple(PROFILES)

_MASK_BY_PROFILE: Final[dict[frozenset[OGSISrcKey], int]] = {
    sources: mask for mask, sources in PROFILES.items()
}


def read_model_mask(sources: Collection[OGSISrcKey] | None) -> int | None:
    if sources is None:
        return None
    return _MASK_BY_PROFILE.get(frozenset(sources))


def visible_sources_for_mask(mask: int) -> frozenset[OGSISrcKey]:
    return PROFILES[mask]
