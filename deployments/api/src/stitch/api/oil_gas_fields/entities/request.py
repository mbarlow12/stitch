from typing import Literal

from pydantic import BaseModel, Field

from stitch.api.entities import PaginationParams
from stitch.ogsi.model import GEM_SRC, LLM_SRC, RMI_SRC, WM_SRC
from stitch.ogsi.model.types import (
    FieldStatus,
    LocationType,
    OGSISrcKey,
    PrimaryHydrocarbonGroup,
    ProductionConventionality,
)

OGSI_SOURCE_DEFAULT: tuple[OGSISrcKey, ...] = (RMI_SRC, GEM_SRC, WM_SRC, LLM_SRC)

SortableField = Literal[
    "name",
    "name_local",
    "basin",
    "state_province",
    "region",
    "id",
    "country",
    "field_status",
    "location_type",
    "production_conventionality",
    "primary_hydrocarbon_group",
    "discovery_year",
    "production_start_year",
    "fid_year",
    "latitude",
    "longitude",
    "resource_id",
]


class OGFieldFilterParams(BaseModel):
    q: str | None = None
    id: int | None = None
    name: str | None = None
    name_local: str | None = None
    basin: str | None = None
    state_province: str | None = None
    region: str | None = None
    country: str | None = None
    field_status: FieldStatus | None = None
    location_type: LocationType | None = None
    production_conventionality: ProductionConventionality | None = None
    primary_hydrocarbon_group: PrimaryHydrocarbonGroup | None = None


class OGFieldSortParams(BaseModel):
    sort_by: SortableField = "name"
    sort_order: Literal["asc", "desc"] = "asc"


class OGFieldQueryParams(PaginationParams, OGFieldFilterParams, OGFieldSortParams):
    source: list[OGSISrcKey] = Field(default_factory=lambda: list(OGSI_SOURCE_DEFAULT))


class MergeCandidateCreateRequest(BaseModel):
    resource_ids: list[int] = Field(..., min_length=2)


class MergeCandidateReviewRequest(BaseModel):
    review_notes: str | None = None


class GenerateMergeCandidatesRequest(BaseModel):
    params: OGFieldQueryParams
