from __future__ import annotations

from collections.abc import Collection, Sequence

from sqlalchemy import (
    Index,
    and_,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, relationship
from stitch.ogsi.model import OGFieldSource, OGFieldResource
from stitch.ogsi.model.types import OGSISrcKey

from .membership import MembershipModel, MembershipStatus
from .oil_gas_field_source import OilGasFieldSourceModel
from .og_field_source_priority import OGFieldSourcePriority

from .resource_base import ResourceBase


class ResourceModel(ResourceBase):
    __tablename__ = "og_field_resources"
    __table_args__ = (Index("rp_repointed_id_idx", "repointed_id"),)

    # SQLAlchemy will automatically see the foreign key `memberships.resource_id`
    # and configure the appropriate SQL statement to load the membership objects
    memberships: Mapped[list[MembershipModel]] = relationship()

    def as_empty_entity(self):
        return OGFieldResource(
            id=self.id,
            source_data=[],
            constituents=frozenset(),
        )

    @classmethod
    async def source_data_by_resource_id(
        cls,
        session: AsyncSession,
        resource_ids: Collection[int],
        licensed_sources: Collection[OGSISrcKey] | None = None,
    ) -> dict[int, list[tuple[OGFieldSource, int]]]:
        """Active ``(source entity, default priority)`` rows per resource id.

        One query mirroring the SQL ``active_src`` CTE: membership -> resource ->
        default priority -> source header, restricted to active memberships of
        non-repointed resources. ``values`` selectin-loads with the entity;
        licensing is applied in SQL. This is the raw source-listing helper for the
        detail path -- it returns the *global default* priority only. Per-field
        override tiering can't be expressed as one scalar per source (a record's
        effective rank now varies by field), so field-scoped ordering lives in the
        SQL ranking (``field_source_values`` / ``queries.add_ranking``), not here.
        Rows are ordered by ``(default priority, source, source_pk)``.
        """
        by_id: dict[int, list[tuple[OGFieldSource, int]]] = {
            rid: [] for rid in resource_ids
        }
        if not by_id:
            return by_id

        m, r, s = MembershipModel, cls, OilGasFieldSourceModel
        p = OGFieldSourcePriority
        stmt = (
            select(m.resource_id, s, p.priority.label("priority"))
            .select_from(m)
            .join(r, r.id == m.resource_id)
            .join(p, p.source == m.source)
            # dual-key: membership.source is not FK-tied to the header's source,
            # so matching on source_pk alone could admit a mismatched row.
            .join(s, and_(s.id == m.source_pk, s.source == m.source))
            .where(
                r.repointed_id.is_(None),
                m.status == MembershipStatus.ACTIVE,
                m.resource_id.in_(by_id.keys()),
            )
        )
        if licensed_sources is not None:
            stmt = stmt.where(m.source.in_(list(dict.fromkeys(licensed_sources))))

        stmt = stmt.order_by(p.priority, m.source, s.id)

        for resource_id, src_model, prio in (await session.execute(stmt)).all():
            by_id[resource_id].append((src_model.as_entity(), prio))
        return by_id

    async def get_source_data(self, session: AsyncSession) -> Sequence[OGFieldSource]:
        by_id = await type(self).source_data_by_resource_id(session, [self.id])
        return [src for src, _ in by_id[self.id]]
