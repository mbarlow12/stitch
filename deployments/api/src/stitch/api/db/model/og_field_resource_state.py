from __future__ import annotations

from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from stitch.api.entities import FILTER_OPTION_FIELDS

from .common import Base
from .oil_gas_field_source_value import ATTRIBUTE_NAMES
from .types import PORTABLE_BIGINT, PORTABLE_FLOAT, PORTABLE_JSON, PORTABLE_JSON_NULL


class OGFieldResourceState(Base):
    __tablename__ = "og_field_resource_state"

    resource_id: Mapped[int] = mapped_column(
        PORTABLE_BIGINT,
        ForeignKey("og_field_resources.id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission_mask: Mapped[int] = mapped_column(SmallInteger, primary_key=True)

    name: Mapped[str | None] = mapped_column(String, nullable=True)
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    name_local: Mapped[str | None] = mapped_column(String, nullable=True)
    state_province: Mapped[str | None] = mapped_column(String, nullable=True)
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    basin: Mapped[str | None] = mapped_column(String, nullable=True)
    reservoir_formation: Mapped[str | None] = mapped_column(String, nullable=True)
    location_type: Mapped[str | None] = mapped_column(String, nullable=True)
    production_conventionality: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
    primary_hydrocarbon_group: Mapped[str | None] = mapped_column(String, nullable=True)
    field_status: Mapped[str | None] = mapped_column(String, nullable=True)
    latitude: Mapped[float | None] = mapped_column(PORTABLE_FLOAT, nullable=True)
    longitude: Mapped[float | None] = mapped_column(PORTABLE_FLOAT, nullable=True)
    discovery_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    production_start_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fid_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    owners: Mapped[Any | None] = mapped_column(PORTABLE_JSON_NULL, nullable=True)
    operators: Mapped[Any | None] = mapped_column(PORTABLE_JSON_NULL, nullable=True)

    provenance: Mapped[dict[str, Any]] = mapped_column(PORTABLE_JSON, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "permission_mask BETWEEN 0 AND 3",
            name="ck_resource_state_permission_mask",
        ),
        Index("ix_resource_state_mask_resource", "permission_mask", "resource_id"),
        Index("ix_resource_state_mask_name", "permission_mask", "name", "resource_id"),
        *(
            Index(f"ix_resource_state_mask_{field}", "permission_mask", field)
            for field in FILTER_OPTION_FIELDS
        ),
    )


_VALUE_COLUMNS = frozenset(OGFieldResourceState.__table__.columns.keys()) - {
    "resource_id",
    "permission_mask",
    "provenance",
}
if _VALUE_COLUMNS != frozenset(ATTRIBUTE_NAMES):
    raise RuntimeError(
        "OGFieldResourceState value columns out of sync with ATTRIBUTE_NAMES: "
        f"{_VALUE_COLUMNS ^ frozenset(ATTRIBUTE_NAMES)}"
    )
