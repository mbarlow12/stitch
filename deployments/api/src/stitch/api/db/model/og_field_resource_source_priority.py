
from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from stitch.ogsi.model.types import OGSISrcKey

from stitch.api.entities import User as UserEntity

from .common import Base
from .mixins import TimestampMixin, UserAuditMixin
from .oil_gas_field_source_value import ATTRIBUTE_NAMES
from .types import PORTABLE_BIGINT


class OGFieldResourceSourcePriority(TimestampMixin, UserAuditMixin, Base):
    __tablename__ = "og_field_resource_source_priority"

    resource_id: Mapped[int] = mapped_column(
        PORTABLE_BIGINT,
        ForeignKey("og_field_resources.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source_pk: Mapped[int] = mapped_column(
        PORTABLE_BIGINT,
        ForeignKey("oil_gas_field_sources.id", ondelete="CASCADE"),
        primary_key=True,
    )
    colname: Mapped[str] = mapped_column(String(50), primary_key=True)
    source: Mapped[OGSISrcKey] = mapped_column(
        String(10),
        ForeignKey("og_field_source_priority.source"),
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "colname IN (" + ", ".join(f"'{n}'" for n in ATTRIBUTE_NAMES) + ")",
            name="ck_field_priority_colname",
        ),
    )

    @classmethod
    def create(
        cls,
        *,
        created_by: UserEntity,
        resource_id: int,
        source: OGSISrcKey,
        source_pk: int,
        colname: str,
        priority: int,
    ):
        return cls(
            resource_id=resource_id,
            source=source,
            source_pk=source_pk,
            colname=colname,
            priority=priority,
            created_by_id=created_by.id,
            last_updated_by_id=created_by.id,
        )
