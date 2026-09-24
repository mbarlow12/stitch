from dataclasses import dataclass, field
from typing import Literal

from stitch.models.types import CountryCodeAlpha3, Latitude, Longitude, Year

from stitch.ogsi.model.types import (
    LocationType,
    ProductionConventionality,
    PrimaryHydrocarbonGroup,
    FieldStatus,
)

ConfidenceStr = Literal["low", "medium", "high"]
ConfidenceScore = Literal[0, 1, 2]


@dataclass(frozen=True)
class OilGasFieldMatchRecord:
    id: int

    name: str | None

    country: CountryCodeAlpha3 | None
    """ISO 3166-1 alpha-3 country code."""

    latitude: Latitude | None = None
    """Latitude in WGS84 coordinate system."""

    longitude: Longitude | None = None
    """Longitude in WGS84 coordinate system."""

    name_local: str | None = None
    """Name in local script if different from primary name."""

    state_province: str | None = None
    """State or province where the resource is located."""

    region: str | None = None
    """Geographic or administrative region."""

    basin: str | None = None
    """Geological basin name."""

    location_type: LocationType | None = None
    """Whether the resource is onshore or offshore."""

    production_conventionality: ProductionConventionality | None = None
    """Production conventionality classification."""

    primary_hydrocarbon_group: PrimaryHydrocarbonGroup | None = None
    """Primary hydrocarbon type aligned with OGSI nomenclature."""

    reservoir_formation: str | None = None
    """Name or description of the reservoir formation."""

    discovery_year: Year | None = None
    """Year of discovery."""

    production_start_year: Year | None = None
    """Actual or planned year of first production."""

    fid_year: Year | None = None
    """Year of final investment decision."""

    field_status: FieldStatus | None = None
    """Current status of the field."""


@dataclass(frozen=True)
class PreparedItem(OilGasFieldMatchRecord):
    segments: list[str] = []
    core: str | None = None
    tokens: frozenset[str] = field(default_factory=frozenset)
    parentheticals: list[str] = []
    keys: list[str] = []
    discriminators: frozenset[str] = field(default_factory=frozenset)
    anchors: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class Signals:
    normalized_names: list[str] = field(default_factory=list)
    min_name_similarity: int | None = None
    countries: list[str] = field(default_factory=list)
    same_country: bool = False
    max_distance_km: float | None = None
    discriminators: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CandidateGroup:
    resource_ids: list[int] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    signals: Signals = field(default_factory=Signals)
    confidence: ConfidenceStr = field(default="low")
