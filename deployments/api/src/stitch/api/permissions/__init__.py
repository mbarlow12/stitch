
from typing import cast, get_args

from stitch.auth import TokenClaims
from stitch.auth.permissions import source_read_sources
from stitch.ogsi.model.types import OGSISrcKey

_VALID_SOURCES: frozenset[str] = frozenset(get_args(OGSISrcKey))


def licensed_sources(claims: TokenClaims) -> frozenset[OGSISrcKey]:
    return frozenset(
        cast(OGSISrcKey, source)
        for source in source_read_sources(
            claims.permissions,
            valid_sources=_VALID_SOURCES,
        )
    )
