from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from stitch.ogsi.model import OGSISrcKey

from .common import Base


class OGFieldSourcePriority(Base):
    __tablename__ = "og_field_source_priority"

    source: Mapped[OGSISrcKey] = mapped_column(String(10), primary_key=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
